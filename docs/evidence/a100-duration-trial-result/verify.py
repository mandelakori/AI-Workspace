"""Verify this outcome offline. No model, source execution or source edits."""
import collections
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

root=Path(__file__).resolve().parent
load=lambda name:json.loads((root/name).read_bytes())
for name,expected in load('evidence-hashes.json').items():
    raw=(root/name).read_bytes()
    assert len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256'],name
m=load('manifest.json');approved='0534cc79d14abfe300f187b5ebf7a4728d89106558a925f16cce3d75fa214644'
assert hashlib.sha256(json.dumps(m,sort_keys=True,separators=(',',':')).encode()).hexdigest()==approved
assert load('operator-approval.json')=={'approval_digest':approved,'authorize':['a100-existing'],'operator_approved':True}
g=load('attempt/provider-gate.json');assert len(g['requests'])==51 and all(q['forwarded'] for q in g['requests'])
assert len({q['body_sha256'] for q in g['requests']})==51
assert all(q['upstream_status']==200 for q in g['requests'])
assert g['requests'][0]['usage']['completion_tokens']==114
assert g['requests'][-1]['error']=='TimeoutError' and 'usage' not in g['requests'][-1]
for p in sorted((root/'attempt').glob('provider-forwarded-*.json')):
    out=json.loads(p.read_bytes());before=load('attempt/'+p.name.replace('forwarded','request'))
    assert out['messages'][0]['role']=='system' and sum(x['role']=='system' for x in out['messages'])==1
    assert 'AI-WORKSPACE ACTIVE TASK CONTRACT' in out['messages'][0]['content']
    assert out['messages'][0]['content'].endswith(before['messages'][0]['content'])
    assert out['messages'][1:]==before['messages'][1:]
    assert {k:v for k,v in out.items() if k!='messages'}=={k:v for k,v in before.items() if k!='messages'}
rows=[json.loads(l) for l in (root/'attempt/mcp.jsonl').read_text().splitlines()]
edits=[r for r in rows if r['tool']=='edit'];assert len(edits)==37 and not any(r.get('applied') for r in edits)
assert collections.Counter(r['code'] for r in edits)=={'anchor_mismatch':12,'ambiguous_anchor':24,'invalid_anchor':1}
assert [r['index'] for r in rows if r['tool']=='check']==[4]
with ZipFile(root.parent/'milestone-e-a100/itsdangerous-pinned-source.zip') as archive:
    source=archive.read('src/itsdangerous/timed.py')
assert hashlib.sha256(source).hexdigest()==m['input_inventory']['src/itsdangerous/timed.py']['sha256']
assert source.count(b'\r\n')==228
assert sum(r['code']=='anchor_mismatch' and source.count(r['arguments']['old'].replace('\n','\r\n').encode())==1 for r in edits)==11
assert load('retained-workspace-check.json')['inventory_equals_approved_input']
assert load('post-run-0534.json')['grading_guard_rejected']
assert load('post-run-0534.json')['post_backend_idle']
assert load('trial-budget.json')['quarantined'] and load('trial-budget.json')['phases']['grade']['status']=='PENDING'
assert load('attempt/execution-receipt.json')['cleanup_passed']
print('Verified: first inference/compaction succeed; 37 edits rejected, timeout/quarantine, no source delivery or grading.')
