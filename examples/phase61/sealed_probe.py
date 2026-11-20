"""Generic black-box protocol only; future sealed inputs are never staged here."""
import asyncio
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path.cwd()))
import httpx
from httpx._utils import URLPattern
assert Path(httpx.__file__).resolve().is_relative_to(Path.cwd().resolve())

case=json.load(sys.stdin)
if case['mode']=='match':
    result=URLPattern(case['pattern']).matches(httpx.URL(case['url']))
elif case['mode']=='order':
    result=[value.pattern for value in sorted(map(URLPattern,case['patterns']))]
elif case['mode']=='client':
    def transport(label):return httpx.MockTransport(lambda request:httpx.Response(200,text=label))
    mounts={key:transport(label) for key,label in case['mounts'].items()}
    if case.get('async',False):
        async def evaluate():
            async with httpx.AsyncClient(mounts=mounts,transport=transport('fallback'),trust_env=False) as client:
                return [(await client.get(url)).text for url in case['urls']]
        result=asyncio.run(evaluate())
    else:
        with httpx.Client(mounts=mounts,transport=transport('fallback'),trust_env=False) as client:
            result=[client.get(url).text for url in case['urls']]
else:raise ValueError('unknown sealed protocol')
print(json.dumps(result,sort_keys=True,separators=(',',':')))
