"""Isolated routing/admission and scheduler checks with no live model dispatch."""
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic
import unittest
from unittest.mock import patch

from aiwork.controller import Controller, write_json
from aiwork.local_runtime import MIB, admit_context
from aiwork.router import Plane, routes
from aiwork.schema import Check, Config, Task


CONFIG = Path(__file__).resolve().parents[1] / 'config/phase3.example.toml'
CHECK = Check(('{python}', '-c', 'from units import value; assert value == 2'))


class RoutingValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.work = self.root / 'source'
        self.work.mkdir()
        (self.work / 'units.py').write_bytes(b'value = 0\n')
        self.local, self.remote, _ = Config.load(CONFIG).profiles
        self.locks = self.root / 'shared-lanes'
        self.controller = Controller(Config(self.root / 'state', (self.local, self.remote),
                                            execution_state=self.locks))
        self.task = Task('Set the approved fixture value to 2.', self.work, 'agent', 'routing-fixture',
                         ('units.py',), ('units.py',), (CHECK,), mode='engineering', write_roots=('units.py',))

    def order(self, task, scores=None):
        return [row.profile.id for row in routes(task, (self.local, self.remote), scores or {})]

    def test_ranking_tie_history_and_overrides(self):
        self.assertEqual(self.order(self.task), [self.local.id, self.remote.id])
        complex_task = replace(self.task, complexity=4)
        self.assertEqual(self.order(complex_task), [self.remote.id, self.local.id])
        # Historical quality is stronger than the preference for an A100.
        history = {self.local.id: (3, 4, 40), self.remote.id: (0, 2, 1)}
        self.assertEqual(self.order(complex_task, history), [self.local.id, self.remote.id])
        self.assertEqual(self.order(replace(complex_task, preferred_profile=self.remote.id), history)[0], self.remote.id)
        self.assertEqual(self.order(replace(complex_task, profile=self.remote.id), history), [self.remote.id])
        self.assertEqual(self.order(replace(complex_task, location='local')), [self.local.id])
        self.assertEqual(self.order(replace(complex_task, min_context=self.local.context + 1)), [self.remote.id])
        self.assertEqual(self.order(replace(complex_task, location='local', profile=self.remote.id)), [])
        self.assertEqual(self.order(replace(complex_task, profile='unconfigured')), [])
        with self.assertRaisesRegex(ValueError, 'configured profile'):
            self.controller.submit_task(self.task, True, profile_id='unconfigured')

    def test_history_is_category_local_and_excludes_blocked_attempts(self):
        state = self.controller.state
        job = self.controller.submit_task(self.task, True)
        for number, status, elapsed in ((1, 'verified', 12), (2, 'failed', 3), (3, 'partial', 9), (4, 'blocked', 1)):
            state.record(job, number, self.local.id, {'status': status, 'elapsed': elapsed})
        separate = self.controller.submit_task(replace(self.task, category='another-category'), True)
        state.record(separate, 1, self.remote.id, {'status': 'verified', 'elapsed': 1})
        self.assertEqual(state.scores(self.task.category), {self.local.id: (1, 3, 12)})

    def test_a100_unavailable_falls_back_only_within_explicit_eligibility(self):
        runners = []

        @contextmanager
        def connection(*args, **kwargs):
            raise TimeoutError('inert A100 readiness expired')
            yield

        def local_execute(profile, task, work, attempt, *args, **kwargs):
            runners.append(profile.id)
            (work / 'units.py').write_bytes(b'value = 2\n')
            from aiwork.process import Result
            return Result(0, .02, '', '', False, False)

        with (patch('aiwork.remote.a100_session', side_effect=connection) as tunnel,
              patch('aiwork.controller.opencode_path', return_value='inert'),
              patch('aiwork.controller.Inference.ready'), patch('aiwork.controller.ollama_residency', return_value=None),
              patch.object(self.controller, 'gpu_sample', return_value=[]),
              patch('aiwork.controller.OpenCode.execute', side_effect=local_execute)):
            task = replace(self.task, attempts=2, complexity=4)
            job = self.controller.submit_task(task, True)
            completed = self.controller.run_submitted(job)
            self.assertEqual(completed['status'], 'verified', completed)
            self.assertEqual([(a['profile'], a['status']) for a in self.controller.state.attempts(job)],
                             [(self.remote.id, 'blocked'), (self.local.id, 'verified')])
            self.assertEqual(runners, [self.local.id])
            forced = self.controller.submit_task(replace(task, attempts=1), True, profile_id=self.remote.id)
            result = self.controller.run_submitted(forced)
            self.assertEqual(result['status'], 'blocked')
            self.assertIn('readiness expired', result['detail'])
            self.assertEqual(runners, [self.local.id])
            self.assertEqual(tunnel.call_count, 2)
            with self.controller.planes['a100'].reserve(self.remote, .3):
                pass  # Both failed A100 reservations released their selected lane.

    def test_explicit_vram_requirement_fails_closed_without_telemetry(self):
        profile = replace(self.local, memory_mib=2048)
        ctl = Controller(Config(self.root / 'admission', (profile,), execution_state=self.locks))
        task = replace(self.task, profile=profile.id, attempts=1)
        with (patch('aiwork.controller.opencode_path', return_value='inert'),
              patch('aiwork.controller.Inference.ready'),
              patch('aiwork.controller.ollama_residency', return_value={'resident':False}),
              patch('aiwork.controller.OpenCode.execute') as worker):
            for readings, reason in (([{'free_mib': 1024}], 'GPU free memory below'), ([], 'GPU telemetry unavailable')):
                with self.subTest(readings=readings), patch.object(ctl, 'gpu_sample', return_value=readings):
                    result = ctl.run_submitted(ctl.submit_task(task, True))
                    self.assertEqual(result['status'], 'blocked')
                    self.assertIn(reason, result['detail'])
                    admission = json.loads((Path(result['artifacts'])/'attempt-001/admission.json').read_bytes())
                    self.assertFalse(admission['admitted'])
            worker.assert_not_called()

    def test_resident_context_can_disqualify_an_eligible_local_profile(self):
        profile = replace(self.local, memory_mib=2048)
        ctl = Controller(Config(self.root / 'resident', (profile,), execution_state=self.locks))
        task = replace(self.task, profile=profile.id, min_context=4096, attempts=1)
        resident = {'resident': True, 'configured_server_context': 2048}
        with (patch('aiwork.controller.opencode_path', return_value='inert'),
              patch('aiwork.controller.Inference.ready'),
              patch('aiwork.controller.ollama_residency', return_value=resident),
              patch.object(ctl, 'gpu_sample', return_value=[]),
              patch('aiwork.controller.OpenCode.execute') as worker):
            result = ctl.run_submitted(ctl.submit_task(task, True))
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('serving context 2048', result['detail'])
        worker.assert_not_called()

    def test_configured_harness_without_required_capability_cannot_dispatch(self):
        profile = replace(self.local, harness='qwen')
        ctl = Controller(Config(self.root / 'qwen', (profile,), execution_state=self.locks))
        task = replace(self.task, profile=profile.id, attempts=1)
        with patch('aiwork.controller.Inference.ready') as readiness:
            result = ctl.run_submitted(ctl.submit_task(task, True))
        self.assertEqual(result['status'], 'blocked', result)
        self.assertIn('cannot satisfy engineering contract', result['detail'])
        attempt = Path(result['artifacts']) / 'attempt-001'
        receipt = json.loads((attempt / 'execution-receipt.json').read_bytes())
        self.assertEqual(receipt['status'], 'capability_rejected')
        readiness.assert_not_called()

    def test_real_calibration_rejects_unmeasured_capacity_ram_vram_and_deadline(self):
        # The preserved measurement is read only and optional outside the operator checkout.
        calibration = CONFIG.parents[1]/'.aiwork/adaptive-local/calibration/calibration.json'
        if not calibration.is_file():
            self.skipTest('operator calibration snapshot is not installed')
        report = json.loads(calibration.read_bytes())
        base = dict(input_tokens=7440,output_tokens=2048,reserve_tokens=512,maximum=32768,
                    memory={'gpu_free_bytes':7600*MIB,'ram_available_bytes':9000*MIB},deadline_seconds=280)
        self.assertEqual(admit_context(report, **base)['selected'], 16384)
        for override, reason in (({'maximum':8192},'observed task demand'),
            ({'memory':base['memory']|{'gpu_free_bytes':1}},'GPU headroom'),
            ({'memory':base['memory']|{'ram_available_bytes':1}},'RAM headroom'),
            ({'deadline_seconds':10},'inference deadline')):
            with self.subTest(reason=reason):
                result=admit_context(report, **(base|override))
                self.assertIsNone(result['selected'])
                self.assertIn(reason,{why for row in result['candidates'] for why in row['rejected']})

    def test_exclusive_local_worker_blocks_other_controller_slot_and_recovers(self):
        runner = '''from pathlib import Path
import sys
from aiwork.router import Plane
from aiwork.schema import Profile
root=Path(sys.argv[1]); p=Profile("regular","inert","http://127.0.0.1:1/v1")
try:
    with Plane("local",2,root/"second",root/"shared-lanes").reserve(p,.3):
        print("admitted")
except TimeoutError:
    print("occupied")
'''
        plane=Plane('local',1,self.root/'state',self.locks)
        query=lambda:subprocess.check_output([sys._base_executable,'-c',runner,str(self.root)],text=True,timeout=8).strip()
        with plane.reserve(self.local, .3):
            self.assertEqual(query(),'occupied')
        self.assertEqual(query(),'admitted')

    def test_busy_a100_lane_is_bounded_and_other_plane_is_independent(self):
        peer=Plane('a100',1,self.root/'peer',self.locks)
        start=monotonic()
        with self.controller.planes['a100'].reserve(self.remote,.3):
            with self.assertRaisesRegex(TimeoutError,'a100 worker queue'):
                with peer.reserve(self.remote,.12):
                    self.fail('occupied A100 lane entered')
            with self.controller.planes['local'].reserve(self.local,.3):
                pass
        self.assertLess(monotonic()-start,1)
        with peer.reserve(self.remote,.3):
            pass

    def test_failed_cleanup_preserves_source_and_stops_promotion_and_fallback(self):
        for failed_owner in ('relay', 'local inference'):
            with self.subTest(failed_owner=failed_owner):
                def interrupted(task, profile, work, attempt, *_args):
                    (work/'units.py').write_bytes(b'value = 2\n')
                    write_json(attempt/'agent-process.json', {'code': 0})
                    relay_clean = failed_owner != 'relay'
                    write_json(attempt/'execution-receipt.json', {
                        'status': 'completed' if relay_clean else 'cleanup_failure', 'cleanup_passed': relay_clean,
                    })
                    if relay_clean:
                        local = attempt/'local-inference'
                        local.mkdir()
                        write_json(local/'ownership.json', {'cleanup_passed': False})
                    raise RuntimeError(f'owned {failed_owner} cleanup failed')

                with patch.object(self.controller, 'agent', side_effect=interrupted) as agent:
                    result = self.controller.run_submitted(self.controller.submit_task(replace(self.task, attempts=2), True))
                self.assertEqual(result['status'], 'blocked')
                self.assertIn('cleanup', result['detail'])
                self.assertEqual(agent.call_count, 1)
                attempt = Path(result['artifacts'])/'attempt-001'
                self.assertEqual((attempt/'workspace/units.py').read_bytes(), b'value = 2\n')
                self.assertEqual((self.work/'units.py').read_bytes(), b'value = 0\n')
                self.assertFalse((attempt/'output-inventory.json').exists())
                self.assertFalse((attempt/'check-00.json').exists())
                receipt = json.loads((attempt/'execution-receipt.json').read_bytes())
                self.assertEqual(receipt['status'], 'cleanup_failure')
                self.assertFalse(receipt['cleanup_passed'])

    @unittest.skipUnless(os.getenv('AIWORK_TEST_OPENCODE_BOUNDARY') and os.getenv('AIWORK_TEST_DOCKER_IMAGE'),
                         'requires installed inert OpenCode and local offline verifier')
    def test_both_controller_lanes_use_scoped_tools_and_independent_verification(self):
        for profile, value in ((self.local, 2), (self.remote, 1)):
            with self.subTest(profile=profile.id):
                self.inert_lane(profile, value)

    def inert_lane(self, profile, value):
        requests = []
        digest = sha256(b'value = 0\n').hexdigest()
        edit = {'expected_sha256':digest,'mode':'replace','old':'value = 0','new':f'value = {value}'}
        actions = [('checks_focus', {'path':'units.py'}),
                   ('checks_edit', edit|{'path':'../outside.py'}),
                   ('checks_edit', edit|{'path':'units.py'}), ('checks_check', {'index':0})]
        canary = self.root/'outside.py'
        canary.write_text('private_canary = 123456789\n', encoding='utf-8')

        class Backend(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = ({'models':[{'name':profile.model,'size_vram':4096*MIB,'context_length':profile.context}]}
                        if self.path=='/api/ps' else {'data':[{'id':profile.model}]})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length']))
                body = json.loads(raw)
                requests.append((sha256(raw).hexdigest(), body))
                i = sum(message['role']=='tool' for message in body['messages'])
                if i < len(actions):
                    name, args = actions[i]
                    delta = {'role':'assistant','tool_calls':[{'index':0,'id':f'route_tool_{i}','type':'function',
                                'function':{'name':name,'arguments':json.dumps(args)}}]}
                else:
                    delta = {'role':'assistant','content':'Inert worker claims completion.'}
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream')
                self.end_headers()
                for payload, reason in ((delta,None), ({},'tool_calls' if i<len(actions) else 'stop')):
                    row={'id':'inert','object':'chat.completion.chunk','created':1,'model':profile.model,
                         'choices':[{'index':0,'delta':payload,'finish_reason':reason}]}
                    self.wfile.write(('data: '+json.dumps(row)+'\n\n').encode())
                self.wfile.write(b'data: {"choices":[],"usage":{"prompt_tokens":110,"completion_tokens":11,"total_tokens":121}}\n\n')
                self.wfile.write(b'data: [DONE]\n\n')

        with ThreadingHTTPServer(('127.0.0.1',0),Backend) as server:
            thread=Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                selected=replace(profile,endpoint=f'http://127.0.0.1:{server.server_port}/v1')
                other=self.local if selected.location=='a100' else self.remote
                ctl=Controller(Config(self.root/f'{profile.location}-inert',(selected,other),
                    execution_state=self.locks,verification_image=os.environ['AIWORK_TEST_DOCKER_IMAGE']))
                task=replace(self.task,profile=profile.id,location=profile.location,attempts=1,timeout=55,
                             commands=(Check(('{python}','-c','from units import value; assert value > 0')),))
                # The A100 tunnel seam is inert. The route, lane lock, HTTP inventory,
                # installed harness, provider relay and Docker verification are real.
                with patch('aiwork.remote.a100_session',return_value=nullcontext()) as tunnel:
                    result=ctl.run_submitted(ctl.submit_task(task))
                self.assertEqual(tunnel.call_count,int(profile.location=='a100'))
            finally:
                server.shutdown()
                thread.join()
        status='verified' if value==2 else 'failed'
        self.assertEqual(result['status'],status,result)
        attempt=Path(result['artifacts'])/'attempt-001'
        gate=json.loads((attempt/'provider-gate.json').read_bytes())
        receipt=json.loads((attempt/'execution-receipt.json').read_bytes())
        self.assertEqual(receipt['status'],'completed')
        self.assertEqual(receipt['independent_verification'],status)
        self.assertTrue(receipt['cleanup_passed'])
        self.assertEqual([h for h,b in requests],[r['forwarded_sha256'] for r in gate['requests']])
        self.assertEqual(len(requests),5)
        self.assertTrue(all(b['model']==profile.model for h,b in requests))
        self.assertTrue(all(b['reasoning_effort']=='none' for _,b in requests))
        for _, body in requests:
            if profile.engine=='ollama':
                self.assertEqual(body['max_tokens'], profile.output_tokens)
            else:
                self.assertEqual(body['max_completion_tokens'], profile.output_tokens)
                self.assertEqual(body['chat_template_kwargs'], {'enable_thinking': False})
        self.assertEqual(605,sum(x['usage']['total_tokens'] for x in receipt['provider_usage']['reported']))
        self.assertEqual(receipt['resources']['used']['inference'],5)
        self.assertEqual(receipt['resources']['remaining_operations'],44)
        self.assertTrue(all(seconds >= 0 for seconds in receipt['resources']['seconds'].values()))
        self.assertEqual((attempt/'workspace/units.py').read_text(),f'value = {value}\n')
        self.assertEqual(canary.read_text(),'private_canary = 123456789\n')
        self.assertEqual((self.work/'units.py').read_bytes(),b'value = 0\n')
        records=[json.loads(line) for line in (attempt/'mcp.jsonl').read_text().splitlines()]
        self.assertFalse(records[1].get('applied',False))
        self.assertTrue(records[2]['applied'] and records[3]['passed'])
        self.assertEqual((attempt/'output-inventory.json').exists(),value==2)
        captured = receipt['evidence']['files']
        self.assertEqual(len(captured), 15)
        self.assertEqual(receipt['evidence']['captured_bytes'], sum(row['bytes'] for row in captured.values()))
        for name, row in captured.items():
            raw = (attempt / name).read_bytes()
            self.assertEqual(row, {'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'complete': True})
        if evidence:=os.environ.get('AIWORK_TEST_ROUTING_EVIDENCE'):
            destination=Path(evidence)/profile.location
            destination.mkdir(parents=True,exist_ok=True)
            for name in ('route.json','admission.json','catalog-readiness.json','provider-gate.json',
                         'execution-receipt.json','agent-metrics.json','mcp.jsonl','check-00.json', *captured):
                shutil.copyfile(attempt/name,destination/name)
            write_json(destination/'result.json', result)
