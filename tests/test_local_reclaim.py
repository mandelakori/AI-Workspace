import hashlib
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
from time import monotonic
import unittest
from unittest.mock import patch

from aiwork.local_reclaim import listener_identity, reclaim_local_memory, unload_idle
from aiwork.process import Result
from aiwork.schema import Config, IdleOllama


class LocalReclaimTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        binary = self.root/'ollama.exe'
        binary.write_bytes(b'reviewed inert fixture')
        self.policy = IdleOllama('http://127.0.0.1:21234', 'idle:fixture', 'a'*64, str(binary),
                                 hashlib.sha256(binary.read_bytes()).hexdigest())
        self.person = (17, 12345, binary)
        self.row = {'name':self.policy.model, 'digest':self.policy.model_sha256}

    def test_operator_configuration_is_opt_in_and_loopback_only(self):
        config = self.root/'controller.toml'
        self.assertIsNone(Config.load(config).idle_ollama)
        config.write_text('[idle_ollama]\n' + ''.join(f'{k} = {json.dumps(v)}\n' for k,v in vars(self.policy).items()))
        self.assertEqual(Config.load(config).idle_ollama, self.policy)
        for address in ('https://127.0.0.1:11434', 'http://localhost:11434', 'http://127.0.0.1:0',
                        'http://127.0.0.1:11434/v1','http://192.0.2.1:11434'):
            with self.subTest(address=address), self.assertRaises(ValueError):
                replace(self.policy,endpoint=address).validate()

    def test_exact_local_model_unload_and_pending_active_runner(self):
        ack = {'done':True,'done_reason':'unload','model':self.policy.model}
        unmanaged = {'name':'untouched:latest','digest':'b'*64}
        for resident, status in (([unmanaged], 'unloaded'), ([self.row, unmanaged], 'still_resident')):
            with (self.subTest(status=status), patch('aiwork.local_reclaim.listener_identity',return_value=self.person),
                  patch('aiwork.local_reclaim.sleep'), patch('aiwork.local_reclaim.local_json',side_effect=[
                      {'version':'0.40.17'},{'models':[self.row, unmanaged]},{'models':[self.row, unmanaged]},ack,
                      *[{'models':resident}]*3]) as rpc):
                self.assertEqual(unload_idle(self.policy),{'status':status,'posts':1})
                posts = [c for c in rpc.call_args_list if c.args[1]=='api/generate']
                self.assertEqual(len(posts),1)
                self.assertEqual(posts[0].args[2],{'model':self.policy.model,'keep_alive':0,'stream':False})

    def test_unknown_or_changed_identity_never_posts(self):
        tag = {'models':[self.row]}
        scenarios = (
            (replace(self.policy, executable_sha256='b'*64), [self.person], [], 'executable hash'),
            (self.policy, [self.person], [{'version':'unknown'}], 'version lacks'),
            (self.policy, [self.person], [{'version':'0.40.17'},{'models':[self.row|{'digest':'b'*64}]}], 'model identity'),
            (self.policy, [self.person,self.person[:1]+(23456,self.person[2])], [{'version':'0.40.17'},tag,tag], 'listener identity'),
        )
        for policy, identity, responses, message in scenarios:
            with (self.subTest(message=message), patch('aiwork.local_reclaim.listener_identity',side_effect=identity),
                  patch('aiwork.local_reclaim.local_json',side_effect=responses) as rpc):
                with self.assertRaisesRegex(ValueError,message):
                    unload_idle(policy)
                self.assertTrue(all(c.args[1]!='api/generate' for c in rpc.call_args_list))

    def test_reclamation_deadline_stop_and_unconfigured_policy(self):
        with patch('aiwork.local_reclaim.run') as child:
            self.assertFalse(reclaim_local_memory(None,self.root,monotonic()+30))
            self.assertFalse(reclaim_local_memory(self.policy,self.root,monotonic()+1))
            stop=self.root/'STOP';stop.touch()
            self.assertFalse(reclaim_local_memory(self.policy,self.root,monotonic()+30,stop))
            child.assert_not_called()
            child.return_value=Result(1,8,'','',True,False)
            self.assertTrue(reclaim_local_memory(self.policy,self.root,monotonic()+30))
            self.assertEqual(child.call_args.args[2],8)
            self.assertEqual(json.loads((self.root/'memory-reclamation.json').read_bytes())['status'],'client_timed_out')

    @unittest.skipUnless(os.name=='nt','Windows listener identity')
    def test_listener_identity_uses_live_windows_process(self):
        with ThreadingHTTPServer(('127.0.0.1',0),BaseHTTPRequestHandler) as server:
            pid, launched, binary=listener_identity(f'http://127.0.0.1:{server.server_port}')
            self.assertEqual(pid,os.getpid())
            self.assertGreater(launched,0)
            self.assertEqual(binary.name.lower(),'python.exe')
