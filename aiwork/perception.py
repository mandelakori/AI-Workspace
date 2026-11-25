"""Read-only screenshot observations, kept outside the engineering worker scope."""
from __future__ import annotations

import base64
from dataclasses import dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
from threading import Event, Thread
from time import monotonic
import tomllib
from typing import Protocol
from urllib.parse import urlsplit

from .http import request
from .local_runtime import MIB, memory_snapshot
from .process import environment, executable, run
from .remote import a100_session
from .schema import Profile

MAX_IMAGE = 4 * MIB
MODEL = 'omniparser-v2'
PINS = {'source': '354021201345a96178360b28733573e27269f2de',
        'weights': 'f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4',
        'florence_processor': '5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac',
        'florence_code': 'f6c1a25888ffc1d945ee8a1a77ac833c7303d46e'}
REMOTE_TOKEN = 'AIWORK_OMNI_TOKEN'
UNCERTAIN = 'A100_PERCEPTION_UNCERTAIN'


def png_size(frame: bytes) -> tuple[int, int]:
    if not 33 <= len(frame) <= MAX_IMAGE or frame[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR':
        raise ValueError('expected a PNG of at most 4 MiB')
    w, h = struct.unpack('!II', frame[16:24])
    check_dimensions(w, h)
    return w, h


def check_dimensions(w: int, h: int) -> None:
    if type(w) is not int or type(h) is not int or not 0 < w <= 4096 or not 0 < h <= 4096 or w*h > 4096*2160:
        raise ValueError('screenshot dimensions exceed the interpretation limit')


def normalize_elements(rows) -> list[dict]:
    if not isinstance(rows, list) or len(rows) > 256:
        raise ValueError('invalid perception elements')
    elements = []
    for row in rows:
        if not isinstance(row, dict) or row.get('kind') not in {'text','icon'} or not isinstance(row.get('description'), str):
            raise ValueError('invalid perception element')
        box = row.get('bbox')
        if (not isinstance(box, list) or len(box) != 4
                or any(type(x) not in (int,float) or not math.isfinite(x) or not 0 <= x <= 1 for x in box)
                or box[0] >= box[2] or box[1] >= box[3]):
            raise ValueError('invalid normalized screenshot coordinates')
        elements.append({'id':len(elements)+1, 'kind':row['kind'], 'bbox':box, 'description':row['description'][:512]})
    return elements


def approved_observation(path: Path, sha256: str) -> tuple[bytes, dict]:
    """Read only operator-approved, bounded JSON from a completed local parse."""
    with path.open('rb') as stream:
        raw = stream.read(512*1024+1)
    if len(raw) > 512*1024 or hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError('screen observation hash mismatch or size limit exceeded')
    result = json.loads(raw)
    if (type(result) is not dict or type(result.get('schema')) is not int or result['schema'] != 1
            or result.get('pins') != PINS or result.get('backend') != MODEL or result.get('location') != 'local'
            or result.get('cleanup_passed') is not True or result.get('untrusted_screen_content') is not True
            or result.get('coordinate_system') != 'normalized_xyxy_image'):
        raise ValueError('screen inspection requires a completed local OmniParser observation')
    w,h = result.get('width'),result.get('height')
    check_dimensions(w,h)
    return raw, {'sha256':sha256, 'width':w,'height':h,'coordinate_system':result['coordinate_system'],
                 'untrusted_screen_content':True,'elements':normalize_elements(result.get('elements'))}


def observations(frame: bytes, result: dict, location: str, elapsed: float) -> dict:
    w, h = png_size(frame)
    if not isinstance(result, dict) or result.get('pins') != PINS or result.get('cleanup') is not True:
        raise ValueError('unverified perception backend version or cleanup')
    elements = normalize_elements(result.get('elements'))
    measured = result.get('metrics', {})
    if not isinstance(measured, dict):
        raise ValueError('invalid perception resource metrics')
    metrics = {k:v for k,v in measured.items() if k in {
        'server_seconds','initialization_seconds','inference_seconds','peak_cuda_bytes',
        'available_ram_before','available_ram_after','free_vram_before','free_vram_after'}
        and type(v) in (int,float) and 0 <= v < 10**14}
    return {'schema':1, 'backend':MODEL, 'location':location, 'width':w, 'height':h, 'pins':PINS,
            'coordinate_system':'normalized_xyxy_image', 'elements':elements,
            'metrics':metrics | {'elapsed_seconds':round(elapsed,3)}, 'cleanup_passed':True,
            'untrusted_screen_content':True}


@dataclass(frozen=True)
class PerceptionConfig:
    python: str = ''
    source: str = ''
    cache: str = ''
    ocr: str = ''
    enable_remote: bool = False
    local_port: int = 18771
    remote_port: int = 18770
    timeout: int = 90
    ram_mib: int = 4096
    vram_mib: int = 6144

    @classmethod
    def load(cls, path: Path | None):
        if path is None:
            return cls()
        data = tomllib.loads(path.read_text(encoding='utf-8'))
        for key in ('python','source','cache','ocr'):
            if data.get(key):
                data[key] = str((path.resolve().parent/data[key]).resolve(strict=True))
        config = cls(**data)
        if (type(config.enable_remote) is not bool or any(type(x) is not int for x in (
                config.timeout,config.ram_mib,config.vram_mib,config.local_port,config.remote_port))
                or not 10<=config.timeout<=180 or not 512<=config.ram_mib<=131072 or not 512<=config.vram_mib<=65536
                or not all(1024<=p<=65535 for p in (config.local_port,config.remote_port))):
            raise ValueError('invalid bounded perception configuration')
        paths = (config.python,config.source,config.cache,config.ocr)
        if any(paths) and (not all(paths) or not Path(config.python).is_file()
                           or any(not Path(path).is_dir() for path in paths[1:])):
            raise ValueError('configure the isolated interpreter, source and offline model caches together')
        return config


def require_memory(snapshot: dict, ram_mib: int, vram_mib: int) -> None:
    if snapshot.get('ram_available_bytes',0)<ram_mib*MIB or snapshot.get('gpu_free_bytes',0)<vram_mib*MIB:
        raise ValueError('insufficient measured RAM or VRAM for screenshot interpretation')


def capture_screen(root: Path) -> bytes:
    if os.name != 'nt' or not (shell := executable('powershell.exe')):
        raise ValueError('primary-screen capture requires an interactive Windows desktop')
    script = """
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$r=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
if ($r.Width -gt 8192 -or $r.Height -gt 8192 -or !$r.Width -or !$r.Height) { throw 'Unsupported desktop size' }
$image=[Drawing.Bitmap]::new($r.Width,$r.Height)
$g=[Drawing.Graphics]::FromImage($image)
try {
    $g.CopyFromScreen($r.Location,[Drawing.Point]::Empty,$r.Size)
    $scale=[Math]::Min(1,[Math]::Min(1920.0/$r.Width,1080.0/$r.Height))
    $scaled=[Drawing.Bitmap]::new($image,[int]($scale*$r.Width),[int]($scale*$r.Height))
    $stream=[IO.MemoryStream]::new()
    try { $scaled.Save($stream,[Drawing.Imaging.ImageFormat]::Png); [Convert]::ToBase64String($stream.ToArray()) }
    finally { $stream.Dispose(); $scaled.Dispose() }
} finally { $g.Dispose(); $image.Dispose() }
"""
    result = run([shell,'-NoProfile','-NonInteractive','-Command',script], root, 8,
                 environment(root/'screen-home'), output_limit=6*MIB)
    if result.code or result.timed_out or result.truncated:
        raise RuntimeError('local screen capture failed or exceeded its limit')
    frame = base64.b64decode(result.stdout.strip(), validate=True)
    png_size(frame)
    return frame


class ScreenBackend(Protocol):
    def available(self) -> dict[str, bool]: ...

    def observe(self, frame: bytes, location: str, share_remote: bool = False) -> dict: ...


class Perception:
    def __init__(self, controller, settings: PerceptionConfig):
        self.controller = controller
        self.settings = settings

    def available(self) -> dict[str, bool]:
        return {'local_perception':bool(self.settings.python),'remote_perception':self.settings.enable_remote}

    def observe(self, frame: bytes, location: str, share_remote: bool = False) -> dict:
        png_size(frame)
        cfg, settings = self.controller.config, self.settings
        started = monotonic()
        if location == 'local' and not settings.python:
            raise ValueError('local OmniParser is not installed/configured')
        if location == 'a100' and (not settings.enable_remote or share_remote is not True):
            raise ValueError('remote screen processing requires configuration and explicit consent for this screenshot')
        if location == 'a100' and (settings.remote_port == cfg.ssh.get('remote_port',18080) or any(
                urlsplit(p.endpoint).port == settings.local_port for p in cfg.profiles if p.location=='a100')):
            raise ValueError('remote perception requires ports distinct from the configured engineering endpoint')
        if location not in ('local','a100'):
            raise ValueError('invalid perception location')
        profile = Profile('omni-perception',MODEL,f'http://127.0.0.1:{settings.local_port}/v1', location=location,
                          memory_mib=settings.vram_mib, api_key_env=REMOTE_TOKEN if location=='a100' else '')
        with self.controller.planes[location].reserve(profile,5):
            deadline = started + settings.timeout
            if location == 'local':
                require_memory(memory_snapshot(),settings.ram_mib,settings.vram_mib)
                result = self.local(frame,deadline)
                return observations(frame,result,location,monotonic()-started)
            if not cfg.ssh.get('alias') or len(os.environ.get(REMOTE_TOKEN,'')) < 24:
                raise ValueError('remote perception requires the existing SSH alias and a separate peer token')
            remote_cfg = replace(cfg,ssh=cfg.ssh|{'remote_port':settings.remote_port})
            marker = (cfg.execution_state or cfg.state)/UNCERTAIN
            clean_error = None
            try:
                with a100_session(remote_cfg,profile,dispatch=False,timeout=min(8,deadline-monotonic())):
                    peer = request(profile.endpoint+'/perception/status', key=os.environ[REMOTE_TOKEN],timeout=3)
                    if peer.get('pins')!=PINS or not 0 < peer.get('max_seconds',0) < deadline-monotonic()-3:
                        raise ValueError('remote peer pin or execution limit does not satisfy this request')
                    require_memory(peer.get('memory',{}),settings.ram_mib,settings.vram_mib)
                    if (cfg.state/'STOP').exists():
                        raise ValueError('controller stopped before screenshot transmission')
                    marker.touch(exist_ok=False)
                    result = request(profile.endpoint+'/perception/parse','POST',
                        {'png':base64.b64encode(frame).decode('ascii')}, key=os.environ[REMOTE_TOKEN],
                        timeout=max(.01,deadline-monotonic()))
                    if result.get('pins') == PINS and result.get('cleanup') is True and isinstance(result.get('error'),str):
                        clean_error = result['error']
                    else:
                        observed = observations(frame,result,location,monotonic()-started)
                marker.unlink()
            except (OSError,ValueError,RuntimeError,TypeError):
                if marker.exists():
                    raise RuntimeError('remote perception completion uncertain; A100 lane requires operator review') from None
                raise
            if clean_error is not None:
                raise RuntimeError(clean_error)
            return observed

    def local(self, frame: bytes, deadline: float) -> dict:
        cfg, s = self.controller.config, self.settings
        env = environment(cfg.state/'omni-home') | {'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
        remaining = deadline-monotonic()
        if remaining <= 0:
            raise TimeoutError('local perception deadline exhausted before launch')
        result = run([s.python,'-m','aiwork.omni_worker','parse',s.source,s.cache,s.ocr],cfg.state,
                     remaining,env,cfg.state/'STOP',stdin=frame,output_limit=MIB)
        if result.code or result.timed_out or result.truncated:
            raise RuntimeError('local OmniParser failed: ' + result.stderr.strip()[-500:])
        return json.loads(result.stdout) | {'cleanup':True}


def benchmark(backend: Perception, path: Path) -> dict:
    with path.open('rb') as stream:
        frame = stream.read(MAX_IMAGE+1)
    png_size(frame)
    stopped = Event()
    samples = []
    before = memory_snapshot()

    def measure():
        while not stopped.is_set():
            try:
                samples.append(memory_snapshot())
            except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):
                pass
            stopped.wait(.5)

    monitor = Thread(target=measure, daemon=True)
    monitor.start()
    try:
        result = backend.observe(frame,'local')
    finally:
        stopped.set()
        monitor.join(4)
    metric = result['metrics']
    memory_keys = ('ram_available_bytes','gpu_free_bytes')
    minima = {key:min((r[key] for r in samples if key in r),default=None) for key in memory_keys}
    return {'pins':result['pins'],'elements':len(result['elements']),
            'element_counts':{kind:sum(row['kind']==kind for row in result['elements']) for kind in ('text','icon')},
            'observations':result['elements'],
            'width':result['width'],'height':result['height'],'metrics':metric,
            'cleanup_passed':result['cleanup_passed'],'memory_before':before,'memory_after_cleanup':memory_snapshot(),
            'system_memory_samples':len(samples),'sampled_minimum_free_bytes':minima}
