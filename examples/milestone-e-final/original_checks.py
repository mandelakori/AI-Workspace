"""Frozen public verifier and payload-only sealed runner; no reference solution."""
import ast
from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
import sys
import typing

sys.path.insert(0,str(Path('src').resolve()))


def observe(case):
    from itsdangerous import BadSignature, SignatureExpired, TimestampSigner, TimedSerializer, URLSafeTimedSerializer
    clock=[1700000000]
    class ClockSigner(TimestampSigner):
        def get_timestamp(self):return clock[0]
    limit=(None if case.get('unlimited') else timedelta(**case['delta']) if 'delta' in case else case['seconds'])
    payload={'message':case.get('message','duration test'),'values':[1,False,None]}
    mode=case['api'];signer=ClockSigner('aiwork-public-test-key')
    factory=URLSafeTimedSerializer if mode.startswith('urlsafe') else TimedSerializer
    old=factory('old-public-test-key',signer=ClockSigner)
    serializer=factory(['old-public-test-key','new-public-test-key'] if case.get('rotation') else 'old-public-test-key',signer=ClockSigner)
    signed=signer.sign(b'public payload') if mode in {'signer','validate'} else old.dumps(payload)
    if case.get('tamper'):
        signed=signed[:-1]+(b'!' if isinstance(signed,bytes) else '!')
    clock[0]+=case['age'];stamp=datetime.fromtimestamp(1700000000,tz=timezone.utc)
    try:
        if mode=='validate':return {'result':'accepted' if signer.validate(signed,max_age=limit) else 'invalid'}
        if mode=='signer':
            value,at=signer.unsign(signed,max_age=limit,return_timestamp=True)
            return {'result':'accepted','payload_ok':value==b'public payload','timestamp_ok':at==stamp and at.tzinfo is not None}
        if mode.endswith('unsafe'):
            valid,value=serializer.loads_unsafe(signed,max_age=limit)
            return {'result':'accepted' if valid else 'unsafe-expired','payload_ok':value==payload}
        value=serializer.loads(signed,max_age=limit,return_timestamp=case.get('return_timestamp',False))
        at_ok=True
        if case.get('return_timestamp'):value,at=value;at_ok=at==stamp and at.tzinfo is not None
        return {'result':'accepted','payload_ok':value==payload,'timestamp_ok':at_ok}
    except SignatureExpired as error:
        expected_payload=b'public payload' if mode=='signer' else None
        return {'result':'expired','metadata_ok':error.date_signed==stamp and error.date_signed.tzinfo is not None
                and (expected_payload is None or error.payload==expected_payload)}
    except BadSignature:return {'result':'bad-signature'}
    except Exception as error:return {'result':'error','error':type(error).__name__,'detail':str(error)[:250]}


def public():
    rows=[]
    for case in json.loads(Path('_aiwork_public.json').read_bytes()):
        actual=observe(case)
        passed=actual['result']==case['expected'] and all(v for k,v in actual.items() if k.endswith('_ok'))
        rows.append({'id':case['id'],'passed':passed,'expected':case['expected'],'observed':actual})
    result={'passed':sum(r['passed'] for r in rows),'total':len(rows),'cases':rows}
    print(json.dumps(result));return 0 if result['passed']==result['total'] else 1


def interfaces():
    from itsdangerous import TimestampSigner,TimedSerializer
    rows=[]
    for fn in (TimestampSigner.unsign,TimestampSigner.validate,TimedSerializer.loads,TimedSerializer.loads_unsafe):
        for item in [fn,*typing.get_overloads(fn)]:
            annotation=typing.get_type_hints(item)['max_age']
            rows.append({'function':fn.__qualname__,'duration_annotated':timedelta in typing.get_args(annotation)})
    print(json.dumps(rows));return 0 if all(r['duration_annotated'] for r in rows) else 1


def main():
    action=sys.argv[1]
    if action=='public':return public()
    if action=='interfaces':return interfaces()
    if action=='sealed':print(json.dumps(observe(json.loads(sys.stdin.read()))));return 0
    if action=='syntax':
        for p in Path('src').rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
        print('Production syntax passes');return 0
    if action in {'upstream','authored'}:
        import pytest
        authored=Path('tests/test_itsdangerous/test_timedelta_max_age.py')
        if action=='authored' and not authored.is_file():print('Required authored tests missing');return 1
        paths=[str(authored)] if action=='authored' else ['tests']
        if action=='upstream' and authored.exists():paths+=['--ignore='+str(authored)]
        return pytest.main(['-q','-p','no:cacheprovider',*paths])
    raise ValueError('unsupported frozen check')


if __name__=='__main__':raise SystemExit(main())
