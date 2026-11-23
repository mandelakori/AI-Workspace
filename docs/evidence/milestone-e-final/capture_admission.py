"""Inert storage sizing only: recorded streams plus conservative new public context."""
import hashlib,importlib.util,json,shutil,sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from time import monotonic
from urllib.request import Request,build_opener,ProxyHandler
root=Path.cwd();sys.path.insert(0,str(root))
from aiwork.execution_context import ExecutionContext,ResourcePolicy
from aiwork.harness import mcp_catalog
from aiwork.provider_gate import ProviderGate
from aiwork.trial_budget import write
module=importlib.util.spec_from_file_location('trial',root/'examples/milestone-e-final/trial.py');trial=importlib.util.module_from_spec(module);module.loader.exec_module(trial)
bundle=root/'.aiwork/milestone-e-final/acceptance-trial';manifest=trial.load(bundle);task=trial.task(bundle,manifest)
out=root/'.aiwork/milestone-e-final/capture-admission-final';out.mkdir(exist_ok=False)
spec=out/'tool.json';write(spec,{'workspace':str(bundle/'input'),'baseline':str(bundle/'input'),'engineering':True,'objective':task.objective,
 'write_roots':list(task.write_roots),'image':manifest['runner'],'checks':[{'argv':list(c.argv),'timeout':c.timeout} for c in task.commands],
 'resources':{'operations':96,'edit_reserve':8,'verification_reserve':8,'model_requests':64,'compactions':4}})
catalog=mcp_catalog(spec,out/'catalog-home',8,None);write(out/'catalog.json',catalog)
context=ExecutionContext(spec)
source=root/'docs/evidence/a100-editor-trial-result/attempt'
blob='\n'.join((bundle/'input'/p).read_text(encoding='utf-8') for p in ['FEATURE.md','PUBLIC-VERIFICATION.md','_aiwork_checks.py','_aiwork_original_checks.py','_aiwork_public.json','_aiwork_expanded.json'])
sequence=[i%44+1 for i in range(64)];index=[0]
class Backend(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']));number=sequence[index[0]];index[0]+=1
        path=source/f'provider-response-{number:03}.sse'
        self.send_response(200);self.send_header('Content-Length',str(path.stat().st_size));self.end_headers()
        with path.open('rb') as stream:
            while chunk:=stream.read(65536):self.wfile.write(chunk)
started=monotonic()
with ThreadingHTTPServer(('127.0.0.1',0),Backend) as backend:
    thread=Thread(target=backend.serve_forever,daemon=True);thread.start()
    try:
        with ProviderGate(f'http://127.0.0.1:{backend.server_port}/v1',manifest['profile']['model'],'',out,monotonic()+120,context=context) as gate:
            for number in sequence:
                body=json.loads((source/f'provider-request-{number:03}.json').read_bytes())
                body['messages'][0]['content']+='\nInert conservative public-context sizing only:\n'+blob
                body['tools']=[{'type':'function','function':{'name':'checks_'+t['name'],'description':t['description'],'parameters':t['inputSchema']}} for t in catalog['tools']]
                request=Request(gate.endpoint+'/chat/completions',json.dumps(body).encode(),headers={'Authorization':'Bearer '+gate.token})
                actual=hashlib.sha256()
                with build_opener(ProxyHandler({})).open(request,timeout=10) as response:
                    while chunk:=response.read(65536):actual.update(chunk)
                assert actual.hexdigest()==hashlib.sha256((source/f'provider-response-{number:03}.sse').read_bytes()).hexdigest()
    finally:backend.shutdown();thread.join()
capture=gate.capture.summary()
assert len(gate.receipts)==64 and not gate.failed.is_set() and not gate.exhausted.is_set()
assert capture['reserved_bytes']==0 and all(v['complete'] for v in capture['files'].values())
for name,entry in capture['files'].items():
    data=(out/name).read_bytes();assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
write(out/'summary.json',{'kind':'INERT CAPACITY VALIDATION; recorded streams; NO MODEL TOKENS OR ENGINEERING CLAIM',
 'requests':64,'source_response_sequence':sequence,'all_current_public_text_bytes_padded_per_request':len(blob.encode()),
 'seconds':monotonic()-started,'payload_bytes':capture['captured_bytes'],'payload_limit':capture['limit_bytes'],
 'disk_headroom':capture['headroom_bytes'],'actual_disk_free':shutil.disk_usage(out).free,'remaining_payload_bytes':capture['limit_bytes']-capture['captured_bytes'],
 'all_192_payload_hashes_verified':True,'all_streams_complete':True,'new_model_requests':0,
 'limitations':'Measured conservative trace mix, not a guarantee for every worst-case model output/context combination. Hard limits still apply.'})
print((out/'summary.json').read_text())
