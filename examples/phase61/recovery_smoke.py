"""One operator-authorized local fixture session; never starts an HTTPX campaign."""
from dataclasses import replace
import json
import hashlib
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from aiwork.controller import Controller, write_json
from aiwork.schema import Check, Config, Task
from aiwork.trial_budget import create, run_phase
from aiwork.workspace import inventory


def worker(root: Path) -> None:
    cfg=Config.load(root/'local.toml')
    cfg=replace(cfg,state=root/'controller')
    profile,=cfg.profiles
    if profile.location!='local' or profile.managed:
        raise ValueError('fixture permits the existing unmanaged local profile only')
    command=Check(('python','-m','unittest','discover','-s','tests','-v'),timeout=20)
    task=Task(
        'Implement Duration.to_seconds(amount, unit) for seconds, minutes and hours. '
        'Preserve fractional amounts; unknown units must raise ValueError. '
        'Keep public tests read-only. Inspect relevant symbols, edit the implementation '
        'and run the approved public check before finishing.',
        root/'input','agent','navigation-smoke',(),('duration.py',),(command,),
        profile=profile.id,location='local',timeout=120,attempts=1,mode='engineering',
        write_roots=('duration.py',),commands=(command,),baseline_check=True,
        min_context=8192,agent_role='implementation')
    task.validate()
    write_json(root/'task-receipt.json',{'objective':task.objective,'input_inventory':inventory(task.workspace),
        'write_roots':task.write_roots,'command':command.argv,'timeout':120,'attempts':1,
        'controller_implementation_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((Path(__file__).resolve().parents[2]/'aiwork').glob('*.py'))},
        'operator_mid_run_guidance':False,'classification':'Self-authored fixture, not unfamiliar-repository acceptance'})
    controller=Controller(cfg)
    job=controller.submit_task(task)
    write_json(root/'submitted.json',{'job':job})
    write_json(root/'result.json',controller.run_submitted(job))


def main():
    root=Path(sys.argv[1]).resolve()
    if len(sys.argv)>2 and sys.argv[2]=='_worker':
        worker(root);return
    # Preparing a new root is irreversible for this script: never overwrite/resume it.
    root.mkdir(parents=True,exist_ok=False)
    (root/'local.toml').write_bytes(Path(sys.argv[2]).read_bytes())
    work=root/'input';(work/'tests').mkdir(parents=True)
    (work/'duration.py').write_text('# Public navigation fixture.\n'*80+
        'class Duration:\n    @staticmethod\n    def to_seconds(amount, unit):\n        return amount\n',encoding='utf-8')
    (work/'README.md').write_text('Duration conversion public fixture. Modify duration.py only.\n',encoding='utf-8')
    (work/'tests/test_duration.py').write_text('''import unittest
from duration import Duration

class PublicDuration(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(Duration.to_seconds(2.5, 'seconds'), 2.5)
    def test_minutes(self):
        self.assertEqual(Duration.to_seconds(1.5, 'minutes'), 90)
    def test_hours(self):
        self.assertEqual(Duration.to_seconds(2, 'hours'), 7200)
    def test_unknown(self):
        with self.assertRaises(ValueError):
            Duration.to_seconds(3, 'fortnights')

if __name__ == '__main__': unittest.main()
''',encoding='utf-8')
    state=root/'controller'
    create(state,'explicitly-authorized-single-recovery-fixture','fixture',{'warm':3,'work':120,'grade':3})
    warm=run_phase(state,'warm',[sys.executable,'-c',"print('fixture preflight; no model warm-up request')"],Path(__file__).resolve().parents[2])
    write_json(root/'preflight-process.json',warm)
    if warm['code'] or warm['timed_out'] or not warm['cleanup']['passed']:return
    result=run_phase(state,'work',[sys.executable,str(Path(__file__).resolve()),str(root),'_worker'],Path(__file__).resolve().parents[2])
    write_json(root/'work-process.json',result)
    print(json.dumps({'root':str(root),'work_process':result},indent=2))


if __name__=='__main__':main()
