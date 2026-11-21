import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from aiwork.mcp import focus, inspect_source
from aiwork.index import relevant
from aiwork.metrics import summarize_trace
from aiwork.harness import OpenCode
from aiwork.process import Result
from aiwork.schema import Check, Profile, Task
from unittest.mock import patch


class FocusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.work = self.root / "work"
        self.work.mkdir()

    def test_symbol_and_pagination_do_not_dump_full_source(self):
        source = "# header\n" + "# padding\n" * 1000 + "class Parser:\n    def parse(self, text):\n        return text\n"
        (self.work / "parser.py").write_text(source, newline="\n")
        small = focus(self.work, {"path":"parser.py", "symbol":"Parser.parse"})
        self.assertEqual(small["source"], "    def parse(self, text):\n        return text\n")
        self.assertIsNone(small["next_line"])
        first = focus(self.work, {"path":"parser.py"})
        self.assertEqual(first["next_line"], 61)
        self.assertEqual(focus(self.work, {"path":"parser.py", "line":61})["line"], 61)
        self.assertLessEqual(len(first["source"]), 3000)
        (self.work / "unicode.py").write_text(("#"+"界"*100+"\n")*200,encoding="utf-8",newline="\n")
        self.assertLessEqual(len(focus(self.work,{"path":"unicode.py"})["source"].encode("utf-8")),3000)

    def test_discovery_and_query_jump_beyond_headers_in_large_python_and_text(self):
        source='# padding for discovery\n'*4000+'class Engine:\n    def execute(self, value):\n        return value\n'
        (self.work/'engine.py').write_text(source,newline='\n')
        first=focus(self.work,{'path':'engine.py'})
        self.assertTrue(any(d['symbol']=='Engine' for d in first['symbols']))
        excerpt=focus(self.work,{'path':'engine.py','query':'execute'})
        self.assertEqual(excerpt['selected_symbol'],'Engine.execute')
        self.assertGreater(excerpt['line'],4000)
        self.assertIn('return value',excerpt['source'])
        self.assertLessEqual(len(json.dumps(excerpt['symbols']).encode()),1200)
        (self.work/'notes.txt').write_text('unused\n'*120+'target contract\n')
        self.assertIn('target contract',focus(self.work,{'path':'notes.txt','query':'target'})['source'])
        for bad in [True,'x'*161]:
            with self.assertRaises(ValueError):focus(self.work,{'path':'engine.py','query':bad})

    def test_writable_source_precedes_keyword_heavy_tests_and_parses_large_files(self):
        (self.work/'engine.py').write_text('# padding\n'*8000+'class Engine:\n    pass\n')
        (self.work/'test_engine_conversion_state_parser.py').write_text('def test_engine_conversion():pass\n')
        result=json.loads(relevant(self.work,'engine conversion state parser',('engine.py',),1800))['matches']
        self.assertEqual(result[0]['path'],'engine.py')
        self.assertIn('Engine',result[0]['symbols'])

    def test_duplicate_excerpts_are_suppressed_across_reconnect_until_source_changes(self):
        p=self.work/'module.py';p.write_text('value = 1\n',newline='\n')
        spec=self.root/'tool.json'
        first=inspect_source(spec,self.work,{'path':'module.py'})
        second=inspect_source(spec,self.work,{'path':'module.py'})
        self.assertEqual(first['source'],'value = 1\n')
        self.assertEqual(second['source'],'')
        self.assertTrue(second['already_inspected'])
        p.write_text('value = 2\n',newline='\n')
        self.assertEqual(inspect_source(spec,self.work,{'path':'module.py'})['source'],'value = 2\n')

    def test_reconnect_keeps_budget_objective_and_executes_public_check_after_edit(self):
        (self.work/'module.py').write_text('value = 1\n')
        spec=self.root/'tool.json'
        goal='Implement the active public objective'
        spec.write_text(json.dumps({'workspace':str(self.work),'baseline':str(self.work),
            'engineering':True,'objective':goal,'write_roots':['module.py'],'image':'',
            'checks':[{'argv':['{python}','-c','from module import value; assert value == 2; print("VERIFIED")']}]}))
        def call(name,args):
            message={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}}
            result=subprocess.run([sys.executable,'-m','aiwork.mcp',str(spec)],input=json.dumps(message)+'\n',
                                  capture_output=True,text=True,check=True,timeout=20)
            return json.loads(json.loads(result.stdout)['result']['content'][0]['text'])
        self.assertEqual(call('focus',{'path':'module.py'})['remaining_calls'],15)
        (self.work/'module.py').write_text('value = 2\n')
        self.assertIn('value = 2',call('focus',{'path':'module.py'})['source'])
        result=call('check',{'index':0})
        self.assertTrue(result['passed'])
        self.assertEqual(result['stdout'].strip(),'VERIFIED')
        self.assertEqual(result['objective'],goal)
        self.assertEqual(result['remaining_calls'],13)
        for _ in range(13):call('focus',{'path':'module.py'})
        self.assertIn('budget exhausted',call('check',{'index':0})['error'])

    def test_external_excluded_binary_and_oversized_input_are_rejected(self):
        (self.root / "private.txt").write_text("PRIVATE-CANARY")
        (self.work / ".env").write_text("PRIVATE-CANARY")
        (self.work / "binary").write_bytes(b"\xff")
        (self.work / "huge").write_bytes(b"x" * (256*1024+1))
        (self.work / "long-line").write_text("x" * 4000)
        for name in ("../private.txt", ".env", "binary", "huge", "long-line"):
            with self.subTest(name=name), self.assertRaises((ValueError, UnicodeError)):
                focus(self.work, {"path":name})
        for args in ({"path":"binary", "line":True}, {"path":"binary", "line":0}, {"path":"binary", "shell":"echo"}):
            with self.assertRaises(ValueError): focus(self.work, args)

    def test_symbol_pagination_resumes_without_repeating_the_first_page(self):
        (self.work / "long.py").write_text("def target():\n"+"    pass\n"*80,newline="\n")
        first=focus(self.work,{"path":"long.py","symbol":"target"})
        second=focus(self.work,{"path":"long.py","symbol":"target","line":first["next_line"]})
        self.assertEqual(second["line"],61)
        self.assertIsNone(second["next_line"])
        self.assertNotIn("def target",second["source"])
        with self.assertRaises(ValueError):focus(self.work,{"path":"long.py","symbol":"target","line":90})

    def test_mcp_inspection_preserves_goal_and_public_failure_tail(self):
        (self.work / "module.py").write_text("value = 1\n")
        spec = self.root / "tool.json"
        spec.write_text(json.dumps({"workspace":str(self.work), "baseline":str(self.work),
            "engineering":True, "objective":"Implement the active public objective", "write_roots":["module.py"],
            "image":"", "checks":[{"argv":["{python}", "-c", "print('x'*6000); raise ValueError('CONCRETE-CAUSE')"]}]}))
        messages = [{"jsonrpc":"2.0", "id":i, "method":"tools/call", "params":{"name":name,"arguments":args}}
                    for i,(name,args) in enumerate([("focus",{"path":"module.py"}), ("check",{"index":0})],1)]
        raw = subprocess.run([sys.executable,"-m","aiwork.mcp",str(spec)], input="\n".join(map(json.dumps,messages))+"\n",
                             capture_output=True,text=True,check=True,timeout=20)
        responses = [json.loads(json.loads(line)["result"]["content"][0]["text"]) for line in raw.stdout.splitlines()]
        self.assertEqual(responses[0]["objective"], "Implement the active public objective")
        self.assertEqual(responses[0]["remaining_calls"],15)
        self.assertFalse(responses[1]["passed"])
        self.assertIn("CONCRETE-CAUSE",responses[1]["stderr"])
        self.assertEqual(responses[1]['objective'],responses[0]['objective'])

    def test_small_opencode_engineering_uses_bounded_inspection(self):
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        task = Task("Implement active objective",self.work,"agent","test",(),("module.py",),(Check(("{python}","-V")),),
                    mode="engineering",write_roots=("module.py",))
        with patch("aiwork.harness.mcp_catalog",return_value={'passed':True,'tools':[]}),patch("aiwork.harness.run",return_value=Result(0,0,"","",False,False)) as run:
            OpenCode("fixture").run_session(Profile("local","fixture","http://localhost:9999/v1",context=8192),
                task,self.work,artifacts,"objective",10,artifacts/"tool.json",None)
        permissions=json.loads(run.call_args.args[3]["OPENCODE_CONFIG_CONTENT"])["permissions"]
        self.assertFalse(any(p["action"]=="read" and p["effect"]=="allow" for p in permissions))
        self.assertTrue(any(p["action"]=="checks_focus" and p["effect"]=="allow" for p in permissions))
        self.assertTrue(any(p['action']=='checks_edit' and p['effect']=='allow' for p in permissions))
        self.assertFalse(any(p['action'] in {'edit','write','patch'} and p['effect']=='allow' for p in permissions))

    def test_inspection_success_does_not_count_as_a_passing_public_test(self):
        (self.root / "mcp.jsonl").write_text("\n".join(json.dumps({"tool":tool,"passed":True})
                                                   for tool in ["focus","focus","check","diff"]))
        self.assertEqual(summarize_trace("",self.root)["successful_public_mcp_checks"],1)
