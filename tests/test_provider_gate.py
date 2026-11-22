"""Inert HTTP backends prove admission precedes forwarding; no model is used."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Thread
from time import monotonic
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler
import unittest
from unittest.mock import patch
from time import sleep

from aiwork.provider_gate import catalog, ProviderGate, REQUIRED
from aiwork.execution_context import ExecutionContext, ResourcePolicy


class ProviderGateTests(unittest.TestCase):
    def test_upstream_failure_latches_and_records_same_and_changed_body_resends(self):
        received=[]
        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                received.append(self.rfile.read(int(self.headers['Content-Length'])))
                self.send_response(500);self.end_headers();self.wfile.write(b'{"error":"synthetic"}')
        with tempfile.TemporaryDirectory() as tmp,ThreadingHTTPServer(('127.0.0.1',0),Backend) as backend:
            thread=Thread(target=backend.serve_forever);thread.start()
            try:
                root=Path(tmp);spec=root/'tool.json'
                spec.write_text(json.dumps({'objective':'Keep goal','write_roots':['module.py'],'checks':[]}))
                context=ExecutionContext(spec);context.initialize(ResourcePolicy())
                with ProviderGate(f'http://127.0.0.1:{backend.server_port}/v1','inert','',root,monotonic()+8,context=context) as gate:
                    for i,body in enumerate([self.body(),self.body(),{**self.body(),'temperature':0}]):
                        req=Request(gate.endpoint+'/chat/completions',json.dumps(body).encode(),headers={'Authorization':'Bearer '+gate.token})
                        with self.assertRaises(HTTPError) as caught:build_opener(ProxyHandler({})).open(req,timeout=2)
                        self.assertEqual(caught.exception.code,500 if i==0 else 400)
                        if i:self.assertEqual(json.loads(caught.exception.read())['error']['code'],'controller_failure_latched')
                self.assertEqual(len(received),1)
                self.assertEqual([r['forwarded'] for r in gate.receipts],[True,False,False])
                self.assertEqual(gate.receipts[1]['retry_of'],1);self.assertIsNone(gate.receipts[2]['retry_of'])
                self.assertEqual(context.summary()['used']['inference'],1)
                self.assertEqual(context.summary()['remaining_operations'],48)
            finally:backend.shutdown();thread.join()

    def test_slow_inert_prefill_survives_multiple_cancellation_poll_intervals(self):
        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200);self.end_headers();sleep(.8);self.wfile.write(b'{"ok":true}')
        with tempfile.TemporaryDirectory() as directory,ThreadingHTTPServer(('127.0.0.1',0),Backend) as backend:
            thread=Thread(target=backend.serve_forever);thread.start()
            try:
                with ProviderGate(f'http://127.0.0.1:{backend.server_port}/v1','inert','',Path(directory),monotonic()+5) as gate:
                    req=Request(gate.endpoint+'/chat/completions',json.dumps(self.body()).encode(),
                                headers={'Authorization':'Bearer '+gate.token})
                    with build_opener(ProxyHandler({})).open(req,timeout=3) as response:self.assertEqual(response.read(),b'{"ok":true}')
                self.assertFalse(gate.failed.is_set())
            finally:backend.shutdown();thread.join()
    def body(self, names=REQUIRED):
        return {'model':'inert','messages':[{'role':'user','content':'synthetic'}],
                'tools':[{'type':'function','function':{'name':n,'parameters':{'type':'object'}}} for n in sorted(names)]}

    def test_catalog_requires_all_tools_without_adding_permissions(self):
        self.assertTrue(catalog(self.body())['passed'])
        for names in [[], ['glob','grep'], REQUIRED|{'bash'}, [*REQUIRED,'checks_focus']]:
            with self.subTest(names=names):self.assertFalse(catalog(self.body(names))['passed'])

    def test_missing_catalog_latches_closed_and_never_reaches_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            with ProviderGate('http://127.0.0.1:1/v1','inert','',Path(tmp),monotonic()+5) as gate:
                for body in [self.body(['glob']),self.body()]:
                    req=Request(gate.endpoint+'/chat/completions',json.dumps(body).encode(),
                                headers={'Authorization':'Bearer '+gate.token,'Content-Type':'application/json'})
                    with self.assertRaises(HTTPError) as caught:build_opener(ProxyHandler({})).open(req,timeout=2)
                    self.assertEqual(caught.exception.code,400)
                self.assertTrue(gate.failed.is_set())
                self.assertTrue(all(not r['forwarded'] for r in gate.receipts))

    def test_valid_catalog_forwards_request_bytes_unchanged(self):
        received=[]
        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                received.append(self.rfile.read(int(self.headers['Content-Length'])))
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(b'{"ok":true}')
        with tempfile.TemporaryDirectory() as tmp,ThreadingHTTPServer(('127.0.0.1',0),Backend) as backend:
            thread=Thread(target=backend.serve_forever);thread.start()
            try:
                with ProviderGate(f'http://127.0.0.1:{backend.server_port}/v1','inert','',Path(tmp),monotonic()+5) as gate:
                    raw=json.dumps(self.body(),indent=1).encode()
                    req=Request(gate.endpoint+'/chat/completions',raw,headers={'Authorization':'Bearer '+gate.token})
                    with build_opener(ProxyHandler({})).open(req,timeout=2) as response:self.assertEqual(response.read(),b'{"ok":true}')
                self.assertEqual(received,[raw])
                self.assertFalse(gate.failed.is_set())
            finally:backend.shutdown();thread.join()

    def test_exhausted_context_never_forwards_and_is_not_provider_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spec=root/'tool.json'
            spec.write_text(json.dumps({'objective':'Active goal','write_roots':['module.py'],'checks':[]}))
            context=ExecutionContext(spec)
            context.initialize(ResourcePolicy(operations=1,edit_reserve=0,verification_reserve=0))
            context.charge_tool('focus')
            with ProviderGate('http://127.0.0.1:1/v1','inert','',root,monotonic()+5,context=context) as gate:
                req=Request(gate.endpoint+'/chat/completions',json.dumps(self.body()).encode(),
                            headers={'Authorization':'Bearer '+gate.token})
                with self.assertRaises(HTTPError) as caught:build_opener(ProxyHandler({})).open(req,timeout=2)
                self.assertEqual(caught.exception.code,400)
                self.assertIn(b'controller_resource_exhausted',caught.exception.read())
                self.assertTrue(gate.exhausted.is_set())
                self.assertFalse(gate.failed.is_set())
                self.assertFalse(gate.receipts[0]['forwarded'])

    def test_scoped_catalog_refuses_unmetered_native_tools(self):
        self.assertFalse(catalog(self.body(REQUIRED|{'glob'}),scoped_only=True)['passed'])

    def test_accounting_failure_fails_closed_without_skipping_connection_cleanup(self):
        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200);self.end_headers();self.wfile.write(b'{"ok":true}')
        with tempfile.TemporaryDirectory() as tmp,ThreadingHTTPServer(('127.0.0.1',0),Backend) as backend:
            root=Path(tmp);spec=root/'tool.json'
            spec.write_text(json.dumps({'objective':'Public objective','write_roots':['module.py'],'checks':[]}))
            context=ExecutionContext(spec);context.initialize(ResourcePolicy())
            thread=Thread(target=backend.serve_forever);thread.start()
            try:
                with patch.object(context,'elapsed',side_effect=TimeoutError('injected accounting failure')):
                    with ProviderGate(f'http://127.0.0.1:{backend.server_port}/v1','inert','',root,
                                      monotonic()+5,context=context) as gate:
                        req=Request(gate.endpoint+'/chat/completions',json.dumps(self.body()).encode(),
                                    headers={'Authorization':'Bearer '+gate.token})
                        with build_opener(ProxyHandler({})).open(req,timeout=2) as response:response.read()
                self.assertTrue(gate.failed.is_set())
                self.assertFalse(gate.connections)
                self.assertEqual(gate.receipts[0]['accounting_error'],'TimeoutError')
            finally:backend.shutdown();thread.join()
