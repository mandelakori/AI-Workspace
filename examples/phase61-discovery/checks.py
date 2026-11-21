"""Public behavior and independent grading entry point; contains no implementation."""
import ast
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch


def evaluate(case):
    from dotenv.variables import parse_variables
    if 'stream' in case:
        from dotenv import dotenv_values
        with patch.dict(os.environ, {}, clear=True):
            return dict(dotenv_values(stream=StringIO(case['stream'])))
    return ''.join(atom.resolve(case.get('env', {})) for atom in parse_variables(case['value']))


def public(path):
    cases=json.loads(Path(path).read_text(encoding='utf-8'))
    results=[]
    for case in cases:
        try:
            actual=evaluate(case)
            results.append({'id':case['id'],'passed':actual==case['expected'],
                            'expected':case['expected'],'actual':actual})
        except Exception as error:
            results.append({'id':case['id'],'passed':False,'error':type(error).__name__+': '+str(error)[:500]})
    return {'passed':sum(r['passed'] for r in results),'total':len(results),'cases':results}


if __name__=='__main__':
    action=sys.argv[1]
    import dotenv.variables
    module=Path(dotenv.variables.__file__).resolve()
    if module!=Path('/work/src/dotenv/variables.py'):
        raise RuntimeError('candidate import did not resolve to the mounted source')
    if action=='sealed':
        # Read only input from stdin; expectations remain on the controller host.
        print(json.dumps(evaluate(json.loads(sys.stdin.read()))));sys.exit(0)
    if action=='public':
        result=public('_public_cases.json')
        result['source_sha256']=hashlib.sha256(module.read_bytes()).hexdigest()
        print(json.dumps(result));sys.exit(0 if result['passed']==result['total'] else 1)
    if action=='syntax':
        ast.parse(module.read_bytes())
        print(json.dumps({'syntax_passed':True,'source_sha256':hashlib.sha256(module.read_bytes()).hexdigest()}))
    else:
        import pytest
        # /tmp is noexec in the existing sandbox. Upstream CLI tests create
        # one executable fixture. Run that unchanged test in the disposable bind
        # copy; keep all other temporary I/O on the faster container tmpfs.
        args=['-q','-rs','-p','no:cacheprovider']
        if action=='upstream':
            executable_test='test_run_with_path_from_env_file'
            regular=pytest.main([*args,'tests','--ignore=tests/test_nested_defaults.py',
                                 '-k','not '+executable_test])
            Path('/work/.pytest_cache').mkdir(exist_ok=True)
            executable=pytest.main([*args,'tests/test_cli.py::'+executable_test,
                                    '--basetemp=/work/.pytest_cache/exec-tmp'])
            sys.exit(1 if regular or executable else 0)
        sys.exit(pytest.main([*args,'tests/test_nested_defaults.py']))
