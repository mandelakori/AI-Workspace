"""Owned OpenCode readiness barrier and a fail-closed provider catalog check.

No tool schemas, prompts, or model arguments are rewritten by the relay.
Private server credentials and HTTP authorization headers are never archived.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
from threading import Event, Lock, Thread, current_thread
import socket
from time import monotonic, sleep
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler, Request

from .http import NoRedirect
from .process import owned_process, run, Result
from .trial_budget import write

REQUIRED = frozenset({'checks_focus', 'checks_edit', 'checks_check', 'checks_diff'})
NATIVE = frozenset({'glob', 'grep', 'list', 'todowrite'})


def catalog(body: dict, allow_read: bool = False) -> dict:
    tools = body.get('tools', [])
    if not isinstance(tools, list):
        tools = []
    names = [t.get('function', {}).get('name') for t in tools if isinstance(t, dict)]
    allowed = REQUIRED | NATIVE | ({'read'} if allow_read else set())
    valid = (all(isinstance(n, str) for n in names) and len(names) == len(tools)
             and len(names) == len(set(names)))
    offered = {n for n in names if isinstance(n, str)}
    return {'offered': sorted(offered), 'missing': sorted(REQUIRED - offered),
            'unexpected': sorted(offered - allowed),
            'passed': valid and REQUIRED <= offered and offered <= allowed}


class ProviderGate:
    def __init__(self, endpoint: str, model: str, key: str, artifacts: Path,
                 deadline: float, allow_read: bool = False):
        self.upstream = urlsplit(endpoint.rstrip('/'))
        if (self.upstream.scheme not in {'http', 'https'} or not self.upstream.hostname
                or self.upstream.username or self.upstream.password
                or self.upstream.query or self.upstream.fragment):
            raise ValueError('invalid provider endpoint')
        self.model, self.key, self.artifacts = model, key, artifacts
        self.deadline, self.allow_read = deadline, allow_read
        self.token = secrets.token_urlsafe(32)
        self.failed = Event()
        self.lock = Lock()
        self.count = 0
        self.captured = 0
        self.receipts = []
        self.connections = set()
        self.handlers = set()

    def save(self):
        write(self.artifacts / 'provider-gate.json', {
            'failed_closed': self.failed.is_set(), 'requests': self.receipts,
            'required': sorted(REQUIRED), 'request_rewriting': False,
            'captured_bytes': self.captured,
        })

    def __enter__(self):
        gate = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass

            def setup(self):
                super().setup()
                self.connection.settimeout(min(5, max(.01, gate.deadline-monotonic())))
                with gate.lock:
                    gate.connections.add(self.connection); gate.handlers.add(current_thread())

            def finish(self):
                try: super().finish()
                finally:
                    with gate.lock:
                        gate.connections.discard(self.connection); gate.handlers.discard(current_thread())

            def do_POST(self):
                with gate.lock:
                    if not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + gate.token):
                        self.send_error(401); return
                    size = int(self.headers.get('Content-Length', '-1'))
                    if (self.path != '/v1/chat/completions' or not 0 < size <= 2_097_152
                            or gate.captured + size > 16 * 1024 * 1024):
                        gate.failed.set(); gate.save(); self.send_error(400); return
                    raw = self.rfile.read(size)
                    gate.count += 1
                    number = gate.count
                    gate.captured += len(raw)
                    (gate.artifacts / f'provider-request-{number:03}.json').write_bytes(raw)
                    try:
                        body = json.loads(raw)
                        check = catalog(body, gate.allow_read)
                        admitted = (check['passed'] and body.get('model') == gate.model
                                    and not gate.failed.is_set() and monotonic() < gate.deadline)
                    except (ValueError, AttributeError):
                        check = {'passed': False, 'offered': [], 'missing': sorted(REQUIRED)}
                        admitted = False
                    receipt = {'request': number, **check, 'forwarded': admitted,
                               'body_sha256': hashlib.sha256(raw).hexdigest()}
                    gate.receipts.append(receipt)
                    if not admitted:
                        gate.failed.set(); gate.save()
                        self.send_response(400); self.send_header('Content-Type', 'application/json'); self.end_headers()
                        self.wfile.write(b'{"error":{"code":"required_tools_unavailable","message":"Provider catalog or model failed the frozen guard"}}')
                        return
                    gate.save()
                connection = None
                response_path = gate.artifacts / f'provider-response-{number:03}.sse'
                try:
                    cls = http.client.HTTPSConnection if gate.upstream.scheme == 'https' else http.client.HTTPConnection
                    connection = cls(gate.upstream.hostname, gate.upstream.port,
                                     timeout=max(.01, gate.deadline - monotonic()))
                    headers = {'Content-Type': 'application/json'}
                    if gate.key: headers['Authorization'] = 'Bearer ' + gate.key
                    connection.request('POST', gate.upstream.path + '/chat/completions', raw, headers)
                    with gate.lock:
                        if connection.sock is not None: gate.connections.add(connection.sock)
                    response = connection.getresponse()
                    self.send_response(response.status)
                    self.send_header('Content-Type', response.getheader('Content-Type', 'application/json'))
                    self.send_header('Connection', 'close'); self.end_headers()
                    receipt['upstream_status'] = response.status
                    with response_path.open('wb') as stream:
                        while monotonic() < gate.deadline:
                            block = response.read1(65536)
                            if not block: break
                            with gate.lock:
                                gate.captured += len(block)
                                if gate.captured > 16 * 1024 * 1024:
                                    raise ValueError('provider evidence budget exhausted')
                            stream.write(block); stream.flush()
                            self.wfile.write(block); self.wfile.flush()
                        else: raise TimeoutError('provider deadline expired')
                    receipt['response_sha256'] = hashlib.sha256(response_path.read_bytes()).hexdigest()
                except (OSError, ValueError, http.client.HTTPException) as error:
                    gate.failed.set()
                    receipt['error'] = type(error).__name__
                    self.close_connection = True
                finally:
                    if connection is not None:
                        with gate.lock: gate.connections.discard(connection.sock)
                        connection.close()
                    with gate.lock: gate.save()

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f'http://127.0.0.1:{self.server.server_port}/v1'
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        with self.lock: connections = list(self.connections); handlers = list(self.handlers)
        for connection in connections:
            try: connection.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        self.server.server_close(); self.thread.join(timeout=1)
        cleanup_deadline = monotonic()+2
        for handler in handlers: handler.join(timeout=max(0,cleanup_deadline-monotonic()))
        if any(h.is_alive() for h in handlers) or self.thread.is_alive():
            self.failed.set(); self.save()
            raise RuntimeError('provider relay cleanup failed')
        self.save()


@contextmanager
def ready_server(binary: str, work: Path, artifacts: Path, env: dict,
                 deadline: float, stop: Path | None):
    """Wait for this exact private location's MCP connection before submitting work."""
    if os.name != 'nt' and (os.environ.get('AIWORK_TRIAL_BUDGET') or os.environ.get('AIWORK_TRIAL_GROUP_MEMBER')):
        raise RuntimeError('measured private-server ownership currently requires Windows jobs')
    state = {}; started = monotonic(); lines = []; lock = Lock()
    def read_output(pipe):
        for raw in iter(pipe.readline, b''):
            line = raw.decode('utf-8', 'replace')
            with lock:
                if match := re.search(r'server listening on (http://127\.0\.0\.1:\d+)', line): state['url'] = match[1]
                if match := re.search(r'server password (\S+)', line): state['password'] = match[1]
                clean = re.sub(r'(server password )\S+', r'\1[REDACTED]', line)
                if sum(map(len, lines)) < 65536: lines.append(clean)
    receipt = {'ready': False, 'owned': True, 'private_server': True}
    child = reader = None
    try:
        with owned_process([binary, 'serve', '--hostname', '127.0.0.1', '--port', '0'],
                           cwd=work, env=env, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as child:
            reader = Thread(target=read_output, args=(child.stdout,), daemon=True); reader.start()
            receipt['pid'] = child.pid
            opener = build_opener(ProxyHandler({}), NoRedirect())
            while monotonic() < deadline and not (stop and stop.exists()):
                if child.poll() is not None: raise RuntimeError('private OpenCode server exited before readiness')
                with lock: location = dict(state)
                if 'url' in location and 'password' in location:
                    auth = base64.b64encode(('opencode:' + location['password']).encode()).decode()
                    try:
                        request = Request(location['url'] + '/api/mcp', headers={'Authorization': 'Basic ' + auth})
                        with opener.open(request, timeout=min(1, max(.01, deadline-monotonic()))) as response:
                            data = json.loads(response.read(65537))
                        if Path(data.get('location',{}).get('directory','')).resolve()!=work.resolve():
                            raise RuntimeError('MCP readiness belongs to a different location')
                        servers = data.get('data', [])
                        if any(s.get('name') == 'checks' and s.get('status', {}).get('status') == 'connected' for s in servers):
                            receipt.update(ready=True, elapsed=round(monotonic()-started, 3), servers=servers)
                            write(artifacts / 'catalog-readiness.json', receipt)
                            client_env = {**env, 'OPENCODE_SERVER_PASSWORD': location['password']}
                            break
                    except OSError: pass
                sleep(.05)
            else: raise RuntimeError('required MCP server did not become ready within the attempt')
            yield location['url'], client_env
    finally:
        if reader is not None: reader.join(timeout=1)
        if child is not None and child.stdout is not None: child.stdout.close()
        receipt['cleanup_passed'] = (child is not None and child.poll() is not None
                                     and (reader is None or not reader.is_alive()))
        receipt['elapsed_total'] = round(monotonic()-started, 3)
        write(artifacts / 'catalog-readiness.json', receipt)
        (artifacts / 'private-server.log').write_text(''.join(lines), encoding='utf-8')
        if child is not None and not receipt['cleanup_passed']:
            raise RuntimeError('private server cleanup failed')


def guarded_run(binary, profile, work, artifacts, env, config, prompt, timeout, stop, key):
    started = monotonic(); deadline = started + timeout
    with ProviderGate(profile.endpoint, profile.model, key, artifacts, deadline, profile.context > 8192) as gate:
        provider = config['providers']['aiwork']
        provider['settings']['baseURL'] = gate.endpoint
        provider['settings']['apiKey'] = '{env:AIWORK_CATALOG_TOKEN}'
        provider['env'] = ['AIWORK_CATALOG_TOKEN']
        env = {**env, 'AIWORK_CATALOG_TOKEN': gate.token, 'OPENCODE_CONFIG_CONTENT': json.dumps(config)}
        with ready_server(binary, work, artifacts, env, deadline, stop) as (url, client_env):
            result = run([binary, 'run', '--server', url, '--title', 'AI Workspace engineering',
                          '--format', 'json', '--model', config['model'], '--', prompt],
                         work, max(0, deadline-monotonic()), client_env, stop,
                         output_limit=8*1024*1024, stdout_path=artifacts/'agent-live.jsonl')
    return Result(1 if gate.failed.is_set() else result.code, monotonic()-started,
                  result.stdout, result.stderr, result.timed_out, result.truncated)
