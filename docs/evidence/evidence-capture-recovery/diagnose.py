"""Open offline diagnostics, not sealed acceptance or a production correction."""
import sys,json,inspect,typing
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path('src').resolve()))
from itsdangerous import TimestampSigner,TimedSerializer,URLSafeTimedSerializer

clock=[1700000000.125]
class ClockSigner(TimestampSigner):
    def get_timestamp(self):return int(clock[0])

def observe(api,limit,elapsed,phase=.125):
    clock[0]=1700000000+phase
    signer=ClockSigner('diagnostic-key')
    serializer=(URLSafeTimedSerializer if api.startswith('urlsafe') else TimedSerializer)('diagnostic-key',signer=ClockSigner)
    signed=signer.sign(b'payload') if api in {'signer','validate'} else serializer.dumps('payload')
    clock[0]+=elapsed
    try:
        if api=='validate':return {'result':signer.validate(signed,max_age=limit)}
        if api=='signer':signer.unsign(signed,max_age=limit)
        elif api.endswith('unsafe'):return {'result':serializer.loads_unsafe(signed,max_age=limit)[0]}
        else:serializer.loads(signed,max_age=limit)
        return {'result':'accepted'}
    except Exception as error:return {'error':type(error).__name__}

rows=[]
for api in ('signer','validate','serializer','serializer-unsafe','urlsafe','urlsafe-unsafe'):
    for label,limit,elapsed,phase in [('zero-equality',timedelta(0),0,.125),
            ('sleep-low-phase',timedelta(seconds=1),1.1,.125),('sleep-high-phase',timedelta(seconds=1),1.1,.95),
            ('integer-equality',1,1.1,.125),('integer-expired',1,2.1,.125)]:
        rows.append({'api':api,'probe':label,'observed':observe(api,limit,elapsed,phase)})
class FloatOnly:
    def __float__(self):return 100.
for label,limit in [('numeric-string','100'),('numeric-bytes',b'100'),('nan-string','nan'),
        ('infinite-string','inf'),('nonnumeric-string','invalid'),('float-only-object',FloatOnly())]:
    rows.append({'api':'signer','probe':label,'observed':observe('signer',limit,50)})
for limit,age in [(2**53+3,2**53+4),(2**53+1,2**53+1)]:
    clock[0]=0;signer=ClockSigner('diagnostic-key');token=signer.sign(b'payload');clock[0]=age
    try:signer.unsign(token,max_age=limit);v={'result':'accepted'}
    except Exception as error:v={'error':type(error).__name__}
    rows.append({'api':'signer','probe':'large-integer','limit':limit,'age':age,'observed':v})
interfaces=[]
for fn in (TimestampSigner.unsign,TimestampSigner.validate,TimedSerializer.loads,TimedSerializer.loads_unsafe):
    for item in [fn,*typing.get_overloads(fn)]:
        a=typing.get_type_hints(item)['max_age']
        interfaces.append({'name':fn.__qualname__,'duration':timedelta in typing.get_args(a),'parameters':str(inspect.signature(item))})
try:TimestampSigner('diagnostic-key').sep.encode();separator='unexpected_success'
except Exception as error:separator=type(error).__name__
print(json.dumps({'kind':'OPEN_OFFLINE_DIAGNOSTICS_NOT_SEALED_ACCEPTANCE','probes':rows,'interfaces':interfaces,
                  'separator_type':type(TimestampSigner('diagnostic-key').sep).__name__,'separator_encode':separator}))
