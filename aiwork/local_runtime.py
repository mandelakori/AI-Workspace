"""Owned local Ollama instances and measured resource admission. Never pulls models."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import math
from dataclasses import replace
from time import monotonic, sleep
from urllib.request import Request, build_opener, ProxyHandler

from .http import NoRedirect
from .process import environment, executable, owned_process
from .trial_budget import write

MIB = 1024**2


def listener_owner(port: int) -> int:
    """Identify the exact Windows loopback listener before any load/generation."""
    if os.name!='nt':raise RuntimeError('owned Ollama listener verification currently requires Windows')
    size=ctypes.c_ulong(0);api=ctypes.windll.iphlpapi.GetExtendedTcpTable
    api(None,ctypes.byref(size),False,2,3,0)
    data=ctypes.create_string_buffer(size.value)
    if api(data,ctypes.byref(size),False,2,3,0)!=0:raise OSError('TCP ownership inventory failed')
    values=ctypes.cast(data,ctypes.POINTER(ctypes.c_uint32))
    owners=set()
    for i in range(values[0]):
        offset=1+6*i
        if socket.ntohs(values[offset+2]&65535)==port and values[offset+1]==16777343:
            owners.add(values[offset+5])
    if len(owners)!=1:raise RuntimeError('loopback listener ownership is unknown')
    return owners.pop()


def local_json(endpoint: str, route: str, body: dict | None = None, timeout: float = 3) -> dict:
    if not re.fullmatch(r'http://127\.0\.0\.1:\d+', endpoint):
        raise ValueError('owned inference requires an explicit IPv4 loopback endpoint')
    request = Request(endpoint+'/'+route, None if body is None else json.dumps(body).encode(),
                      {'Content-Type':'application/json'})
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout) as response:
        return json.loads(response.read(4*1024*1024+1))


def memory_snapshot() -> dict:
    """Windows available physical RAM plus bounded GPU telemetry; unknown is rejected."""
    result = {'at':monotonic()}
    if os.name == 'nt':
        class Memory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),
                      *[(name,ctypes.c_ulonglong) for name in
                        ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]]
        status=Memory();status.length=ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            result.update(ram_total_bytes=status.total,ram_available_bytes=status.available)
    program=executable('nvidia-smi')
    if program:
        row=subprocess.run([program,'--query-gpu=memory.total,memory.free,memory.used',
                            '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
        if row.returncode==0:
            lines=row.stdout.strip().splitlines()
            if len(lines)==1:
                total,free,used=map(int,lines[0].split(','))
                result.update(gpu_total_bytes=total*MIB,gpu_free_bytes=free*MIB,gpu_used_bytes=used*MIB)
    return result


def copy_model(source: Path, destination: Path, manifest: str, *, deadline: float | None = None) -> dict:
    """Copy only this existing manifest's blobs; never link writable files to originals."""
    source=source.resolve(strict=True);destination=destination.resolve()
    if deadline is not None and monotonic()>=deadline:raise TimeoutError('model copy deadline')
    if destination.exists() or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('model copy requires a new independent directory')
    if not re.fullmatch(r'registry\.ollama\.ai/library/[a-z0-9._-]+/[a-z0-9._-]+',manifest):
        raise ValueError('unsupported local model manifest path')
    origin=source/'manifests'/manifest
    if origin.is_symlink() or not origin.is_relative_to(source) or not origin.is_file():
        raise ValueError('missing plain installed model manifest')
    raw=origin.read_bytes();data=json.loads(raw)
    blobs={entry['digest']:entry['size'] for entry in [data['config'],*data['layers']]}
    if shutil.disk_usage(destination.parent).free < sum(blobs.values())+2*1024**3:
        raise ValueError('insufficient disk headroom for isolated model copy')
    destination.mkdir();(destination/'blobs').mkdir()
    target=destination/'manifests'/manifest;target.parent.mkdir(parents=True);target.write_bytes(raw)
    receipt={'source':str(source),'destination':str(destination),'manifest':manifest,
             'manifest_sha256':hashlib.sha256(raw).hexdigest(),'blobs':{}}
    for digest,size in blobs.items():
        if not re.fullmatch(r'sha256:[a-f0-9]{64}',digest) or type(size) is not int or size<0:
            raise ValueError('invalid installed blob descriptor')
        path=source/'blobs'/digest.replace(':','-')
        if path.is_symlink() or path.stat().st_size != size:
            raise ValueError('installed blob is linked or has an unexpected size')
        copied=destination/'blobs'/path.name
        hasher=hashlib.sha256()
        with path.open('rb') as inp,copied.open('xb') as out:
            while block:=inp.read(8*MIB):
                if deadline is not None and monotonic()>=deadline:raise TimeoutError('model copy deadline')
                hasher.update(block);out.write(block)
        if hasher.hexdigest()!=digest[7:]:raise ValueError('installed model blob hash mismatch')
        receipt['blobs'][digest]={'bytes':size,'sha256':hasher.hexdigest()}
    write(destination.parent/'model-copy.json',receipt)
    return receipt


@contextmanager
def isolated_ollama(binary: str, store: Path, context: int, artifacts: Path,
                    timeout: float, *, gpu_headroom_mib: int = 512):
    """No existing listener is touched. The Windows job owns server and runners."""
    if not 1024<=context<=262144 or timeout<=0 or not 0<=gpu_headroom_mib<=8192:
        raise ValueError('invalid isolated inference bounds')
    artifacts.mkdir(parents=True,exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    if port==11434:raise ValueError('refuse shared Ollama port')
    endpoint=f'http://127.0.0.1:{port}'
    env=environment(artifacts/'home')
    env.update(OLLAMA_HOST=f'127.0.0.1:{port}',OLLAMA_MODELS=str(store.resolve()),
               OLLAMA_CONTEXT_LENGTH=str(context),OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1',
               OLLAMA_NO_CLOUD='1',OLLAMA_NOPRUNE='1',OLLAMA_KEEP_ALIVE='3m',
               OLLAMA_LOAD_TIMEOUT='45s',OLLAMA_FLASH_ATTENTION='1',OLLAMA_KV_CACHE_TYPE='f16',
               OLLAMA_GPU_OVERHEAD=str(gpu_headroom_mib*MIB))
    deadline=monotonic()+timeout
    receipt={'endpoint':endpoint,'context':context,'store':str(store.resolve()),'owned':True,
             'gpu_headroom_mib':gpu_headroom_mib,'flash_attention':True,'kv_cache_type':'f16',
             'parallel':1,'ready':False}
    child=None
    with (artifacts/'server.log').open('wb') as log:
        try:
            with owned_process([binary,'serve'],cwd=artifacts,env=env,stdin=subprocess.DEVNULL,
                               stdout=log,stderr=subprocess.STDOUT) as child:
                receipt.update(pid=child.pid,executable=str(Path(binary).resolve()))
                write(artifacts/'ownership.json',receipt)
                while monotonic()<deadline:
                    if child.poll() is not None:raise RuntimeError('isolated Ollama exited before readiness')
                    try:
                        version=local_json(endpoint,'api/version',timeout=min(1,max(.01,deadline-monotonic())))
                        if listener_owner(port)!=child.pid:
                            raise RuntimeError('private inference listener is not owned by this process')
                        receipt.update(ready=True,version=version,listener_pid=child.pid);break
                    except OSError:sleep(.1)
                else:raise TimeoutError('isolated Ollama readiness deadline')
                write(artifacts/'ownership.json',receipt)
                yield endpoint,deadline,child.pid
        finally:
            receipt['cleanup_passed']=child is not None and child.poll() is not None
            write(artifacts/'ownership.json',receipt)
            if child is not None and not receipt['cleanup_passed']:
                raise RuntimeError('owned local inference cleanup failed')


def admit_context(report: dict, *, input_tokens: int, output_tokens: int, reserve_tokens: int,
                  maximum: int, memory: dict, deadline_seconds: float,
                  gpu_headroom_mib: int = 512, ram_headroom_mib: int = 2048) -> dict:
    """Smallest empirically qualified window. No extrapolated/unmeasured admission."""
    if (any(type(v) is not int or v<0 for v in (input_tokens,output_tokens,reserve_tokens,maximum,
                                                gpu_headroom_mib,ram_headroom_mib))
            or not math.isfinite(deadline_seconds) or deadline_seconds<=0):
        raise ValueError('invalid local admission policy')
    rows=[];ram_envelope=0
    for row in sorted(report['contexts'],key=lambda r:r['context']):
        reasons=[];size=row['context'];estimate=None
        if row.get('status')!='measured':reasons.append('context not independently measured')
        if size>maximum:reasons.append('operator context maximum')
        if size<input_tokens+output_tokens+reserve_tokens:reasons.append('observed task demand')
        if not all(type(memory.get(k)) is int and memory[k]>=0 for k in ('gpu_free_bytes','ram_available_bytes')):
            reasons.append('memory telemetry unavailable')
        elif row.get('status')=='measured':
            # Global available RAM can rise during a probe as unrelated memory is
            # reclaimed. Never treat that as zero model RAM or a cheaper larger
            # window: retain the smaller-window peak plus resident CPU footprint.
            resident=row.get('resident',{})
            cpu=max(0,resident.get('size',0)-resident.get('size_vram',0))
            ram_envelope=max(ram_envelope,row['ram_increment_bytes'],cpu+512*MIB if cpu else 0)
            if memory['gpu_free_bytes'] < row['gpu_increment_bytes']+gpu_headroom_mib*MIB:reasons.append('GPU headroom')
            if memory['ram_available_bytes'] < ram_envelope+ram_headroom_mib*MIB:reasons.append('RAM headroom')
        prefill=row.get('prefill_tokens_per_second',0);generation=row.get('generation_tokens_per_second',0)
        if prefill<=0 or generation<=0:reasons.append('throughput unknown')
        else:
            estimate=(row.get('load_seconds',0)+row.get('initial_prefill_overhead_seconds',0)+
                      input_tokens/prefill+output_tokens/generation)
            if estimate>deadline_seconds:reasons.append('inference deadline')
        rows.append({'context':size,'rejected':reasons,'estimated_request_seconds':estimate,
                     'required_ram_bytes':ram_envelope})
    return {'selected':next((r['context'] for r in rows if not r['rejected']),None),
            'demand':input_tokens+output_tokens+reserve_tokens,'observed_input_tokens':input_tokens,
            'memory':memory,'deadline_seconds':deadline_seconds,'candidates':rows,
            'gpu_headroom_mib':gpu_headroom_mib,'ram_headroom_mib':ram_headroom_mib}


@contextmanager
def calibrated_runtime(profile, task, artifacts: Path, deadline: float):
    """Opt-in calibrated profiles use their own inference server, never shared Ollama."""
    path=Path(profile.local_calibration).resolve(strict=True);raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=profile.calibration_sha256:
        raise ValueError('calibration hash changed; require operator review')
    report=json.loads(raw)
    if report['model']!=profile.model or report.get('engineering_benchmark') is not False:
        raise ValueError('calibration/model identity mismatch')
    if not task.context_input_tokens:
        raise ValueError('calibrated admission requires observed context_input_tokens')
    observed=max(task.context_input_tokens,max(0,task.min_context-profile.output_tokens-profile.context_reserve_tokens))
    admission=admit_context(report,input_tokens=observed,output_tokens=profile.output_tokens,
            reserve_tokens=profile.context_reserve_tokens,maximum=profile.context,memory=memory_snapshot(),
            deadline_seconds=max(.001,deadline-monotonic()-min(20,max(4,task.timeout//5))),
            gpu_headroom_mib=profile.gpu_headroom_mib,ram_headroom_mib=profile.ram_headroom_mib)
    write(artifacts/'local-context-admission.json',admission|{'calibration_sha256':profile.calibration_sha256})
    if admission['selected'] is None:raise ValueError('no measured context satisfies demand, memory and deadline')
    copy=report['model_copy'];store=Path(copy['destination']).resolve(strict=True)
    if store!=path.parent/'model-store':raise ValueError('calibration model store is outside its owned bundle')
    manifest=store/'manifests'/copy['manifest']
    if hashlib.sha256(manifest.read_bytes()).hexdigest()!=copy['manifest_sha256']:
        raise ValueError('isolated model manifest changed')
    binary=executable('ollama')
    if not binary:raise ValueError('installed Ollama executable unavailable')
    with isolated_ollama(binary,store,admission['selected'],artifacts/'local-inference',
                         max(.001,deadline-monotonic()),gpu_headroom_mib=report['plan']['gpu_headroom_mib']) as (endpoint,_,_):
        try:
            yield replace(profile,endpoint=endpoint+'/v1',context=admission['selected'])
        finally:
            try:
                resident=local_json(endpoint,'api/ps',timeout=min(1,max(.01,deadline-monotonic())))
                write(artifacts/'local-inference/resident-after.json',resident)
                active=next((m for m in resident['models'] if m['name']==profile.model),None)
                if active and active.get('context_length')!=admission['selected']:
                    receipt_path=artifacts/'execution-receipt.json'
                    if receipt_path.exists():
                        receipt=json.loads(receipt_path.read_bytes());receipt['status']='resource_contract_failure';write(receipt_path,receipt)
                    raise RuntimeError('served context differs from admitted context')
            except (OSError,ValueError) as error:
                write(artifacts/'local-inference/telemetry-error.json',{'error':type(error).__name__})
