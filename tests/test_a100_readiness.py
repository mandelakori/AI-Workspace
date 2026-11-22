"""Frozen-trial guards: inert/local tests, never A100 inference."""
from dataclasses import asdict, replace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from aiwork.harness import request_options
from aiwork.httpx_benchmark import digest, file_hash, implementation
from aiwork.router import routes
from aiwork.schema import Config,Profile
from aiwork.workspace import inventory

SCRIPT=Path(__file__).resolve().parents[1]/'examples/milestone-e-a100/trial.py'
spec=importlib.util.spec_from_file_location('a100_trial',SCRIPT)
trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)


class A100ReadinessTests(unittest.TestCase):
    def fixture(self,root):
        for part in ('input','source'):
            (root/part).mkdir();(root/part/'FEATURE.md').write_text('Implement the duration feature.')
        binary=root/'opencode';binary.write_bytes(b'inert')
        p=Config.load(trial.ASSETS/'controller.toml').profiles[0]
        m={'kind':'milestone-e-a100-itsdangerous','arm':trial.ARM,'phase_limits':trial.LIMITS,
            'input_inventory':inventory(root/'input'),'pristine_inventory':inventory(root/'source'),
            'opencode':{'path':str(binary),'sha256':file_hash(binary)},'profile':asdict(p),'runner':'sha256:inert',
            'implementation_sha256':implementation(),
            'asset_hashes':{p.name:file_hash(p) for p in trial.ASSETS.iterdir() if p.is_file()}}
        (root/'manifest.json').write_text(json.dumps(m));(root/'manifest.sha256').write_text(digest(m))
        return m

    def test_exact_approval_and_consumed_trial_guards_prevent_dispatch(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);m=self.fixture(root);grant=root/'grant.json'
            for approved,arms in [(False,[trial.ARM]),(True,['local']),(True,[])]:
                grant.write_text(json.dumps({'approval_digest':digest(m),'authorize':arms,'operator_approved':approved}))
                with patch.object(trial,'run_phase') as dispatch:
                    with self.assertRaises(ValueError):trial.run(root,grant)
                    dispatch.assert_not_called()
            self.assertFalse((root/'execution-started.json').exists())
            grant.write_text(json.dumps({'approval_digest':digest(m),'authorize':[trial.ARM],'operator_approved':True}))
            self.assertEqual(trial.authorize(root,grant),m)
            with self.assertRaises((ValueError,FileNotFoundError)):trial.closed(root)
            (root/'execution-started.json').write_text('{}')
            with patch.object(trial,'runner_status',return_value={'image_id':'sha256:inert'}),patch.object(trial,'run_phase') as dispatch:
                with self.assertRaisesRegex(ValueError,'consumed'):trial.run(root,grant)
                dispatch.assert_not_called()

    def test_frozen_source_drift_and_managed_profiles_fail_closed(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);m=self.fixture(root);self.assertEqual(trial.load(root),m)
            (root/'input/FEATURE.md').write_text('changed')
            with self.assertRaisesRegex(ValueError,'source changed'):trial.load(root)
            (root/'input/FEATURE.md').write_text('Implement the duration feature.')
            m['profile']['managed']=True
            (root/'manifest.json').write_text(json.dumps(m));(root/'manifest.sha256').write_text(digest(m))
            with self.assertRaisesRegex(ValueError,'A100 trial'):trial.load(root)

    def test_explicit_a100_route_preserves_capacity_and_disabled_thinking(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);m=self.fixture(root);t=trial.task(root,m);p=Profile(**m['profile'])
            t.validate();local=replace(p,id='local',location='local')
            r=routes(t,(local,p),{'local':(1000,1000,.1),p.id:(0,1,30)})
            self.assertEqual([x.profile.id for x in r],[trial.ARM])
            self.assertEqual(p.context,65536);self.assertEqual(t.timeout,720);self.assertEqual(t.tool_operations,96)
            self.assertEqual(request_options(p)['chat_template_kwargs'],{'enable_thinking':False})
            self.assertEqual(t.attempts,1)
            props={'model_path':p.model,'model_ftype':'Q6_K','build_info':'inert','total_slots':1,
                   'default_generation_settings':{'n_ctx':131072},'chat_template':'inert'}
            manifest={'endpoint_identity':trial.identity(props)}
            trial.ready_identity(manifest,props,[{'is_processing':False,'n_ctx':131072}])
            for slots in ([],[{'is_processing':True,'n_ctx':131072}],[{'is_processing':False,'n_ctx':8192}]):
                with self.assertRaisesRegex(ValueError,'no inference'):trial.ready_identity(manifest,props,slots)

    def test_inventory_accepts_slot_arrays_but_rejects_generation_routes(self):
        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                self.send_response(200);self.end_headers();self.wfile.write(b'[{"id":0,"is_processing":false}]')
        with ThreadingHTTPServer(('127.0.0.1',0),Backend) as server:
            worker=Thread(target=server.serve_forever,daemon=True);worker.start()
            try:
                self.assertEqual(trial.read_json(f'http://127.0.0.1:{server.server_port}/slots'),[{'id':0,'is_processing':False}])
                with self.assertRaises(ValueError):trial.read_json(f'http://127.0.0.1:{server.server_port}/completion')
                with self.assertRaises(ValueError):trial.read_json('http://127.0.0.1:1@evil.invalid/props')
            finally:server.shutdown();worker.join()
