"""Audit only saved execution receipts for the approved comparison."""
import collections
import hashlib
import json
from pathlib import Path
import re

PAIR = Path('.aiwork/a100-thinking-diagnostic/pair')
BASE = PAIR.parent
def read(p):
    return json.loads(p.read_bytes())

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def rows(p):
    return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]

def inspect(mode):
    root = PAIR/mode
    attempt, = (root/'state/runs').glob('*/attempt-*')
    manifest = read(root/'manifest.json')
    finished = read(root/'engineering-closed.json')
    start = read(root/'execution-started.json')['started']
    result = read(root/'engineering-result.json')
    worker = read(attempt/'execution-receipt.json')
    context = read(attempt/'execution-context.json')
    gate = read(attempt/'provider-gate.json')
    check = read(attempt/'checkpoint.json')
    assert result['status']=='verified' and check['public']['compiled'] and check['public']['passed_cases']==5
    request_rows = []
    for req in gate['requests']:
        n=req['request']
        f=read(attempt/f'provider-forwarded-{n:03}.json')
        orig=read(attempt/f'provider-request-{n:03}.json')
        assert req['forwarded'] and req['response_complete'] and req['upstream_status']==200 and req['passed']
        assert f['model']==manifest['profile']['model'] and f.get('max_completion_tokens',f.get('max_tokens'))==4096
        assert all(f[k]==v for k,v in manifest['generation'].items()) and 'reasoning_effort' not in f
        assert {d['function']['name'] for d in f['tools']}==set(gate['required'])
        assert f['tools']==orig['tools']
        assert len([x for x in f['messages'] if x['role']=='system'])==1 and f['messages'][0]['role']=='system'
        assert json.loads(f['messages'][0]['content'].split('\n',2)[1])==context['contract']
        init=orig['messages'][0]['role']=='system'
        assert f['messages'][1:]==orig['messages'][int(init):]
        if init:assert orig['messages'][0]['content'] in f['messages'][0]['content']
        text=(attempt/f'provider-response-{n:03}.sse').read_text(encoding='utf-8').splitlines()
        replies=[c for line in text if line.startswith('data: ') and line!='data: [DONE]'
                 for c in json.loads(line[6:]).get('choices',[])]
        fr=[c['finish_reason'] for c in replies if c.get('finish_reason')]
        assert len(fr)==1 and 'data: [DONE]' in text
        dd=[c.get('delta',{}) for c in replies]
        reason=[x.get('reasoning_content') for x in dd if x.get('reasoning_content')]
        visible=''.join(x.get('content') or '' for x in dd)
        ids=[c['id'] for d in dd for c in d.get('tool_calls',[]) if c.get('id')]
        usage=req['usage']
        request_rows.append({'request':n,'finish':fr[0],'tool_call_ids':ids,'seconds':req['elapsed'],
                             'reasoning_payload_bytes':sum(len(v.encode()) for v in reason),
                             'reasoning_payload_deltas':len(reason),'inline_thinking_tags':bool(re.search(r'</?think>',visible)),
                             'reasoning_tokens':usage.get('completion_tokens_details',{}).get('reasoning_tokens'),
                             'cache_tokens':usage.get('prompt_tokens_details',{}).get('cached_tokens'),'usage':usage})
    cap=worker['evidence']
    for name,record in cap['files'].items():
        p=attempt/name
        assert record['complete'] and p.stat().st_size==record['bytes'] and digest(p)==record['sha256']
    assert cap['captured_bytes']==sum(x['bytes'] for x in cap['files'].values())
    calls=rows(attempt/'mcp.jsonl')
    events=[x for x in rows(attempt/'agent.jsonl') if x.get('type')=='tool_use']
    ids={call_id:r['request'] for r in request_rows for call_id in r['tool_call_ids']}
    def milestone(tool, criterion):
        row=next(x for x in calls if x['tool']==tool and criterion(x))
        event,=[x for x in events if x['part']['tool']==f'checks_{tool}']
        part=event['part']; state=part['state']
        time=state['time']
        assert state['status']=='completed'
        return {'operation':row['call'],'model_request':ids[part['id']],
                'started_seconds':round(time['start']/1000-start,3),'completed_seconds':round(time['end']/1000-start,3),
                'passed':row.get('passed')}
    api_tokens={key:sum(q['usage'][key] for q in request_rows) for key in ('prompt_tokens','completion_tokens','total_tokens')}
    cache=[q['cache_tokens'] for q in request_rows if q['cache_tokens'] is not None]
    reasons=[q['reasoning_tokens'] for q in request_rows if q['reasoning_tokens'] is not None]
    emitted=[r for r in request_rows if r['reasoning_payload_bytes'] or r['inline_thinking_tags']]
    assert bool(emitted)==(mode=='on')
    metrics=read(attempt/'agent-metrics.json')
    return {'mode':mode,'approval':(root/'manifest.sha256').read_text().strip(),'job':attempt.parent.name,
            'hashes_verified':len(cap['files']),'capture_bytes':cap['captured_bytes'],'settings_verified_requests':len(request_rows),
            'reasoning_emission_requests':len(emitted),'reasoning_payload_bytes':sum(q['reasoning_payload_bytes'] for q in request_rows),
            'reasoning_payload_deltas':sum(q['reasoning_payload_deltas'] for q in request_rows),
            'provider_reasoning_tokens':sum(reasons) if reasons else None,'provider_reasoning_counter_receipts':len(reasons),
            'api_tokens':api_tokens,'cache_tokens':sum(cache) if cache else None,'cache_counter_receipts':len(cache),
            'sdk_tokens':metrics['tokens'],'gpu_samples':metrics['gpu_samples'],
            'operations':dict(collections.Counter(row['tool'] for row in calls)),'operations_total':len(calls),
            'accepted_edits':sum(row.get('applied',False) for row in calls),
            'rejected_edits':sum(row['tool']=='edit' and not row.get('applied') for row in calls),
            'tool_errors':metrics['tool_errors'],'first_applied_edit':milestone('edit',lambda x:x.get('applied')),
            'first_public_check':milestone('check',lambda x:x['index']==0),'phase_limits':manifest['limits'],
            'worker':{k:worker[k] for k in ('status','elapsed','raw_exit_code','timed_out','cleanup_passed','provider_gate_passed')},
            'resource_usage':worker['resources'],'engineering_seconds':round(finished['closed_at']-start,3),
            'peak_prompt':max(q['usage']['prompt_tokens'] for q in request_rows),'finish_reasons':dict(collections.Counter(q['finish'] for q in request_rows)),
            'requests':request_rows,'controller_public_passed':check['public']['passed_cases'],'source':read(root/'frozen.json'),
            'frozen':finished['frozen_sha256'],'warm_seconds':read(root/'warm-process.json')['elapsed'],
            'work_seconds':read(root/'work-process.json')['elapsed']}
if __name__=='__main__':
    result={mode:inspect(mode) for mode in ('off','on')}
    (BASE/'live-metrics.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    for mode,record in result.items():
        print(mode,json.dumps({k:v for k,v in record.items() if k not in ('requests','resource_usage','gpu_samples')}))
