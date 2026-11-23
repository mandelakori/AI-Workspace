import hashlib,json
from pathlib import Path
from jinja2 import __version__,StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
env=SandboxedEnvironment(undefined=StrictUndefined)
def fail(message): raise ValueError(message)
env.globals['raise_exception']=fail
source=Path('pinned.jinja').read_bytes()
template=env.from_string(source.decode())
results={}
for path in sorted(Path('.').glob('*-request.json')):
    body=json.loads(path.read_bytes())
    for msg in body['messages']:
        for tool in msg.get('tool_calls',[]):
            tool['function']['arguments']=json.loads(tool['function']['arguments'])
    mode=body['chat_template_kwargs']['enable_thinking']
    prompt=template.render(messages=body['messages'],tools=body['tools'],add_generation_prompt=True,enable_thinking=mode)
    suffix=prompt.rsplit('<|im_start|>assistant',1)[-1]
    assert suffix=='\n<think>\n' if mode else suffix=='\n<think>\n\n</think>\n\n'
    assert all(tool['function']['name'] in prompt for tool in body['tools'])
    if path.stem.startswith('continuation'):
        assert '<function=checks_focus>' in prompt and 'scope fixture content' in prompt
    results[path.stem]={'enabled':mode,'suffix':suffix,'tool_schema_and_continuation_valid':True}
print(json.dumps({'jinja':__version__,'template_sha256':hashlib.sha256(source).hexdigest(),'results':results,'generation_requests':0}))
