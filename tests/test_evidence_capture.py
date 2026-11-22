"""No inference: exact payload integrity, bounded capture and inert HTTP replay."""
import errno
import hashlib
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import tempfile
from threading import Event, Thread
from time import monotonic,sleep
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,build_opener,ProxyHandler

from aiwork.evidence_capture import EvidenceCapture,EvidenceExhausted,EvidenceIOError,UsageLines
from aiwork.execution_context import ExecutionContext,ResourcePolicy,ResourceExhausted
from aiwork.process import Result
from aiwork.provider_gate import ProviderGate,REQUIRED,finish_execution

ROOT=Path(__file__).resolve().parents[1]


def body():
    return {'model':'inert','messages':[{'role':'user','content':'fixture only'}],
            'tools':[{'type':'function','function':{'name':name,'parameters':{'type':'object'}}} for name in sorted(REQUIRED)]}


def send(gate,value=None):
    return build_opener(ProxyHandler({})).open(Request(gate.endpoint+'/chat/completions',
        json.dumps(body() if value is None else value).encode(),headers={'Authorization':'Bearer '+gate.token}),timeout=8)


def context(root):
    spec=root/'tool.json';spec.write_text(json.dumps({'objective':'inert capture fixture','write_roots':['module.py'],'checks':[]}))
    result=ExecutionContext(spec);result.initialize(ResourcePolicy(model_requests=128));return result


def proof(name,value):
    directory=os.environ.get('AIWORK_TEST_EVIDENCE_CAPTURE')
    if directory:
        target=Path(directory);target.mkdir(parents=True,exist_ok=True)
        (target/(name+'.json')).write_bytes((json.dumps(value,indent=2)+'\n').encode())


class CaptureTests(unittest.TestCase):
    def test_reservations_limit_disk_headroom_and_release_unused_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);capture=EvidenceCapture(root,10,0)
            with capture.reserve(7) as first:
                with self.assertRaises(EvidenceExhausted):
                    with capture.reserve(4,exact=True):pass
                with capture.reserve(9) as second:self.assertEqual(second[0],3)
                with capture.open('a') as stream:capture.append('a',stream,b'ab',first)
            self.assertEqual(capture.used,2);self.assertEqual(capture.reserved,0)
            capture.complete('a');self.assertEqual(capture.files['a']['sha256'],hashlib.sha256(b'ab').hexdigest())
            with patch('aiwork.evidence_capture.shutil.disk_usage',return_value=shutil._ntuple_diskusage(100,100,0)):
                with self.assertRaises(EvidenceExhausted):
                    with capture.reserve(1):pass
            self.assertEqual(capture.used,2)

    def test_partial_disk_write_is_accounted_hashed_and_classified(self):
        with tempfile.TemporaryDirectory() as directory:
            capture=EvidenceCapture(Path(directory),20,0)
            with capture.open('partial') as stream:
                class Disk:
                    calls=0
                    def write(self,data):
                        self.calls+=1
                        if self.calls==1:return stream.write(data[:3])
                        raise OSError(errno.ENOSPC,'injected full disk')
                with self.assertRaises(EvidenceExhausted):
                    with capture.reserve(9) as lease:capture.append('partial',Disk(),b'abcdefghi',lease)
            self.assertEqual(capture.used,3);self.assertEqual(capture.reserved,0)
            self.assertFalse(capture.files['partial']['complete'])
            self.assertEqual(capture.files['partial']['sha256'],hashlib.sha256(b'abc').hexdigest())
            self.assertEqual(capture.files['partial']['unarchived_bytes'],6)
            self.assertEqual(capture.files['partial']['unarchived_sha256'],hashlib.sha256(b'defghi').hexdigest())

    def test_exact_writes_do_not_overwrite_or_exceed_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);capture=EvidenceCapture(root,3,0);capture.store('one',b'abc')
            with self.assertRaises(EvidenceExhausted):capture.store('two',b'd')
            self.assertFalse((root/'two').exists());self.assertEqual(capture.used,3)
            other=EvidenceCapture(root,10,0)
            with self.assertRaises(EvidenceIOError):other.store('one',b'changed')
            self.assertEqual((root/'one').read_bytes(),b'abc')
            for limit in [0,-1,True,513*1024*1024]:
                with self.assertRaises(ValueError):EvidenceCapture(root,limit,0)

    def test_usage_parsing_is_incremental_and_oversized_lines_do_not_grow_memory(self):
        parser=UsageLines();data=b'data: '+json.dumps({'usage':{'total_tokens':7}}).encode()+b'\n\n'
        for byte in data:parser.feed(bytes([byte]))
        self.assertEqual(parser.usage,{'total_tokens':7})
        for _ in range(100):parser.feed(b'x'*65536)
        self.assertLessEqual(len(parser.pending),256*1024);self.assertTrue(parser.oversized)
        parser.feed(b'\n'+data);self.assertEqual(parser.usage,{'total_tokens':7})


class CaptureGateTests(unittest.TestCase):
    def test_metadata_ceiling_preserves_last_ledger_and_records_resource_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ctx=context(root)
            gate=ProviderGate('http://127.0.0.1:1/v1','inert','',root,monotonic()+5,context=ctx)
            gate.save();before=(root/'provider-gate.json').read_bytes()
            gate.receipts=[{'injected': 'x'*(16*1024*1024)}]
            with self.assertRaises(EvidenceExhausted):gate.save()
            self.assertEqual((root/'provider-gate.json').read_bytes(),before)
            self.assertTrue((root/'provider-evidence-exhaustion.json').exists())
            self.assertTrue(gate.exhausted.is_set());self.assertIn('metadata',ctx.summary()['exhausted'])

    def test_attribution_limit_stops_unadmitted_requests_without_payload_or_forward(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ctx=context(root)
            with ProviderGate('http://127.0.0.1:1/v1','inert','',root,monotonic()+5,context=ctx) as gate:
                gate.count=1024
                with self.assertRaises(HTTPError):send(gate)
            self.assertEqual(gate.capture.used,0);self.assertEqual(gate.unadmitted_requests,1)
            self.assertFalse(gate.receipts);self.assertTrue(gate.exhausted.is_set());self.assertFalse(gate.failed.is_set())
            with self.assertRaises(ResourceExhausted):ctx.provider_request(body())

    def test_upstream_truncated_http_body_remains_provider_failure_with_prefix_hash(self):
        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']));self.send_response(200)
                self.send_header('Content-Length','100');self.end_headers();self.wfile.write(b'prefix')
        with tempfile.TemporaryDirectory() as directory,ThreadingHTTPServer(('127.0.0.1',0),Backend) as backend:
            root=Path(directory);server=Thread(target=backend.serve_forever);server.start()
            try:
                with ProviderGate(f'http://127.0.0.1:{backend.server_port}/v1','inert','',root,monotonic()+5) as gate:
                    try:
                        with send(gate) as response:response.read()
                    except IncompleteRead:pass
                self.assertTrue(gate.failed.is_set());self.assertFalse(gate.exhausted.is_set())
                self.assertFalse(gate.receipts[0]['response_complete'])
                self.assertEqual(gate.receipts[0]['error'],'IncompleteRead')
                self.assertEqual(gate.receipts[0]['response_sha256'],hashlib.sha256(b'prefix').hexdigest())
            finally:backend.shutdown();server.join()

    def test_incoming_and_rewritten_limits_stop_before_forwarding_with_attribution(self):
        raw=json.dumps(body()).encode()
        for size in [1,len(raw)+1]:
            with self.subTest(size=size),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);ctx=context(root)
                with ProviderGate('http://127.0.0.1:1/v1','inert','',root,monotonic()+5,context=ctx,capture_limit=size,disk_headroom=0) as gate:
                    with self.assertRaises(HTTPError):send(gate)
                self.assertFalse(gate.receipts[0]['forwarded']);self.assertTrue(gate.exhausted.is_set());self.assertFalse(gate.failed.is_set())
                self.assertEqual(gate.receipts[0]['declared_request_bytes'],len(raw))
                self.assertLessEqual(gate.capture.used,size);self.assertEqual(gate.capture.reserved,0)
                with self.assertRaises(ResourceExhausted):ctx.provider_request(body())

    def test_stream_exhaustion_preserves_exact_prefix_and_normalizes_cleanly(self):
        payload=b'x'*80000;received=[]
        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                received.append(self.rfile.read(int(self.headers['Content-Length'])))
                self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers()
                try:self.wfile.write(payload)
                except OSError:pass
        with tempfile.TemporaryDirectory() as directory,ThreadingHTTPServer(('127.0.0.1',0),Backend) as backend:
            root=Path(directory);ctx=context(root);thread=Thread(target=backend.serve_forever);thread.start()
            try:
                with ProviderGate(f'http://127.0.0.1:{backend.server_port}/v1','inert','',root,monotonic()+8,context=ctx,capture_limit=4096,disk_headroom=0) as gate:
                    try:
                        with send(gate) as response:client=response.read()
                    except IncompleteRead as error:client=error.partial
                    for _ in range(100):
                        if gate.exhausted.is_set():break
                        sleep(.01)
                    with self.assertRaises(HTTPError):send(gate)
                self.assertEqual(len(received),1);self.assertTrue(gate.exhausted.is_set());self.assertFalse(gate.failed.is_set())
                receipt=gate.receipts[0];saved=(root/'provider-response-001.sse').read_bytes()
                self.assertEqual(saved,client);self.assertEqual(saved,payload[:len(saved)])
                self.assertFalse(receipt['response_complete']);self.assertEqual(receipt['response_sha256'],hashlib.sha256(saved).hexdigest())
                self.assertEqual(gate.capture.used,4096);self.assertEqual(gate.capture.reserved,0);self.assertFalse(gate.connections)
                final=finish_execution('inert',gate,Result(1,1,'','',False,False),ctx,root,monotonic(),True)
                normalized=json.loads((root/'execution-receipt.json').read_bytes());self.assertEqual(final.code,0)
                self.assertEqual(normalized['status'],'resource_exhausted');self.assertIn('evidence',normalized['exhaustion_reason'])
                proof('configured-exhaustion',{'gate':json.loads((root/'provider-gate.json').read_bytes()),'execution':normalized})
            finally:backend.shutdown();thread.join()

    def test_cancelled_stream_keeps_hash_and_closes_owned_connections(self):
        delivered=Event();release=Event()
        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']));self.send_response(200);self.end_headers()
                self.wfile.write(b'prefix');self.wfile.flush();delivered.set();release.wait(5)
        with tempfile.TemporaryDirectory() as directory,ThreadingHTTPServer(('127.0.0.1',0),Backend) as backend:
            root=Path(directory);server=Thread(target=backend.serve_forever);server.start();errors=[]
            try:
                with ProviderGate(f'http://127.0.0.1:{backend.server_port}/v1','inert','',root,monotonic()+20) as gate:
                    def client():
                        try:
                            with send(gate) as response:response.read()
                        except OSError as error:errors.append(type(error).__name__)
                    reader=Thread(target=client);reader.start();self.assertTrue(delivered.wait(2))
                    for _ in range(100):
                        if gate.capture.files.get('provider-response-001.sse',{}).get('bytes')==6:break
                        sleep(.01)
                reader.join(2);self.assertFalse(reader.is_alive());self.assertFalse(gate.connections)
                self.assertTrue(gate.failed.is_set());self.assertFalse(gate.receipts[0]['response_complete'])
                self.assertEqual(gate.receipts[0]['response_sha256'],hashlib.sha256(b'prefix').hexdigest())
            finally:release.set();backend.shutdown();server.join()

    def test_storage_failure_is_local_evidence_failure_and_never_forwards(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ctx=context(root)
            with ProviderGate('http://127.0.0.1:1/v1','inert','',root,monotonic()+5,context=ctx) as gate:
                with patch.object(gate.capture,'store',side_effect=EvidenceIOError('injected write failure')):
                    with self.assertRaises(HTTPError):send(gate)
            finish_execution('inert',gate,Result(1,0,'','',False,False),ctx,root,monotonic(),True)
            self.assertEqual(json.loads((root/'execution-receipt.json').read_bytes())['status'],'evidence_failure')
            self.assertFalse(gate.receipts[0]['forwarded'])

    def test_full_saved_streams_replayed_twice_exceed_observed_trial_size(self):
        source=ROOT/'docs/evidence/a100-editor-trial-result/attempt'
        paths=[source/f'provider-response-{n:03}.sse' for _ in range(2) for n in range(1,45)]
        incoming=[(source/f'provider-request-{n:03}.json').read_bytes() for _ in range(2) for n in range(1,45)]
        position=[0]
        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']));path=paths[position[0]];position[0]+=1
                self.send_response(200);self.send_header('Content-Length',str(path.stat().st_size));self.end_headers()
                with path.open('rb') as stream:
                    while data:=stream.read(65536):self.wfile.write(data)
        with tempfile.TemporaryDirectory() as directory,ThreadingHTTPServer(('127.0.0.1',0),Backend) as backend:
            root=Path(directory);ctx=context(root);server=Thread(target=backend.serve_forever);server.start();started=monotonic()
            try:
                with ProviderGate(f'http://127.0.0.1:{backend.server_port}/v1',json.loads(incoming[0])['model'],'',root,monotonic()+120,context=ctx) as gate:
                    for index,raw in enumerate(incoming):
                        request=Request(gate.endpoint+'/chat/completions',raw,headers={'Authorization':'Bearer '+gate.token})
                        digest=hashlib.sha256()
                        with build_opener(ProxyHandler({})).open(request,timeout=10) as response:
                            while data:=response.read(65536):digest.update(data)
                        self.assertEqual(digest.hexdigest(),hashlib.sha256(paths[index].read_bytes()).hexdigest())
                audit=gate.capture.summary();self.assertGreater(audit['captured_bytes'],16777435)
                self.assertLessEqual(audit['captured_bytes'],audit['limit_bytes']);self.assertFalse(gate.failed.is_set());self.assertFalse(gate.exhausted.is_set())
                self.assertEqual(position[0],88);self.assertEqual(len(gate.receipts),88);self.assertEqual(audit['reserved_bytes'],0)
                for name,item in audit['files'].items():
                    data=(root/name).read_bytes();self.assertEqual(len(data),item['bytes']);self.assertEqual(hashlib.sha256(data).hexdigest(),item['sha256']);self.assertTrue(item['complete'])
                self.assertEqual(sum(x['bytes'] for x in audit['files'].values()),audit['captured_bytes'])
                proof('saved-trace-replay',{'kind':'88 INERT HTTP REPLAYS; 44 COMPLETE HISTORICAL STREAMS TWICE; NO MODEL',
                    'seconds':monotonic()-started,'gate':json.loads((root/'provider-gate.json').read_bytes()),'all_payload_hashes_verified':True})
            finally:backend.shutdown();server.join()
