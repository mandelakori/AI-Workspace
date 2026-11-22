"""Captured Qwen failure regression; deterministic/inert only, no model tokens."""
from copy import deepcopy
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import tempfile
from threading import Thread
import unittest

from aiwork.execution_context import ExecutionContext,ResourcePolicy
from aiwork.harness import OpenCode,opencode_path
from aiwork.schema import Check,Profile,Task
from aiwork.verify import invoke

EVIDENCE=Path(__file__).resolve().parents[1]/'docs/evidence/milestone-e-a100-result'

RENDER=r'''
import hashlib,json
from pathlib import Path
import jinja2
from jinja2.sandbox import SandboxedEnvironment
env=SandboxedEnvironment()
def fail(message):raise jinja2.TemplateError(message)
env.globals['raise_exception']=fail
template=env.from_string(Path('pinned.jinja').read_text())
results=[]
for vector in json.loads(Path('vectors.json').read_bytes()):
    try:
        rendered=template.render(**vector['body'],add_generation_prompt=True,enable_thinking=False)
        assert not vector.get('error'), 'expected rejection did not occur'
        assert all(s in rendered for s in vector.get('required',[])), 'instruction lost'
        results.append({'name':vector['name'],'accepted':True,'rendered_sha256':hashlib.sha256(rendered.encode()).hexdigest()})
    except jinja2.TemplateError as error:
        assert vector.get('error') and vector['error'] in str(error), str(error)
        results.append({'name':vector['name'],'accepted':False,'expected_error':str(error)})
print(json.dumps({'renderer':'Jinja2 '+jinja2.__version__,'model_tokens_generated':0,'results':results}))
'''


class SystemContractTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();self.spec=self.root/'tool.json'
        spec=json.loads((EVIDENCE/'attempt/tool.json').read_bytes())
        spec['deadline']=None  # Non-expiring TEST COPY, never the consumed trial.
        self.spec.write_text(json.dumps(spec))
        self.context=ExecutionContext(self.spec);self.context.initialize(ResourcePolicy(**spec['resources']))
        self.body=json.loads((EVIDENCE/'attempt/provider-request-001.json').read_bytes())

    def test_exact_captured_request_merges_without_mutating_or_truncating(self):
        raw=(EVIDENCE/'attempt/provider-request-001.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'423a6b512390534936a3c95a625a3bf2b5ba4ee11e53046a552621adb08decff')
        before=deepcopy(self.body);out,trace=self.context.provider_request(self.body)
        self.assertEqual(self.body,before)
        self.assertEqual([m['role'] for m in out['messages']],['system','user'])
        self.assertTrue(out['messages'][0]['content'].endswith('\n\n'+before['messages'][0]['content']))
        self.assertIn(json.loads(self.spec.read_bytes())['objective'].splitlines()[0],out['messages'][0]['content'])
        self.assertEqual(out['messages'][1:],before['messages'][1:])
        self.assertEqual({k:v for k,v in out.items() if k!='messages'},
                         {k:v for k,v in before.items() if k!='messages'})
        self.assertEqual(trace['remaining_operations'],96)

    def test_missing_system_gets_one_initial_contract(self):
        body=deepcopy(self.body);body['messages']=body['messages'][1:]
        out,_=self.context.provider_request(body)
        self.assertEqual(out['messages'][0]['role'],'system')
        self.assertEqual(out['messages'][1:],body['messages'])
        self.assertIn('AI-WORKSPACE ACTIVE TASK CONTRACT',out['messages'][0]['content'])

    def test_text_parts_and_system_metadata_are_preserved_in_full(self):
        body=deepcopy(self.body);original='  HARNESS-α\n'+('instructions\n'*10000)+'TAIL  '
        body['messages'][0].update(name='harness',content=original)
        out,_=self.context.provider_request(body)
        self.assertEqual(out['messages'][0]['name'],'harness')
        self.assertTrue(out['messages'][0]['content'].endswith(original))
        parts=[{'type':'text','text':'FIRST\n'},{'type':'text','text':'SECOND α'}]
        body['messages'][0]['content']=parts
        out,_=self.context.provider_request(body)
        self.assertEqual(out['messages'][0]['content'][1:],parts)
        self.assertEqual(body['messages'][0]['content'],parts)

    def test_ambiguous_or_nontext_layouts_fail_before_charging_context(self):
        valid=deepcopy(self.body['messages']);invalid=[None,[],[None],
            [{'role':[],'content':'bad'}],[{'role':'developer','content':'ambiguous'}],
            [*valid,{'role':'system','content':'late'}],
            [valid[0],valid[0],valid[1]]]
        for content in [None,{},[{'type':'image_url','image_url':{}}],
                        [{'type':'text','text':5}],[{'text':'missing type'}],
                        [{'type':'text','text':'x','image':'ambiguous'}]]:
            invalid.append([{'role':'system','content':content},valid[1]])
        invalid.append([{'role':'system','content':'x','tool_calls':[]},valid[1]])
        before=self.context.path.read_bytes()
        for messages in invalid:
            with self.subTest(messages=messages),self.assertRaises(ValueError):
                self.context.provider_request({**self.body,'messages':messages})
            self.assertEqual(self.context.path.read_bytes(),before)

    def test_compaction_and_resumed_requests_keep_contract_and_cumulative_budgets(self):
        self.context.charge_tool('focus');original=deepcopy(self.body)
        phases=[None,'compaction',None,'compaction',None]
        for phase in phases:
            body=deepcopy(self.body)
            if phase:body['messages'][-1]['content']='Summarize the conversation above.'
            else:body['messages'] += [{'role':'assistant','content':'Checkpoint'},
                {'role':'tool','tool_call_id':'public','content':'public evidence'},
                {'role':'user','content':'Continue the active implementation.'}]
            out,trace=ExecutionContext(self.spec).provider_request(body,purpose=phase)
            self.assertEqual([m['role'] for m in out['messages']].count('system'),1)
            self.assertEqual(out['messages'][1:],body['messages'][1:])
            self.assertTrue(out['messages'][0]['content'].endswith(original['messages'][0]['content']))
            self.assertIn('"write_roots":',out['messages'][0]['content'])
            self.assertIn('"public_checks":',out['messages'][0]['content'])
            self.assertEqual(trace['remaining_operations'],95)
        state=self.context.summary()
        self.assertEqual(state['used']['inference'],3);self.assertEqual(state['used']['compaction'],2)
        self.assertEqual(state['used']['inspection'],1);self.assertEqual(state['epoch'],2)

    @unittest.skipUnless(os.environ.get('AIWORK_TEST_QWEN_TEMPLATE_IMAGE'),'requires existing offline Jinja image')
    def test_full_pinned_template_reproduces_failure_and_accepts_corrected_cycles(self):
        props=json.loads((EVIDENCE/'preflight-endpoint.json').read_bytes())['props']['data']
        expected=json.loads((EVIDENCE/'manifest.json').read_bytes())['endpoint_identity']['chat_template_sha256']
        self.assertEqual(hashlib.sha256(props['chat_template'].encode()).hexdigest(),expected)
        vectors=[{'name':'exact-historical-failure','body':json.loads((EVIDENCE/'attempt/provider-forwarded-001.json').read_bytes()),
                  'error':'System message must be at the beginning.'}]
        for name,phase in [('initial',None),('compaction-1','compaction'),('resumed-1',None),('compaction-2','compaction'),('resumed-2',None),('missing-system',None),('text-parts',None)]:
            body=deepcopy(self.body)
            if phase:body['messages'][-1]['content']='Summarize the conversation above.'
            if name=='missing-system':body['messages']=body['messages'][1:]
            if name=='text-parts':body['messages'][0]['content']=[{'type':'text','text':'HARNESS-FIRST'},{'type':'text','text':'HARNESS-SECOND'}]
            original=body['messages'][0].get('content') if body['messages'][0]['role']=='system' else None
            out,_=self.context.provider_request(body,purpose=phase)
            required=['AI-WORKSPACE ACTIVE TASK CONTRACT']+([original.strip()] if isinstance(original,str) else ['HARNESS-FIRST','HARNESS-SECOND'] if original else [])
            vectors.append({'name':name,'body':out,'required':required})
        (self.root/'pinned.jinja').write_bytes(props['chat_template'].encode('utf-8'))
        self.assertEqual(hashlib.sha256((self.root/'pinned.jinja').read_bytes()).hexdigest(),expected)
        (self.root/'vectors.json').write_text(json.dumps(vectors),encoding='utf-8')
        (self.root/'render.py').write_text(RENDER)
        result=invoke(Check(('python','render.py'),timeout=30),self.root,self.root/'home',os.environ['AIWORK_TEST_QWEN_TEMPLATE_IMAGE'])
        evidence=os.environ.get('AIWORK_TEST_SYSTEM_EVIDENCE')
        if evidence:
            target=Path(evidence)/'template';target.mkdir(parents=True,exist_ok=True)
            for name in ('pinned.jinja','vectors.json','render.py'):shutil.copyfile(self.root/name,target/name)
            (target/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
        self.assertTrue(result['passed'],result['stderr'])
        results=json.loads(result['stdout'])['results'];self.assertEqual(len(results),8)
        self.assertFalse(results[0]['accepted']);self.assertTrue(all(r['accepted'] for r in results[1:]))


@unittest.skipUnless(os.environ.get('AIWORK_TEST_OPENCODE_BOUNDARY'),'installed OpenCode; inert provider only')
class OpenCodeResendTests(unittest.TestCase):
    def test_installed_opencode_resend_never_reaches_failed_provider(self):
        received=[]
        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(500);self.end_headers()
                self.wfile.write(b'{"error":{"message":"inert failure, no model"}}')
        with tempfile.TemporaryDirectory() as directory,ThreadingHTTPServer(('127.0.0.1',0),Backend) as server:
            root=Path(directory).resolve();work=root/'work';work.mkdir();artifacts=root/'artifacts';artifacts.mkdir()
            (work/'module.py').write_text('unchanged = True\n')
            spec=artifacts/'tool.json';spec.write_text(json.dumps({'workspace':str(work),'baseline':str(work),
                'engineering':True,'objective':'Inert failure only','write_roots':['module.py'],'image':'',
                'checks':[{'argv':['{python}','-V']}]}))
            thread=Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                task=Task('Inert failure only',work,'agent','inert',(),('module.py',),(),mode='engineering',write_roots=('module.py',))
                result=OpenCode(opencode_path()).execute(Profile('inert','inert',f'http://127.0.0.1:{server.server_port}/v1'),
                    task,work,artifacts,task.objective,25,spec)
            finally:server.shutdown();thread.join()
            gate=json.loads((artifacts/'provider-gate.json').read_bytes())
            evidence=os.environ.get('AIWORK_TEST_SYSTEM_EVIDENCE')
            if evidence:
                target=Path(evidence)/'opencode-resend';target.mkdir(parents=True,exist_ok=True)
                for p in artifacts.iterdir():
                    if p.is_file() and p.suffix in {'.json','.jsonl','.txt','.sse'}:shutil.copyfile(p,target/p.name)
            self.assertEqual(len(received),1)
            self.assertNotEqual(result.code,0);self.assertFalse(result.timed_out)
            self.assertEqual([r['forwarded'] for r in gate['requests']],[True,False])
            self.assertEqual(gate['requests'][1]['retry_of'],1)
            self.assertEqual(gate['requests'][1]['blocked_reason'],'failure_latched')
            self.assertEqual((work/'module.py').read_text(),'unchanged = True\n')
            self.assertTrue(json.loads((artifacts/'execution-receipt.json').read_bytes())['cleanup_passed'])
