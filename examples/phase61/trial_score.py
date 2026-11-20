"""Read-only public benchmark adapter. No target implementation or private cases."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

policy = json.loads(Path('_trial_policy.json').read_bytes())

def public():
    spec = importlib.util.spec_from_file_location('public_contract', '_public_checks.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for i, name in enumerate(unittest.defaultTestLoader.getTestCaseNames(module.PublicPathMounts), 1):
        result = unittest.TestResult()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            module.PublicPathMounts(name).run(result)
        rows.append({'case':i, 'name':name, 'verdict':'pass' if result.wasSuccessful() else 'tests',
                     'diagnostic':str(result.failures+result.errors)[-1800:]})
    return rows

def artifacts():
    target = Path('tests/test_path_mounts.py')
    docs = Path('docs/advanced/transports.md').read_text(encoding='utf-8')
    changed = hashlib.sha256(docs.encode()).hexdigest() != policy['original_docs_text_sha256']
    test = subprocess.run([sys.executable,'-m','pytest','-q','-p','anyio.pytest_plugin','-p','no:cacheprovider',str(target)],
                          capture_output=True,text=True,timeout=60) if target.exists() else None
    passed = changed and '/api' in docs and test is not None and test.returncode == 0
    return {'passed':passed,'docs_changed':changed,'tests_passed':bool(test and test.returncode==0),
            'diagnostic':((test.stdout+test.stderr)[-2000:] if test else 'missing authored tests')}

mode=sys.argv[1]
if mode == 'artifacts':
    result=artifacts();print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)
elif mode == 'score':
    upstream=subprocess.run(policy['upstream'],capture_output=True,text=True,timeout=120)
    rows=public();own=artifacts()
    print(json.dumps({'upstream':{'passed':upstream.returncode==0,'diagnostic':(upstream.stdout+upstream.stderr)[-2200:]},
                      'cases':rows,'artifacts':own}))
else:
    raise ValueError('unsupported benchmark mode')
