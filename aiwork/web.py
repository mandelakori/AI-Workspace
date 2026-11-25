"""Loopback operator interface for the existing task controller."""
from __future__ import annotations

import base64
from dataclasses import asdict, replace
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
from pathlib import Path
import re
import secrets
from threading import Lock, Thread
from time import monotonic
from uuid import uuid4

from .controller import Controller
from .inference import Inference, ollama_residency
from .local_reclaim import reclaim_local_memory
from .local_runtime import memory_snapshot
from .perception import MAX_IMAGE, Perception, PerceptionConfig, ScreenBackend, capture_screen
from .remote import a100_session
from .router import routes
from .schema import Check, Config, Profile, Task, relative

JOB_ID = re.compile(r'[a-f0-9]{32}')
ASSETS = {'/': ('index.html', 'text/html'), '/app.css': ('app.css', 'text/css'),
          '/app.js': ('app.js', 'text/javascript')}
ARTIFACT_LIMIT = 128 * 1024


def encoded(data) -> bytes:
    return json.dumps(data, sort_keys=True, default=str, allow_nan=False).encode('utf-8')


def scoped(root: Path, name: str) -> Path:
    path = root if name == '.' else (root / relative(name)).resolve(strict=True)
    if not path.is_dir() or not path.is_relative_to(root):
        raise ValueError('directory is outside the configured root')
    return path


def artifact(root: Path, name: str) -> str:
    path = root / name
    if not path.is_file() or path.resolve() != path:
        return ''
    with path.open('rb') as stream:
        content = stream.read(ARTIFACT_LIMIT + 1)
    return content[:ARTIFACT_LIMIT].decode('utf-8-sig', 'replace') + (
        '\n[Preview truncated. See the on-disk artifact.]' if len(content) > ARTIFACT_LIMIT else '')


def fields(root: Path, file: str, *keys) -> dict:
    try:
        row = json.loads(artifact(root, file))
        return {k: row[k] for k in keys if k in row} if isinstance(row, dict) else {}
    except ValueError:
        return {}


def tail_rows(path: Path) -> list[dict]:
    if not path.is_file() or path.resolve()!=path:
        return []
    with path.open('rb') as stream:
        length = stream.seek(0,2)
        stream.seek(max(0,length-65536))
        lines = stream.read(65536).splitlines()[-48:]
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
            if isinstance(row,dict):
                rows.append(row)
        except (ValueError,TypeError):
            continue
    return rows


class Operator:
    def __init__(self, config: Config, project: Path, private: Path | None, perception: PerceptionConfig,
                 *, screen_backend: ScreenBackend | None = None):
        self.project = project.resolve(strict=True)
        self.private = private.resolve(strict=True) if private else None
        if not self.project.is_dir() or self.private and (
                not self.private.is_dir() or self.private.is_relative_to(self.project)
                or self.project.is_relative_to(self.private)):
            raise ValueError('choose an operator project directory and an optional separate verification root')
        self.controller = Controller(replace(config, profiles=tuple(
            p for p in config.profiles if p.harness == 'opencode' and not p.managed)))
        self.perception: ScreenBackend = screen_backend if screen_backend is not None else Perception(
            self.controller, perception)
        self.session = secrets.token_urlsafe(32)
        self.reviews = {}
        self.review_lock = Lock()
        self.pending = set()
        self.dispatch = Lock()
        self.ready = {}
        self.error = ''

    def task(self, body: dict) -> Task:
        if not self.controller.config.verification_image:
            raise ValueError('configure an offline Docker verification image for web submissions')
        source = self.workspace(body)
        private = body.get('verification_directory', '')
        if private and not self.private:
            raise ValueError('start the interface with --verification-root to use private verification')

        def checks(key):
            values = body.get(key, [])
            if type(values) is not list or len(values) > 16:
                raise ValueError(f'{key} requires a list of up to 16 approved commands')
            return tuple(Check.read(item) for item in values)

        def paths(key):
            values = body.get(key, [])
            if type(values) is not list or len(values) > 128 or any(type(v) is not str for v in values):
                raise ValueError(f'{key} requires explicit workspace-relative paths')
            if len(set(v.casefold() for v in values)) != len(values):
                raise ValueError(f'duplicate {key}')
            return tuple(relative(v) for v in values)

        inputs = paths('inputs')
        if not inputs:
            raise ValueError('list the files or directories the worker may read')
        commands = checks('commands')
        if not commands:
            raise ValueError('approve at least one public command the worker can execute')
        task = Task(objective=body['objective'], workspace=source, kind='agent', category='operator-web',
                    inputs=inputs, deliverables=paths('deliverables'), checks=checks('checks'),
                    location=body.get('location', 'auto'), profile=body.get('profile',''),
                    mode='engineering', write_roots=paths('write_roots'),
                    commands=commands, agent_checks=True, attempts=self.attempts(body), timeout=body.get('timeout',300),
                    complexity=body.get('complexity',2), min_context=body.get('min_context',0),
                    context_input_tokens=body.get('context_input_tokens',0),
                    verification_dir=scoped(self.private,private) if private else None)
        task.validate()
        return task

    def workspace(self, body: dict) -> Path:
        return scoped(self.project, body.get('workspace', '.'))

    def attempts(self, body: dict) -> int:
        return 1

    def policy(self, body: dict):
        task = self.task(body)
        cfg = self.controller.config
        eligible = routes(task, cfg.profiles, self.controller.state.scores(task.category))
        if not eligible:
            raise ValueError('no existing OpenCode profile satisfies this task policy')
        plan = {'manifest': asdict(task), 'verification_image': cfg.verification_image,
                'eligible': [{'profile': asdict(r.profile), 'reason': r.reason} for r in eligible]}
        policy = plan | {'eligible': sorted((asdict(r.profile) for r in eligible), key=lambda r: r['id'])}
        return task, plan, hashlib.sha256(encoded(policy)).hexdigest()

    def review(self, body: dict) -> dict:
        _, plan, digest = self.policy(body)
        token = secrets.token_urlsafe(32)
        with self.review_lock:
            if len(self.reviews) >= 64:
                del self.reviews[next(iter(self.reviews))]
            self.reviews[token] = digest
        return plan | {'review':token}

    def queue(self, body: dict) -> dict:
        task, _, digest = self.policy(body)
        token = body.get('review')
        with self.review_lock:
            if type(token) is not str or self.reviews.get(token) != digest:
                raise ValueError('review the current task permissions before queueing')
            del self.reviews[token]
        job = self.submit_reviewed(task, body)
        self.pending.add(job)
        return {'job': job}

    def submit_reviewed(self, task: Task, body: dict) -> str:
        return self.controller.submit_task(task)

    def run(self, body: dict) -> dict:
        job = body.get('job')
        if type(job) is not str or job not in self.pending:
            raise ValueError('run requires a job reviewed and queued in this web session')
        if not self.dispatch.acquire(blocking=False):
            raise ValueError('a web job is already executing')

        def execute():
            try:
                self.controller.run_submitted(job)
            except Exception as error:
                self.error = str(error)
            finally:
                self.dispatch.release()

        try:
            if job not in self.pending:
                raise ValueError('this approval was already dispatched')
            rows = self.controller.state.jobs(job)
            if not rows or rows[0]['status'] != 'queued':
                raise ValueError('the controller job is no longer queued')
            self.pending.remove(job)
            self.error = ''
            Thread(target=execute, name='aiwork-operator-job', daemon=False).start()
        except BaseException:
            self.dispatch.release()
            raise
        return {'job': job, 'dispatch': 'accepted'}

    def jobs(self) -> dict:
        return {'jobs': [{k: row[k] for k in ('id','status','created','updated','detail','category')}
                         | {'dispatchable': row['id'] in self.pending and row['status']=='queued'}
                         for row in self.controller.state.jobs()],
                'dispatching': self.dispatch.locked(), 'dispatch_error': self.error}

    def detail(self, job: str) -> dict:
        rows = self.controller.state.jobs(job) if JOB_ID.fullmatch(job) else []
        if not rows:
            raise ValueError('unknown job')
        root = (self.controller.config.state.resolve() / 'runs' / job)
        if not root.is_dir() or root.resolve() != root:
            raise ValueError('run artifacts are unavailable')
        state = self.controller.state.attempts(job)
        attempts = []
        for attempt in sorted(root.glob('attempt-*'))[:32]:
            if not re.fullmatch(r'attempt-\d+', attempt.name) or attempt.resolve() != attempt:
                continue
            verification = []
            for check in sorted(attempt.glob('check-*.json'))[:16]:
                verification.append({'check':check.stem} | fields(attempt, check.name, 'passed',
                    'classification','code','elapsed','passed_cases','total'))
            attempts.append({'attempt':attempt.name,
                'metrics':fields(attempt,'agent-metrics.json','tokens','tool_calls',
                                 'effective_context','successful_public_mcp_checks'),
                'execution':fields(attempt,'execution-receipt.json','resources','cleanup_passed','classification',
                                   'provider_usage'),
                'admission':fields(attempt,'admission.json','gpu','inference','minimum_free_mib','admitted',
                                   'effective_context','reclamation_rechecked'),
                'verification':verification,
                'activity':[{k:row[k] for k in ('tool','call','passed','code','index') if k in row}
                            for row in tail_rows(attempt/'mcp.jsonl')[-24:]],
                'answer':next((row['part']['text'][:2500] for row in reversed(tail_rows(attempt/'agent-live.jsonl'))
                               if row.get('type')=='text' and isinstance(row.get('part'),dict)
                               and isinstance(row['part'].get('text'),str)), ''),
                'analysis':fields(attempt,'analysis.json','binary','header','strings','findings','decompilation'),
                'patch':artifact(attempt,'proposed.patch')})
        return {'job':job,'status':rows[0]['status'],'detail':rows[0]['detail'],'attempts':attempts,
                'records':[{k: row[k] for k in ('n','profile','status','elapsed')} for row in state]}

    def status(self) -> dict:
        cfg = self.controller.config
        return {'profiles':[{'id':p.id,'location':p.location,'model':p.model,'context':p.context,
                             'ready':self.ready.get(p.id),
                             'owned_runtime':bool(p.local_calibration),
                             'residency':ollama_residency(p) if p.engine=='ollama' and p.location=='local' else None}
                            for p in cfg.profiles],
                'memory':memory_snapshot(),'reclamation_enrolled':cfg.idle_ollama is not None} | self.perception.available()

    def probe(self, body: dict) -> dict:
        profile = next((p for p in self.controller.config.profiles if p.id==body.get('profile')), None)
        if profile is None:
            raise ValueError('unknown existing profile')
        with self.controller.planes[profile.location].reserve(profile,2):
            try:
                if profile.location=='a100':
                    with a100_session(self.controller.config,profile,timeout=8) as tunnel:
                        if tunnel is None:
                            Inference(profile).ready()
                else:
                    Inference(profile).ready()
                status = {'ready': True}
            except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
                status = {'ready': False, 'detail': str(error)}
        self.ready[profile.id] = status
        return status

    def reclaim(self, body: dict) -> dict:
        cfg = self.controller.config
        if cfg.idle_ollama is None or body.get('confirm') is not True:
            raise ValueError('memory reclamation requires enrollment and explicit confirmation')
        lane = Profile('operator-reclaim', cfg.idle_ollama.model, cfg.idle_ollama.endpoint, engine='ollama')
        with self.controller.planes['local'].reserve(lane, 2):
            root = cfg.state.resolve() / 'operator-reclamation' / uuid4().hex
            root.mkdir(parents=True)
            before = memory_snapshot()
            reclaim_local_memory(cfg.idle_ollama,root,monotonic()+15,cfg.state/'STOP')
            return {'before':before,'after':memory_snapshot(),'receipt':fields(root,'memory-reclamation.json',
                     'status','detail','model','posts','elapsed_seconds')}

    def post(self, path: str, body: dict) -> dict:
        if path == '/api/review':
            return self.review(body)
        if path == '/api/capture':
            return {'png':base64.b64encode(capture_screen(self.controller.config.state)).decode('ascii')}
        if path == '/api/perception':
            data = body['png']
            if type(data) is not str or len(data)>4*((MAX_IMAGE+2)//3):
                raise ValueError('invalid screenshot payload')
            return self.perception.observe(base64.b64decode(data,validate=True), body.get('location','local'),
                                           body.get('share_remote',False))
        actions = {'/api/queue': self.queue, '/api/run': self.run, '/api/probe': self.probe,
                   '/api/reclaim': self.reclaim}
        if path not in actions:
            raise ValueError('unknown operator action')
        return actions[path](body)

    def get(self, path: str) -> dict | None:
        return None

    assets = ASSETS


def bind(operator: Operator, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(8)

        def log_message(self, *_):
            pass

        def respond(self, raw: bytes, content_type: str, status=200):
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data: blob:; "
                             "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def reply(self, data, status=200):
            self.respond(encoded(data), 'application/json', status)

        def local(self, mutation=False):
            host = f'127.0.0.1:{self.server.server_port}'
            origin = self.headers.get('Origin')
            valid = (self.headers.get_all('Host') == [host] and origin in (None, 'http://' + host)
                     and (not mutation or (origin is not None and secrets.compare_digest(
                         self.headers.get('X-AIWork-Session',''), operator.session))))
            if not valid:
                self.reply({'error':'loopback origin and operator session required'},403)
            return valid

        def do_GET(self):
            if not self.local():
                return
            try:
                if self.path in operator.assets:
                    name, mime = operator.assets[self.path]
                    raw = files('aiwork').joinpath('web_assets', name).read_bytes()
                    self.respond(raw.replace(b'OPERATOR_SESSION_TOKEN', operator.session.encode())
                                 if self.path=='/' else raw, mime)
                elif self.path=='/api/jobs':
                    self.reply(operator.jobs())
                elif self.path.startswith('/api/jobs/'):
                    self.reply(operator.detail(self.path.removeprefix('/api/jobs/')))
                elif self.path=='/api/status':
                    self.reply(operator.status())
                else:
                    data = operator.get(self.path)
                    self.reply(data if data is not None else {'error':'unknown page'},200 if data is not None else 404)
            except (ValueError, OSError, RuntimeError, TypeError, KeyError) as error:
                self.reply({'error':str(error)},400)

        def do_POST(self):
            if not self.local(mutation=True):
                return
            try:
                length = int(self.headers.get('Content-Length','0'))
                limit = 6*1024*1024 if self.path=='/api/perception' else 128*1024
                if (self.headers.get_content_type()!='application/json' or
                    self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length',[]))!=1
                    or not 0<length<=limit):
                    raise ValueError('invalid or oversized JSON request')
                body = json.loads(self.rfile.read(length))
                if type(body) is not dict:
                    raise ValueError('expected a JSON object')
                self.reply(operator.post(self.path, body))
            except (ValueError, OSError, RuntimeError, TypeError, KeyError) as error:
                self.reply({'error':str(error)},400)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def serve(config: Config, project: Path, private: Path | None, perception: PerceptionConfig, port: int) -> None:
    with bind(Operator(config, project, private, perception), port) as server:
        print(f'AI-Workspace operator console: http://127.0.0.1:{server.server_port}/', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
