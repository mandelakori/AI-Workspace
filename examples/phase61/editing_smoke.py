"""One local fixture: deliberately stale first edit, then autonomous recovery."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from aiwork.controller import Controller, write_json
from aiwork.schema import Check, Config, Task
from aiwork.trial_budget import create, run_phase
from aiwork.workspace import inventory


def worker(root: Path):
    cfg=replace(Config.load(root/'local.toml'),state=root/'controller')
    profile,=cfg.profiles
    if profile.location!='local' or profile.managed:raise ValueError('existing local model only')
    check=Check(('python','-m','unittest','discover','-s','tests','-v'),timeout=20)
    objective=(
        'Implement Distance.metres(value, unit) for m, cm and km, preserving fractional values; '
        'unknown units raise ValueError. Only change distance.py; public tests stay read-only. '
        'This fixture includes an intentional edit-rejection drill: your FIRST source-edit request '
        'must be a replacement in distance.py using expected_sha256='+('0'*64)+'. '
        'That deliberately stale fingerprint must be rejected without changing the file. '
        'Then inspect the current source at the suggested region, use its real SHA-256, '
        'apply your own correction with a short unique exact anchor, and run the public check. '
        'Use only tools actually present in the tool catalog. Do not finish before testing.')
    task=Task(objective,root/'input','agent','edit-recovery-fixture',(),('distance.py',),(check,),
        profile=profile.id,location='local',timeout=150,attempts=1,mode='engineering',
        write_roots=('distance.py',),commands=(check,),baseline_check=True,min_context=8192,
        agent_role='implementation')
    task.validate()
    write_json(root/'task-receipt.json',{'objective':objective,'input_inventory':inventory(task.workspace),
        'write_roots':task.write_roots,'command':check.argv,'timeout':150,'attempts':1,
        'controller_implementation_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((Path(__file__).resolve().parents[2]/'aiwork').glob('*.py'))},
        'initial_protocol_requests_intentional_stale_hash':True,'operator_mid_run_guidance':False,
        'classification':'Self-authored fault-injection fixture, not unfamiliar-repository acceptance'})
    controller=Controller(cfg);job=controller.submit_task(task)
    write_json(root/'submitted.json',{'job':job})
    write_json(root/'result.json',controller.run_submitted(job))


def main():
    root=Path(sys.argv[1]).resolve()
    if len(sys.argv)>2 and sys.argv[2]=='_worker':worker(root);return
    root.mkdir(parents=True,exist_ok=False)
    (root/'local.toml').write_bytes(Path(sys.argv[2]).read_bytes())
    work=root/'input';(work/'tests').mkdir(parents=True)
    (work/'distance.py').write_text('''class Distance:
    @staticmethod
    def metres(value, unit):
        return (
            value
        )
''',encoding='utf-8',newline='\n')
    (work/'tests/test_distance.py').write_text('''import unittest
from distance import Distance

class PublicDistance(unittest.TestCase):
    def test_metres(self):self.assertEqual(Distance.metres(2.5, 'm'), 2.5)
    def test_centimetres(self):self.assertEqual(Distance.metres(250, 'cm'), 2.5)
    def test_kilometres(self):self.assertEqual(Distance.metres(1.25, 'km'), 1250)
    def test_unknown(self):
        with self.assertRaises(ValueError):Distance.metres(3, 'feet')
''',encoding='utf-8',newline='\n')
    state=root/'controller'
    create(state,'user-authorized-single-edit-recovery-fixture','fixture',{'warm':3,'work':150,'grade':3},
           quotas={'sessions':1,'planner_requests':0})
    cwd=Path(__file__).resolve().parents[2]
    warm=run_phase(state,'warm',[sys.executable,'-c',"print('fixture preflight, no inference')"],cwd)
    write_json(root/'preflight-process.json',warm)
    if warm['code'] or warm['timed_out'] or not warm['cleanup']['passed']:return
    result=run_phase(state,'work',[sys.executable,str(Path(__file__).resolve()),str(root),'_worker'],cwd)
    write_json(root/'work-process.json',result)
    print(json.dumps({'root':str(root),'work_process':result},indent=2))


if __name__=='__main__':main()
