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

from aiwork.provider_gate import catalog, ProviderGate, REQUIRED


class ProviderGateTests(unittest.TestCase):
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
