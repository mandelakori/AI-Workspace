import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from time import monotonic, time
import unittest
from unittest.mock import patch

from aiwork.controller import Controller
from aiwork.mcp import reserve_trial_call
from aiwork.process import environment
from aiwork.process import run
from aiwork.schema import Config
from aiwork.trial_budget import FILE, PHASE_LIMITS, cleanup_containers, create, current, run_phase


class TrialBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.state = self.root / "state"
        self.repo = Path(__file__).resolve().parents[1]

    def command(self, source):
        return [sys.executable, "-c", source]

    def test_healthy_slow_query_uses_remaining_cleanup_allowance(self):
        clock=[0.0];timeouts=[]
        def query(argv,**kwargs):
            timeouts.append(kwargs['timeout'])
            if len(timeouts)==1:
                if kwargs['timeout']<=3:raise subprocess.TimeoutExpired(argv,kwargs['timeout'])
                clock[0]+=5.813
            return subprocess.CompletedProcess(argv,0,'','')
        with (patch('aiwork.trial_budget.executable',return_value='docker'),
              patch('aiwork.trial_budget.monotonic',side_effect=lambda:clock[0]),
              patch('aiwork.trial_budget.subprocess.run',side_effect=query)):
            result=cleanup_containers('aiwork-trial-'+'a'*32,self.repo)
        self.assertTrue(result['passed'])
        self.assertEqual(timeouts[0],10)
        self.assertAlmostEqual(timeouts[1],4.187)

    def test_unknown_ownership_and_timeout_fail_closed_without_removal(self):
        for failure in ['inspect','mismatch','timeout']:
            calls=[]
            def query(argv,**kwargs):
                calls.append(argv)
                if failure=='timeout':raise subprocess.TimeoutExpired(argv,kwargs['timeout'])
                if argv[1]=='ps':return subprocess.CompletedProcess(argv,0,'abcdef123456\n','')
                return subprocess.CompletedProcess(argv,1 if failure=='inspect' else 0,'unrelated-owner','')
            with (patch('aiwork.trial_budget.executable',return_value='docker'),
                  patch('aiwork.trial_budget.subprocess.run',side_effect=query)):
                result=cleanup_containers('aiwork-trial-'+'a'*32,self.repo)
            self.assertFalse(result['passed'],failure)
            self.assertFalse(any('rm' in call for call in calls))

    def test_warm_is_container_free_but_cleanup_failure_still_quarantines_work(self):
        create(self.state,'test','direct')
        with patch('aiwork.trial_budget.cleanup_containers') as cleanup:
            warm=run_phase(self.state,'warm',self.command("print('no inference')"),self.repo)
        cleanup.assert_not_called()
        self.assertIn('not_applicable',warm['cleanup'])
        with patch('aiwork.trial_budget.cleanup_containers',return_value={'passed':False,'error':'fixture failure'}):
            run_phase(self.state,'work',self.command('pass'),self.repo)
        self.assertTrue(json.loads((self.state/FILE).read_bytes())['quarantined'])
        with self.assertRaisesRegex(ValueError,'quarantined'):
            run_phase(self.state,'grade',self.command('pass'),self.repo)

    def test_warm_cannot_launch_verification_and_interrupted_inference_quarantines(self):
        from aiwork.verify import invoke
        from aiwork.schema import Check
        from aiwork.trial_budget import inference_interrupted
        with patch('aiwork.trial_budget.current',return_value={'phase':'warm'}),patch('aiwork.verify.run') as launch:
            with self.assertRaisesRegex(ValueError,'warm phase cannot launch'):
                invoke(Check(('python','-V')),self.root,self.root/'home','fixture-image')
        launch.assert_not_called()
        create(self.state,'test','direct')
        with patch.dict(os.environ,{'AIWORK_TRIAL_BUDGET':str(self.state/FILE)}):inference_interrupted()
        self.assertTrue(json.loads((self.state/FILE).read_bytes())['quarantined'])
        with self.assertRaisesRegex(ValueError,'quarantined'):
            run_phase(self.state,'warm',self.command('pass'),self.repo)

    def make_warm(self, work, grade):
        create(self.state,"test","direct",{"warm":3,"work":work,"grade":grade})
        result=run_phase(self.state,"warm",self.command("print('neutral fixture warm-up; no model')"),self.repo,containers=False)
        self.assertEqual(result["code"],0)

    def test_total_reservations_and_no_restart_even_after_success(self):
        self.assertEqual(sum(PHASE_LIMITS.values()), 240)
        self.make_warm(3,3)
        first = run_phase(self.state,"work",self.command("print('planning inference tools public verification')"),self.repo,containers=False)
        self.assertEqual(first["code"],0)
        with self.assertRaisesRegex(ValueError,"cannot be restarted"):
            run_phase(self.state,"work",self.command("raise Exception('must not run')"),self.repo,containers=False)
        grade = run_phase(self.state,"grade",self.command("print('independent verification')"),self.repo,containers=False)
        self.assertEqual(grade["code"],0)
        with self.assertRaisesRegex(ValueError,"cannot be restarted"):
            run_phase(self.state,"grade",self.command("pass"),self.repo,containers=False)
        with self.assertRaisesRegex(ValueError,"cannot be resumed"):
            Controller(Config(self.state)).resume("any-job",interrupted=True,reset=True)

    def test_one_cumulative_watchdog_stops_later_phases_and_refuses_resume(self):
        self.make_warm(.9,1)
        source = "import time\nfor phase in ['planning','inference','tool','verification']:\n print(phase,flush=True)\n time.sleep(.35)\n"
        outcome = run_phase(self.state,"work",self.command(source),self.repo,containers=False)
        self.assertTrue(outcome["timed_out"])
        self.assertIn("planning",outcome["stdout"])
        self.assertNotIn("verification",outcome["stdout"])
        with self.assertRaisesRegex(ValueError,"cannot be restarted"):
            run_phase(self.state,"work",self.command("pass"),self.repo,containers=False)
        with self.assertRaisesRegex(ValueError,"quarantined"):
            run_phase(self.state,"grade",self.command("pass"),self.repo,containers=False)

    def test_global_session_and_planner_quotas_and_grading_cannot_infer(self):
        self.make_warm(5,5)
        source = """from pathlib import Path
import os
from aiwork.trial_budget import claim
state=Path(os.environ['AIWORK_TRIAL_BUDGET']).parent
for kind,limit in [('worker',2),('planner',1)]:
 for i in range(limit): claim(kind,state)
 try: claim(kind,state)
 except ValueError: print(kind+'-exhausted')
 else: raise AssertionError('quota bypass')
"""
        outcome=run_phase(self.state,"work",self.command(source),self.repo,containers=False)
        self.assertEqual(outcome["code"],0,outcome["stderr"])
        self.assertIn("worker-exhausted",outcome["stdout"])
        grade=run_phase(self.state,"grade",self.command("from pathlib import Path; import os; from aiwork.trial_budget import claim; claim('worker',Path(os.environ['AIWORK_TRIAL_BUDGET']).parent)"),self.repo,containers=False)
        self.assertNotEqual(grade["code"],0)
        self.assertIn("cannot dispatch",grade["stderr"])

    def test_crashed_reserved_phase_is_not_refunded_or_reinitialized(self):
        import hashlib
        create(self.state,"test","direct")
        path=self.state/FILE;data=json.loads(path.read_bytes());data['active']='work'
        token='expired-fixture-lease'
        data['phases']['work'].update(status='RUNNING',deadline_utc=time()-1,deadline_monotonic=monotonic()-1,
                                     token_sha256=hashlib.sha256(token.encode()).hexdigest())
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):current(self.state)
        with patch.dict(os.environ,{'AIWORK_TRIAL_BUDGET':str(path),'AIWORK_TRIAL_TOKEN':token}):
            with self.assertRaisesRegex(ValueError,'exhausted'):current(self.state)
        with self.assertRaises(ValueError):run_phase(self.state,"work",self.command("pass"),self.repo,containers=False)
        with self.assertRaises(FileExistsError):create(self.state,"test","direct")

    def test_interrupted_launch_is_consumed_and_quarantines_trial(self):
        create(self.state,'test','direct')
        with patch('aiwork.trial_budget.run',side_effect=OSError('fixture interrupted')):
            with self.assertRaises(OSError):
                run_phase(self.state,'warm',self.command('pass'),self.repo,containers=False)
        data=json.loads((self.state/FILE).read_bytes())
        self.assertTrue(data['quarantined'])
        self.assertEqual(data['phases']['warm']['status'],'FAILED')

    def test_lease_not_exported_to_harness_and_tool_reconnect_does_not_reset(self):
        with patch.dict(os.environ,{"AIWORK_TRIAL_BUDGET":"private-host-path","AIWORK_TRIAL_TOKEN":"PRIVATE-CANARY"}):
            env=environment(self.root/'home')
        self.assertNotIn("AIWORK_TRIAL_TOKEN",env)
        self.assertNotIn("AIWORK_TRIAL_BUDGET",env)
        self.assertEqual(env["AIWORK_TRIAL_GROUP_MEMBER"],"1")
        spec=self.root/'tool.json'
        for i in range(16):self.assertEqual(reserve_trial_call(spec,16),i+1)
        with self.assertRaisesRegex(ValueError,"exhausted"):reserve_trial_call(spec,16)

    def test_live_trace_is_bounded_and_survives_owning_controller_timeout(self):
        path=self.root/'bounded.jsonl'
        result=run(self.command("print('x'*200)"),self.repo,3,os.environ.copy(),output_limit=80,stdout_path=path)
        self.assertTrue(result.truncated)
        self.assertEqual(path.read_bytes(),b'x'*80)
        self.make_warm(1,1)
        live=self.root/'live.jsonl'
        nested=("from aiwork.process import run,environment; from pathlib import Path; import sys; "
                f"run([sys.executable,'-c',\"import time;print('MODEL-START',flush=True);time.sleep(10)\"],"
                f"Path({str(self.repo)!r}),9,environment(Path({str(self.root/'home')!r})),stdout_path=Path({str(live)!r}))")
        outcome=run_phase(self.state,'work',self.command(nested),self.repo,containers=False)
        self.assertTrue(outcome['timed_out'])
        self.assertIn('MODEL-START',live.read_text())

    @unittest.skipUnless(os.getenv("AIWORK_TEST_DOCKER_IMAGE"),"set AIWORK_TEST_DOCKER_IMAGE")
    def test_docker_watchdog_and_cleanup_preserve_unrelated_test_container(self):
        image=os.environ['AIWORK_TEST_DOCKER_IMAGE']
        other=subprocess.run(['docker','run','-d','--rm','--pull=never','--network=none',image,'python','-c','import time;time.sleep(40)'],capture_output=True,text=True,check=True).stdout.strip()
        try:
            self.make_warm(3,1)
            source=("from aiwork.verify import invoke; from aiwork.schema import Check; from pathlib import Path; "
                    f"invoke(Check(('python','-c','import time;time.sleep(30)'),timeout=30),Path({str(self.root)!r}),Path({str(self.root/'home')!r}),{image!r})")
            outcome=run_phase(self.state,"work",self.command(source),self.repo,containers=True)
            self.assertTrue(outcome["timed_out"] or outcome["code"]!=0)
            self.assertTrue(outcome["cleanup"]["passed"],outcome)
            alive=subprocess.run(['docker','inspect','--format','{{.State.Running}}',other],capture_output=True,text=True,check=True)
            self.assertEqual(alive.stdout.strip(),'true')
            budget=json.loads((self.state/FILE).read_bytes());label=budget['phases']['work']['label']
            left=subprocess.run(['docker','ps','-aq','--filter','label=aiwork.trial='+label],capture_output=True,text=True,check=True)
            self.assertEqual(left.stdout.strip(),'')
        finally:
            subprocess.run(['docker','rm','-f',other],capture_output=True,check=False)
