"""Offline verification of this failed trial's published receipts; no inference."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
load=lambda name:json.loads((root/name).read_bytes())
for name,expected in load('evidence-hashes.json').items():
    raw=(root/name).read_bytes()
    assert len(raw)==expected['bytes']
    assert hashlib.sha256(raw).hexdigest()==expected['sha256'],name
manifest=load('manifest.json')
approved='150b82b49ebf8235fb0482d70bbcb75d3e3e1556334dd44406f5af3d69fab4af'
assert hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()==approved
assert load('operator-approval.json')=={'approval_digest':approved,'authorize':['a100-existing'],'operator_approved':True}
assert load('warm-readiness.json')['identity']==manifest['endpoint_identity']
template=load('preflight-endpoint.json')['props']['data']['chat_template']
assert hashlib.sha256(template.encode()).hexdigest()==manifest['endpoint_identity']['chat_template_sha256']
before=load('attempt/provider-request-001.json')
after=load('attempt/provider-forwarded-001.json')
assert [m['role'] for m in before['messages']]==['system','user']
assert [m['role'] for m in after['messages']]==['system','system','user']
assert after['messages'][1:]==before['messages']
assert 'System message must be at the beginning.' in load('attempt/provider-response-001.sse')['error']['message']
assert 'not loop.first' in (root/'template-guard.txt').read_text()
gate=load('attempt/provider-gate.json')
assert len(gate['requests'])==2 and sum(r['forwarded'] for r in gate['requests'])==1
assert gate['requests'][0]['upstream_status']==500
assert gate['requests'][0]['missing']==[] and gate['requests'][0]['unexpected']==[]
assert after['max_completion_tokens']==4096
assert after['reasoning_effort']=='none' and after['chat_template_kwargs']=={'enable_thinking':False}
check=load('post-run-check.json')
assert check['worker_workspace_equals_frozen_input'] and check['input_still_matches']
assert not check['candidate_frozen'] and not check['sealed_cases_created']
assert not check['local_forward_port_listening'] and all(not p['running'] for p in check['owned_processes'])
assert load('quarantine-guard-check.json')['grading_guard_rejected']
assert load('trial-budget.json')['phases']['grade']['status']=='PENDING'
assert load('outcome.json')['cleanup_passed']
print('Verified: one forwarded HTTP 500, duplicate-system incompatibility, no edits/grade, cleanup passed.')
