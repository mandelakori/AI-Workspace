"""Test explicit template switches and installed OpenCode tool rounds without inference."""
from dataclasses import replace
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from aiwork.harness import OpenCode, opencode_path, request_options
from aiwork.schema import Check, Profile, Task


PROFILE = Profile('inert', 'inert', 'http://127.0.0.1:18080/v1', engine='llamacpp',
                  seed=1729, temperature=0, context=65536, output_tokens=4096)
TOOLS = {'checks_focus', 'checks_diff', 'checks_edit', 'checks_check'}


class ThinkingSerializationTests(unittest.TestCase):
    def test_paired_wire_settings_only_differ_in_boolean(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                p = replace(PROFILE, enable_thinking=enabled)
                p.validate()
                self.assertEqual(request_options(p), {'temperature': 0, 'seed': 1729,
                    'chat_template_kwargs': {'enable_thinking': enabled}})

    def test_existing_defaults_and_effort_serialization(self):
        self.assertEqual(request_options(PROFILE), {'temperature': 0, 'seed': 1729})
        legacy = request_options(replace(PROFILE, reasoning_effort='none'))
        self.assertEqual(legacy['reasoning_effort'], 'none')
        self.assertIs(legacy['chat_template_kwargs']['enable_thinking'], False)
        self.assertNotIn('chat_template_kwargs', request_options(replace(PROFILE, reasoning_effort='high')))
        self.assertNotIn('chat_template_kwargs', request_options(replace(PROFILE, engine='ollama', reasoning_effort='none')))

    def test_invalid_or_conflicting_settings_rejected(self):
        for options in ({'enable_thinking': 'false'}, {'enable_thinking': 1},
                        {'enable_thinking': True, 'engine': 'ollama'},
                        {'enable_thinking': True, 'reasoning_effort': 'none'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                replace(PROFILE, **options).validate()


@unittest.skipUnless(os.environ.get('AIWORK_TEST_OPENCODE_BOUNDARY'), 'requires installed inert OpenCode')
class ThinkingOpenCodeTests(unittest.TestCase):
    def test_both_modes_deliver_hash_edits_and_public_checks(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), TemporaryDirectory() as directory:
                self.run_mode(Path(directory).resolve(), enabled)

    def run_mode(self, root, enabled):
        work = root / 'work'
        artifacts = root / 'artifacts'
        work.mkdir()
        artifacts.mkdir()
        source = b'value = 1\n'
        (work / 'answer.py').write_bytes(source)
        commands = [('checks_focus', {'path': 'answer.py'}),
                    ('checks_edit', {'path': 'answer.py', 'expected_sha256': sha256(source).hexdigest(),
                                     'mode': 'replace', 'old': 'value = 1', 'new': 'value = 2'}),
                    ('checks_check', {'index': 0})]
        bodies = []
        checks = [{'argv': ['{python}', '-c', 'from answer import value; assert value == 2']}]
        spec = artifacts / 'tool.json'
        spec.write_text(json.dumps({'workspace': str(work), 'baseline': str(work), 'engineering': True,
            'objective': 'Set the inert fixture value to two and check it.', 'write_roots': ['answer.py'],
            'image': '', 'checks': checks, 'resources': {'operations': 24, 'edit_reserve': 4,
                'verification_reserve': 4, 'model_requests': 18, 'compactions': 1}}), encoding='utf-8')

        class Backend(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                bodies.append(body)
                index = sum(m['role'] == 'tool' for m in body['messages'])
                active = index < len(commands)
                if active:
                    name, args = commands[index]
                    delta = {'role': 'assistant', 'tool_calls': [{'index': 0, 'id': f'fixture_{index}',
                             'type': 'function', 'function': {'name':name, 'arguments':json.dumps(args)}}]}
                else:
                    delta = {'role': 'assistant', 'content': 'Inert fixture complete.'}
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                chunks = [(delta, None), ({}, 'tool_calls' if active else 'stop')]
                if enabled:
                    chunks.insert(0, ({'role': 'assistant', 'reasoning_content': 'Synthetic mode marker.'}, None))
                for payload, reason in chunks:
                    event = {'id': 'inert', 'object': 'chat.completion.chunk', 'created': 1, 'model': 'inert',
                             'choices': [{'index': 0, 'delta': payload, 'finish_reason': reason}]}
                    self.wfile.write(('data: ' + json.dumps(event) + '\n\n').encode())
                usage = {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}
                if enabled:
                    usage['completion_tokens_details'] = {'reasoning_tokens': 2}
                self.wfile.write(('data: ' + json.dumps({'choices': [], 'usage': usage}) + '\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')

        task = Task('Set the inert fixture value to two and check it.', work, 'agent', 'inert', (),
                    ('answer.py',), (Check.read(checks[0]),), mode='engineering', write_roots=('answer.py',))
        with ThreadingHTTPServer(('127.0.0.1', 0), Backend) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                p = replace(PROFILE, endpoint=f'http://127.0.0.1:{server.server_port}/v1', enable_thinking=enabled)
                binary = opencode_path()
                self.assertTrue(binary)
                result = OpenCode(binary).execute(p, task, work, artifacts, task.objective, 35, spec)
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(result.code, 0, result.stderr)
        self.assertFalse(result.timed_out)
        self.assertEqual((work / 'answer.py').read_bytes(), b'value = 2\n')
        self.assertEqual(len(bodies), 4)
        self.assertTrue(all({t['function']['name'] for t in b['tools']} == TOOLS for b in bodies))
        self.assertTrue(all(b['chat_template_kwargs'] == {'enable_thinking': enabled}
                            and 'reasoning_effort' not in b and b['temperature'] == 0 and b['seed'] == 1729
                            and b.get('max_completion_tokens', b.get('max_tokens')) == 4096 for b in bodies))
        rows = [json.loads(line) for line in (artifacts / 'mcp.jsonl').read_text().splitlines()]
        self.assertEqual([r['tool'] for r in rows], ['focus', 'edit', 'check'])
        self.assertTrue(rows[1]['applied'] and rows[2]['passed'])
        receipt = json.loads((artifacts / 'execution-receipt.json').read_bytes())
        self.assertTrue(receipt['cleanup_passed'] and receipt['provider_gate_passed'])
        reports = receipt['provider_usage']['reported']
        self.assertEqual(len(reports), 4)
        self.assertTrue(all(x['usage'].get('completion_tokens_details', {}).get('reasoning_tokens')
                            == (2 if enabled else None) for x in reports))
        if evidence := os.environ.get('AIWORK_TEST_THINKING_EVIDENCE'):
            destination = Path(evidence) / ('on' if enabled else 'off')
            destination.mkdir(parents=True, exist_ok=True)
            for p in artifacts.iterdir():
                if p.is_file() and p.suffix in {'.json', '.sse', '.jsonl'}:
                    shutil.copyfile(p, destination / p.name)
