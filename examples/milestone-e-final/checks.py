"""Public specification verifier. Calls target APIs; contains no implementation."""
import ast
from datetime import datetime,timedelta,timezone
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path('src').resolve()))
spec=importlib.util.spec_from_file_location('original_checks',Path('_aiwork_original_checks.py'))
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
ACTIONS=('public_original','public_expanded','upstream','authored','interfaces','documentation','syntax')


def emit(value):
    print(json.dumps(value));return 0 if value['passed'] else 1


def limit_value(case):
    if 'delta' in case:return timedelta(**case['delta'])
    if case.get('unlimited'):return None
    if 'unsupported' not in case:return case['seconds']
    kind=case['unsupported'];value=case.get('value')
    if kind=='bytes':return value.encode('utf-8')
    if kind=='float_only':
        class FloatOnly:
            def __float__(self):return float(value)
        return FloatOnly()
    return value


def observe(case):
    from itsdangerous import TimestampSigner,TimedSerializer,URLSafeTimedSerializer,SignatureExpired,BadSignature
    now=[case.get('signed_at',1600000000)]
    class ClockSigner(TimestampSigner):
        def get_timestamp(self):return now[0]
    api=case['api'];limit=limit_value(case)
    signer=ClockSigner('public-fixture-key',sep=case.get('separator','.'))
    factory=URLSafeTimedSerializer if api.startswith('urlsafe') else TimedSerializer
    kwargs={'signer':ClockSigner,'signer_kwargs':{'sep':case.get('separator','.')}}
    serializer=factory(['old-fixture-key','new-fixture-key'] if case.get('rotation') else 'old-fixture-key',**kwargs)
    old=factory('old-fixture-key',**kwargs)
    token=signer.sign(b'public feature payload') if api in {'signer','validate'} else old.dumps({'public':'payload'})
    if case.get('tamper'):token=token[:-1]+(b'!' if isinstance(token,bytes) else '!')
    now[0]+=case['age'];stamp=datetime.fromtimestamp(case.get('signed_at',1600000000),tz=timezone.utc)
    try:
        if api=='validate':return {'result':'accepted' if signer.validate(token,max_age=limit) else 'invalid'}
        if api=='signer':
            value,at=signer.unsign(token,max_age=limit,return_timestamp=True)
            return {'result':'accepted','payload_ok':value==b'public feature payload','timestamp_ok':at==stamp and at.tzinfo is not None}
        if api.endswith('unsafe'):
            valid,value=serializer.loads_unsafe(token,max_age=limit)
            return {'result':'accepted' if valid else 'unsafe-expired','payload_ok':value=={'public':'payload'}}
        value,at=serializer.loads(token,max_age=limit,return_timestamp=True)
        return {'result':'accepted','payload_ok':value=={'public':'payload'},'timestamp_ok':at==stamp and at.tzinfo is not None}
    except SignatureExpired as error:
        return {'result':'expired','metadata_ok':error.date_signed==stamp and (api!='signer' or error.payload==b'public feature payload')}
    except BadSignature:return {'result':'bad-signature'}
    except Exception as error:return {'result':type(error).__name__}


def behavior(expanded):
    rows=[]
    for case in json.loads(Path('_aiwork_public.json').read_bytes()):
        actual=original.observe(case);ok=actual['result']==case['expected'] and all(v for k,v in actual.items() if k.endswith('_ok'))
        rows.append({'id':case['id'],'passed':ok,**({'observed':actual,'expected':case['expected']} if not ok else {})})
    original_passed=sum(row['passed'] for row in rows)
    if expanded:
        for case in json.loads(Path('_aiwork_expanded.json').read_bytes()):
            actual=observe(case);ok=actual['result']==case['expected'] and all(v for k,v in actual.items() if k.endswith('_ok'))
            rows.append({'id':case['id'],'passed':ok,**({'observed':actual,'expected':case['expected']} if not ok else {})})
    passed=sum(row['passed'] for row in rows);failures=[row for row in rows if not row['passed']]
    return {'passed':passed==len(rows),'passed_cases':passed,'total':len(rows),'original_passed':original_passed,'original_total':12,
            'cases':rows,'summary':f'Public {passed}/{len(rows)}; original {original_passed}/12. First discrepancies: '+str(failures[:2])[:290]}


def docs():
    from itsdangerous import TimestampSigner,TimedSerializer
    text=Path('docs/timed.rst').read_text(encoding='utf-8');lower=text.lower()
    import hashlib
    expected=json.loads(Path('_aiwork_contract.json').read_bytes())['original_doc_sha256']
    rules={'changed':hashlib.sha256(Path('docs/timed.rst').read_bytes()).hexdigest()!=expected,'word_count':len(text.split())>=30,
           **{key:key in lower for key in ['max_age','timedelta','seconds','fraction','zero','negative']},
           'equality':any(word in lower for word in ['equal','inclusive'])}
    for fn in [TimestampSigner.unsign,TimestampSigner.validate,TimedSerializer.loads,TimedSerializer.loads_unsafe]:
        rules[fn.__qualname__+'_docstring']='timedelta' in (inspect.getdoc(fn) or '')
    return {'passed':all(rules.values()),'rules':rules,'summary':'Documentation failed rules: '+str([k for k,v in rules.items() if not v])}


def authored_once(epoch):
    import pytest
    from freezegun import freeze_time
    from itsdangerous import TimestampSigner
    path=Path('tests/test_itsdangerous/test_timedelta_max_age.py')
    if not path.is_file():return {'passed':False,'summary':'Required authored test file missing'}
    tree=ast.parse(path.read_text(encoding='utf-8'));errors=[];time_modules={'time'};sleep_names=set()
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):time_modules.update(alias.asname or alias.name for alias in node.names if alias.name=='time')
        if isinstance(node,ast.ImportFrom) and node.module=='time':sleep_names.update(alias.asname or alias.name for alias in node.names if alias.name in {'sleep','*'})
    assertions=sum(isinstance(n,ast.Assert) or isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='raises' for n in ast.walk(tree))
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call):continue
        fn=node.func
        if isinstance(fn,ast.Name) and fn.id in sleep_names or isinstance(fn,ast.Attribute) and fn.attr=='sleep' and isinstance(fn.value,ast.Name) and fn.value.id in time_modules:
            errors.append('wall-clock sleep at line '+str(node.lineno))
        if isinstance(fn,ast.Attribute) and fn.attr=='encode' and isinstance(fn.value,ast.Attribute) and fn.value.attr=='sep':errors.append('bytes separator encode at line '+str(node.lineno))
    if errors or assertions<1:return {'passed':False,'summary':str(errors or ['Assertions/pytest.raises required; at least six passing collected tests'])}
    observed={'duration':0,'int':0,'none':0,'unsupported':0,'large_int':0};original_unsign=TimestampSigner.unsign
    def observe_call(frame,event,arg):
        if event!='call' or frame.f_code is not original_unsign.__code__:return
        value=frame.f_locals['max_age']
        if isinstance(value,timedelta):observed['duration']+=1
        elif value is None:observed['none']+=1
        elif isinstance(value,int):
            observed['int']+=1
            if abs(value)>2**53:observed['large_int']+=1
        elif not isinstance(value,float):observed['unsupported']+=1
    class Plugin:
        def __init__(self):self.passed=0;self.failed=0;self.skipped=0;self.failures=[]
        @pytest.fixture(autouse=True)
        def fixed_clock(self,monkeypatch):
            def no_sleep(*args,**kwargs):raise AssertionError('Wall-clock sleep is prohibited; use a deterministic clock')
            with freeze_time(epoch):
                monkeypatch.setattr(time,'sleep',no_sleep)
                previous=sys.getprofile();sys.setprofile(observe_call)
                try:yield
                finally:sys.setprofile(previous)
        def pytest_runtest_logreport(self,report):
            if report.skipped or getattr(report,'wasxfail',False):self.skipped+=1
            if report.failed and len(self.failures)<3:
                self.failures.append({'test':report.nodeid,'message':report.longreprtext[-350:]})
            if report.when=='call':
                if report.passed:self.passed+=1
                if report.failed:self.failed+=1
    plugin=Plugin();code=pytest.main(['-q','-p','no:cacheprovider',str(path)],plugins=[plugin])
    return {'passed':code==0 and plugin.passed>=6 and not plugin.skipped and observed['duration']>=6 and all(observed[k] for k in ['int','none','unsupported','large_int']),
            'tests_passed':plugin.passed,'tests_failed':plugin.failed,'skipped':plugin.skipped,'observed':observed,
            'failures':plugin.failures,
            'summary':(f'Authored exit={code}, passed={plugin.passed}, failed={plugin.failed}, skipped={plugin.skipped}, API calls={observed}; '
                       +('First failure: '+plugin.failures[0]['test']+': '+plugin.failures[0]['message'] if plugin.failures else 'Check required API coverage.'))[-440:]}


def run(action):
    if action=='public_original':return behavior(False)
    if action=='public_expanded':return behavior(True)
    if action=='documentation':return docs()
    if action=='authored':
        results=[]
        for epoch in ['2031-04-07 09:10:11','2034-10-19 16:17:18']:
            process=subprocess.run([sys.executable,__file__,'authored_once',epoch],capture_output=True,text=True,timeout=15)
            try:value=json.loads(process.stdout.splitlines()[-1])
            except (ValueError,IndexError):value={'passed':False,'summary':(process.stderr or process.stdout)[-600:]}
            results.append(value)
        return {'passed':all(row['passed'] for row in results),'runs':results,'summary':' | '.join(row['summary'] for row in results)[-600:]}
    if action in {'upstream','interfaces','syntax'}:
        process=subprocess.run([sys.executable,'_aiwork_original_checks.py',action],capture_output=True,text=True,timeout=35)
        return {'passed':process.returncode==0,'stdout':process.stdout,'stderr':process.stderr,'summary':action+': '+(process.stdout+process.stderr)[-250:]}
    if action=='acceptance':
        results={name:run(name) for name in ACTIONS}
        failed=[name for name,row in results.items() if not row['passed']]
        summary=(f"Mandatory gates {'FAIL' if failed else 'PASS'}; original {results['public_original']['passed_cases']}/12; combined {results['public_expanded']['passed_cases']}/48; failed={failed}. "
                 +'; '.join(name+': '+results[name].get('summary','failed')[-150:] for name in failed[:2]))[:440]
        return {'passed':all(row['passed'] for row in results.values()),'results':results,
                'summary':summary}
    raise ValueError('unsupported public check')


if __name__=='__main__':
    action=sys.argv[1]
    if action=='sealed':
        payload=json.loads(sys.stdin.read());print(json.dumps(observe(payload) if payload.get('expanded') else original.observe(payload)))
    else:raise SystemExit(emit(authored_once(sys.argv[2]) if action=='authored_once' else run(action)))
