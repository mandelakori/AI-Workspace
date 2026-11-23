"""Controller-only semantic novelty key; never copied into worker inputs."""
import hashlib
import json
from datetime import timedelta


def fingerprint(case):
    api=case['api'].replace('serializer','timed')
    if api not in {'signer','validate','timed','timed-unsafe','urlsafe','urlsafe-unsafe'} or type(case['age']) is not int:
        raise ValueError('unsupported evaluation API or noninteger timestamp age')
    if case.get('unlimited'):limit={'kind':'none'}
    elif 'delta' in case:
        duration=timedelta(**case['delta'])
        limit={'kind':'duration','microseconds':(duration.days*86400+duration.seconds)*1000000+duration.microseconds}
    elif 'unsupported' in case:limit={'kind':case['unsupported'],'value':case.get('value')}
    else:limit={'kind':type(case['seconds']).__name__,'value':case['seconds']}
    value={'api':api,'age':case['age'],'limit':limit,'tamper':case.get('tamper',False),'rotation':case.get('rotation',False),'separator':case.get('separator','.')}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
