
import hashlib,json
from pathlib import Path
import jinja2
from jinja2.sandbox import SandboxedEnvironment
env=SandboxedEnvironment()
def fail(message):raise jinja2.TemplateError(message)
env.globals['raise_exception']=fail
template=env.from_string(Path('pinned.jinja').read_text())
results=[]
for vector in json.loads(Path('vectors.json').read_bytes()):
    try:
        rendered=template.render(**vector['body'],add_generation_prompt=True,enable_thinking=False)
        assert not vector.get('error'), 'expected rejection did not occur'
        assert all(s in rendered for s in vector.get('required',[])), 'instruction lost'
        results.append({'name':vector['name'],'accepted':True,'rendered_sha256':hashlib.sha256(rendered.encode()).hexdigest()})
    except jinja2.TemplateError as error:
        assert vector.get('error') and vector['error'] in str(error), str(error)
        results.append({'name':vector['name'],'accepted':False,'expected_error':str(error)})
print(json.dumps({'renderer':'Jinja2 '+jinja2.__version__,'model_tokens_generated':0,'results':results}))
