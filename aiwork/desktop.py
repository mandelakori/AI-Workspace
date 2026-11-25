"""Windows launcher and conversational views over the existing loopback operator API."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Lock, Thread
from time import monotonic, sleep
from uuid import uuid4
import webbrowser

from .controller import screen_profile, write_json
from .http import request
from .lock import file_lock
from .perception import PerceptionConfig
from .process import executable, run
from .schema import Check, Config, Task
from .verify import runner_status
from .web import Operator, bind, encoded
from .workspace import LANGUAGES, ignore, linked


CHECKS = {
    'python': ('Python tests', ['{python}','-m','unittest','discover']),
    'node': ('Node tests', ['node','--test']),
    'syntax': ('Source syntax only', ['{python}','-c',
        'import pathlib,py_compile,subprocess; p=pathlib.Path("."); '
        'py=list(p.rglob("*.py")); js=list(p.rglob("*.js")); c=list(p.rglob("*.c")); '
        'assert py or js or c, "No supported syntax-check sources. Choose a project command."; '
        '[py_compile.compile(str(f),cfile="/tmp/source.pyc",doraise=True) for f in py]; '
        '[subprocess.run(["node","--check",str(f)],check=True) for f in js]; '
        '[subprocess.run(["gcc","-fsyntax-only",str(f)],check=True) for f in c]']),
}


def defaults(project: Path) -> dict:
    entries = []
    for child in sorted(project.iterdir(),key=lambda p:p.name.casefold())[:512]:
        name = child.name
        if (name.startswith('.') or ignore(name) or linked(child) or name.casefold() in
                {'dist','build','vendor','target','coverage','docs','venv','__pypackages__'}):
            continue
        if child.is_dir() or (child.is_file() and child.stat().st_size <= 2*1024*1024
                and (child.suffix.casefold() in LANGUAGES or name in
                     {'README.md','LICENSE','requirements.txt','pyproject.toml','package.json','setup.cfg','Makefile'})):
            entries.append(child)
    reads = [p.name for p in entries[:128]]
    writes = [p.name for p in entries if (p.is_dir() and p.name.casefold() not in
                {'test','tests','fixtures','examples','scripts','config','benchmarks','assets','data'} and
                (p.name in {'src','lib','app','aiwork','include','components','packages'} or
                 next(p.glob('*.py'),None) is not None)) or p.suffix.casefold() in LANGUAGES][:64]
    if not reads or not writes:
        raise ValueError('No source scope was found. Pick a folder containing source files or a src directory.')
    names = set(reads)
    check = 'python' if {'tests','test'} & names and ('pyproject.toml' in names or
              any(p.suffix=='.py' for p in entries)) else 'node' if 'package.json' in names else 'syntax'
    argv = CHECKS[check][1]
    if check=='python':
        directory = 'tests' if 'tests' in names else 'test'
        if not any(project.joinpath(directory).glob('test*.py')):
            check, argv = 'syntax', CHECKS['syntax'][1]
        else:
            argv = ['{python}','-c',
                    'import sys, unittest; sys.path.insert(0,"src"); suite=unittest.defaultTestLoader.discover(sys.argv[1]); '
                    'assert suite.countTestCases(), "No unittest cases discovered"; '
                    'sys.exit(not unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful())', directory]
    return {'inputs':reads,'write_roots':writes,'recipe':check,'argv':argv}


def choose_path(directory: bool) -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost',True)
    try:
        return (filedialog.askdirectory(parent=root,mustexist=True,title='Choose an AI-Workspace project') if directory
                else filedialog.askopenfilename(parent=root,title='Choose an authorized PE or ELF binary'))
    finally:
        root.destroy()


class Desktop(Operator):
    assets = {'/':('desktop.html','text/html'),'/desk.js':('desktop.js','text/javascript'),
              '/desk.css':('desktop.css','text/css')}

    def __init__(self, config: Config, project: Path, perception: PerceptionConfig):
        super().__init__(config,project,None,perception)
        self.dialog = Lock()
        self.runtime = {'ready':False,'detail':'Checking Docker verifier…'}
        self.runtime_lock = Lock()
        with self.controller.state.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS desktop_projects (
                    id TEXT PRIMARY KEY, path TEXT UNIQUE NOT NULL
                );
                CREATE TABLE IF NOT EXISTS desktop_threads (
                    id TEXT PRIMARY KEY, project TEXT NOT NULL, title TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS desktop_messages (
                    thread TEXT NOT NULL, prompt TEXT NOT NULL, job TEXT NOT NULL
                );
            """)
        self.register(project)

    def register(self, path: Path) -> str:
        path = path.resolve(strict=True)
        if not path.is_dir() or path==Path(path.anchor):
            raise ValueError('Select a project folder rather than an entire drive.')
        with self.controller.state.db() as db:
            db.execute('INSERT OR IGNORE INTO desktop_projects VALUES (?,?)',(uuid4().hex,str(path)))
            return db.execute('SELECT id FROM desktop_projects WHERE path=?',(str(path),)).fetchone()[0]

    def thread(self, identifier: str):
        with self.controller.state.db() as db:
            row = db.execute("""SELECT t.*, p.path FROM desktop_threads t JOIN desktop_projects p
                                ON t.project=p.id WHERE t.id=?""",(identifier,)).fetchone()
        if row is None:
            raise ValueError('Select a conversation.')
        return row

    def workspace(self, body: dict) -> Path:
        return Path(self.thread(body.get('thread',''))['path']).resolve(strict=True)

    def attempts(self, body: dict) -> int:
        return 2 if body.get('location')=='auto' and len(self.controller.config.profiles)>1 else 1

    def message(self, thread: str, prompt: str, job: str):
        with self.controller.state.db() as db:
            db.execute('INSERT INTO desktop_messages VALUES (?,?,?)',(thread,prompt,job))
            db.execute('UPDATE desktop_threads SET title=? WHERE id=? AND title=?',
                       (' '.join(prompt.split())[:65],thread,'New conversation'))

    def verify_runtime(self, startup=False):
        if not self.runtime_lock.acquire(blocking=False):
            return
        try:
            cfg = self.controller.config
            status = runner_status(cfg.state,cfg.verification_image)
            if startup and not status['available'] and (docker:=executable('docker')):
                self.runtime = {'ready':False,'detail':'Starting the installed Docker verifier…'}
                run([docker,'desktop','start','--detach','--timeout','45'],cfg.state,10,os.environ.copy())
                until = monotonic()+45
                while monotonic()<until and not status['available']:
                    sleep(2)
                    status = runner_status(cfg.state,cfg.verification_image)
            ok = bool(status.get('available') and status.get('image_present'))
            self.runtime = {'ready':ok,'detail':'Offline verifier ready' if ok else
                            'The installed Docker Linux engine or pinned verification image is unavailable.'}
        except (OSError, RuntimeError, ValueError) as error:
            self.runtime = {'ready':False,'detail':str(error)}
        finally:
            self.runtime_lock.release()

    def draft(self, body: dict) -> dict:
        thread = body['thread']
        prompt = body['prompt'].strip()
        if not prompt or len(prompt)>6000:
            raise ValueError('Enter an objective of up to 6,000 characters.')
        location, profile = 'auto', body.get('model','')
        if profile:
            selected = next((p for p in self.controller.config.profiles if p.id==profile),None)
            if selected is None:
                raise ValueError('Select an installed model profile.')
            location = selected.location
        screen = body.get('screen')
        if screen is not None and not (profile and screen_profile(selected)):
            raise ValueError('Choose the owned laptop model to attach local screen observations.')
        project = self.workspace(body)
        proposal = defaults(project)
        with self.controller.state.db() as db:
            previous = list(db.execute('SELECT prompt,job FROM desktop_messages WHERE thread=? ORDER BY rowid DESC LIMIT 3',
                                       (thread,)))
        context = []
        for row in reversed(previous):
            jobs = self.controller.state.jobs(row['job'])
            if jobs:
                context.append(f"{row['prompt'][:300]} ({jobs[0]['status']})")
        if context:
            prompt_with_context = ('Earlier requests in this conversation, for context only. Work from the selected project snapshot.\n'
                                   + '\n'.join(context) + '\n\nCurrent request:\n' + prompt)
        else:
            prompt_with_context = prompt
        check = {'argv':proposal['argv'],'timeout':120}
        # Start with the measured 7,440-token local fixture envelope, then
        # reserve one token per additional UTF-8 byte in the objective or one screen page.
        input_budget = 7440+max(0,len(prompt_with_context.encode('utf-8'))-256)
        if screen is not None:
            input_budget += min(8192,len(encoded(screen)))
        spec = {'thread':thread,'prompt':prompt,'objective':prompt_with_context,'location':location,'profile':profile,
                'inputs':proposal['inputs'],'write_roots':proposal['write_roots'],'deliverables':[],
                'commands':[check],'checks':[check],'timeout':600,'complexity':2,'context_input_tokens':input_budget}
        if screen is not None:
            spec['screen'] = screen
        return {'draft':spec,'recipe':proposal['recipe']}

    def policy(self, body: dict):
        task, plan, fingerprint = super().policy(body)
        if screen := body.get('screen'):
            plan['screen_sha256'] = hashlib.sha256(encoded(screen)).hexdigest()
        binding = encoded([fingerprint,body['thread'],body['prompt'],plan.get('screen_sha256')])
        return task, plan, hashlib.sha256(binding).hexdigest()

    def submit_reviewed(self, task: Task, body: dict) -> str:
        if not self.runtime['ready']:
            self.verify_runtime()
            if not self.runtime['ready']:
                raise ValueError(self.runtime['detail'])
        if observation := body.get('screen'):
            raw = encoded(observation)
            with TemporaryDirectory(prefix='aiwork-screen-') as directory:
                file = Path(directory)/'screen.json'
                file.write_bytes(raw)
                job = self.controller.submit_task(task,screen=(file,hashlib.sha256(raw).hexdigest()))
        else:
            job = self.controller.submit_task(task)
        self.message(body['thread'],body['prompt'],job)
        return job

    def native(self, body: dict) -> dict:
        thread = body['thread']
        self.thread(thread)
        with self.dialog:
            answer = choose_path(False)
        if not answer:
            return {}
        source = Path(answer).resolve(strict=True)
        name = body.get('specialist','binary')
        if name not in {'binary', *self.controller.config.specialists}:
            raise ValueError('Native analyzer is unavailable.')
        task = Task(f'Inspect {source.name}',source.parent,'direct','operator-native',(source.name,),(),
                    (Check(('{python}','-V')),),location='local',specialist=name,timeout=150)
        job = self.controller.submit_task(task,trusted=name!='binary')
        self.message(thread,task.objective,job)
        self.pending.add(job)
        return {'job':job}

    def get(self, path: str):
        if path != '/api/desktop':
            return None
        with self.controller.state.db() as db:
            return {'projects':[dict(r) for r in db.execute('SELECT * FROM desktop_projects ORDER BY rowid DESC')],
                    'threads':[dict(r) for r in db.execute('SELECT * FROM desktop_threads ORDER BY rowid DESC')],
                    'messages':[dict(r) for r in db.execute(
                        'SELECT rowid AS id,* FROM desktop_messages ORDER BY rowid DESC LIMIT 500')],
                    'models':[{'id':p.id,'name':p.model.split('/')[-1].removesuffix('.gguf'),
                               'location':p.location} for p in self.controller.config.profiles],
                    'native':['binary',*self.controller.config.specialists],
                    'runtime':self.runtime,'checks':{key:label for key,(label,_) in CHECKS.items()}
                    } | self.perception.available()

    def post(self, path: str, body: dict) -> dict:
        if path=='/api/pick':
            with self.dialog:
                selected = choose_path(True)
            return {'project':self.register(Path(selected))} if selected else {}
        if path=='/api/thread':
            identifier = uuid4().hex
            with self.controller.state.db() as db:
                if db.execute('SELECT 1 FROM desktop_projects WHERE id=?',(body['project'],)).fetchone() is None:
                    raise ValueError('Select a project.')
                db.execute('INSERT INTO desktop_threads VALUES (?,?,?)',(identifier,body['project'],'New conversation'))
            return {'thread':identifier}
        if path=='/api/draft':
            return self.draft(body)
        if path=='/api/native':
            return self.native(body)
        if path=='/api/review':
            body = self.review_commands(body)
        if path=='/api/queue':
            body = self.review_commands(body)
        return super().post(path,body)

    @staticmethod
    def review_commands(body: dict) -> dict:
        if 'command' not in body:
            return body
        argv = shlex.split(body['command'])
        if not argv:
            raise ValueError('Enter a verification command.')
        checks = [{'argv':argv,'timeout':120}]
        return body|{'commands':checks,'checks':checks}


def open_window(url: str, root: Path) -> None:
    edge = Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'
    if edge.is_file():
        subprocess.Popen([str(edge),'--app='+url,'--user-data-dir='+str(root/'browser'),
                          '--no-first-run','--no-default-browser-check'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    else:
        webbrowser.open(url)


def installed_specialists(config: Config) -> dict:
    if 'ghidra' in config.specialists:
        return config.specialists
    roots = []
    if location := os.environ.get('GHIDRA_INSTALL_DIR'):
        roots.append(Path(location))
    downloads = Path.home()/'Downloads'
    roots += sorted(downloads.glob('ghidra_*/ghidra_*'), reverse=True)
    for root in roots:
        headless = root/'support'/('analyzeHeadless.bat' if os.name=='nt' else 'analyzeHeadless')
        if headless.is_file():
            java = executable('java')
            policy = {'headless':str(headless.resolve())}
            if java:
                policy['java_home'] = str(Path(java).resolve().parents[1])
            return config.specialists|{'ghidra':policy}
    return config.specialists


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    root = repository/'.aiwork'/'desktop'
    root.mkdir(parents=True,exist_ok=True)
    config = next((p for p in (repository/'config/rc.local.toml',repository/'config/rc.example.toml') if p.is_file()))
    port = root/'connection.json'
    try:
        with file_lock(root/'console.lock'):
            perception_path = repository/'.aiwork/omni/perception.toml'
            perception = PerceptionConfig.load(perception_path if perception_path.is_file() else None)
            loaded = Config.load(config)
            settings = replace(loaded,state=root/'state',execution_state=repository/'.aiwork',
                               specialists=installed_specialists(loaded))
            desk = Desktop(settings,repository,perception)
            with bind(desk,0) as server:
                url = f'http://127.0.0.1:{server.server_port}'
                write_json(port,{'url':url})
                Thread(target=desk.verify_runtime,args=(True,),daemon=True).start()
                open_window(url,root)
                server.serve_forever()
    except TimeoutError:
        for _ in range(20):
            try:
                url = json.loads(port.read_bytes())['url']
                request(url+'/api/desktop',timeout=1)
                open_window(url,root)
                return
            except (OSError,ValueError,RuntimeError,KeyError):
                sleep(.25)
        raise RuntimeError('An existing AI-Workspace desktop console did not respond.')


if __name__ == '__main__':
    try:
        main()
    except Exception as err:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,str(err),'AI-Workspace startup',0x10)
        sys.exit(1)
