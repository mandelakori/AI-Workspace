"""One approval-gated A100/OpenCode trial; no inference during prepare/validate."""
from dataclasses import asdict, replace
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import time
from urllib.request import build_opener, ProxyHandler
from urllib.parse import urlsplit

# Bind this review entrypoint to the checked-out controller, not an older wheel
# elsewhere on sys.path. This path never comes from the untrusted target.
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from aiwork.changes import delta, validate_changes
from aiwork.controller import Controller
from aiwork.harness import opencode_path, request_options
from aiwork.http import NoRedirect
from aiwork.httpx_benchmark import digest, file_hash, implementation
from aiwork.inference import Inference
from aiwork.lock import file_lock
from aiwork.remote import a100_session, ssh_probe
from aiwork.router import routes
from aiwork.schema import Check, Config, Profile, Task
from aiwork.selection import compare
from aiwork.trial_budget import FILE, create, current, run_phase, write
from aiwork.verify import invoke, runner_status
from aiwork.workspace import inventory, snapshot
from aiwork.evidence_capture import DEFAULT_CAPTURE_BYTES,DEFAULT_HEADROOM_BYTES
sys.path.insert(0,str(Path(__file__).resolve().parent))
from case_identity import fingerprint

ASSETS=Path(__file__).resolve().parent
REPO=ASSETS.parents[1]
COMMIT='672971d66a2ef9f85151e53283113f33d642dabd'
ARM='a100-existing'
LIMITS={'warm':20,'work':900,'grade':120}
PATHS=('src/itsdangerous/timed.py','docs/timed.rst','tests/test_itsdangerous/test_timedelta_max_age.py')
ACTIONS=('public_original','public_expanded','upstream','authored','interfaces','documentation','syntax','acceptance')
PRISTINE_HASH='c363f1e01fcfdcfe0e0568db82a92f305e76d5f311d9392b7be4bd54a3e2da5f'
WORKER={'attempts':1,'attempt_seconds':720,'operations':96,'edit_reserve':8,'public_test_reserve':8,
        'model_requests':64,'compactions':4,'planner_requests':0,'context':65536,'min_context':32768}
PUBLIC={'original_cases':12,'additional_cases':36,'combined_cases':48,'mandatory_actions':list(ACTIONS[:-1]),
        'worker_acceptance_call_required':True,'successful_harness_closure_required':True,'all_gates_before_freeze':True}


def config(root,manifest):
    return Config(root/'state',(Profile(**manifest['profile']),),ssh=manifest['ssh'],
        opencode=manifest['opencode']['path'],verification_image=manifest['runner'],
        execution_state=Path(manifest['execution_state']))


def identity(props):
    return {k:props[k] for k in ('model_path','model_ftype','build_info','total_slots')}|{
        'context':props['default_generation_settings']['n_ctx'],
        'chat_template_sha256':hashlib.sha256(props['chat_template'].encode()).hexdigest()}


def ready_identity(manifest,props,slots):
    if (identity(props)!=manifest['endpoint_identity'] or not isinstance(slots,list)
            or len(slots)!=props['total_slots'] or not slots
            or any(s.get('is_processing') is not False or s.get('n_ctx',0)<65536 for s in slots)):
        raise ValueError('A100 identity/capacity changed, unknown, or shared slot busy; no inference')


def checks():return tuple(Check(('python','_aiwork_checks.py',a),timeout=45) for a in ACTIONS)


def read_json(url):
    # llama.cpp /slots returns a JSON array; the generic object-only client is
    # deliberately unchanged. No redirects, proxies, generation routes or writes.
    parsed=urlsplit(url)
    if (parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.port
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {'/health','/v1/models','/props','/slots'}):
        raise ValueError('read-only loopback inventory route required')
    with build_opener(ProxyHandler({}),NoRedirect()).open(url,timeout=3) as response:
        raw=response.read(2_097_153)
        if len(raw)>2_097_152:raise ValueError('inventory response too large')
        return json.loads(raw)


def inspect_endpoint(base_config,out):
    out=out.resolve();out.mkdir(exist_ok=False)
    cfg=Config.load(base_config);p=next(p for p in cfg.profiles if p.id==ARM)
    if p.managed or p.location!='a100':raise ValueError('existing unmanaged A100 only')
    cfg=replace(cfg,state=out/'state');cfg.state.mkdir()
    data={'gpu':ssh_probe(cfg.ssh['alias']),'generation_requests':0,'remote_mutations':False,'at':time()}
    owned=None
    try:
        with a100_session(cfg,p,dispatch=False,timeout=15) as owned:
            data['owned_forward_pid']=owned.pid
            for route in ('health','v1/models','props','slots'):
                data[route]={'code':200,'data':read_json(p.endpoint.removesuffix('/v1')+'/'+route)}
    finally:
        data['owned_forward_closed']=owned is not None and owned.poll() is not None
        write(out/'endpoint.json',data)
    if not data['owned_forward_closed']:raise RuntimeError('owned forward cleanup failed')
    return data


def task(root,manifest):
    objective=(root/'input/FEATURE.md').read_text()+'\n\n'+(root/'input/PUBLIC-VERIFICATION.md').read_text()
    return Task(objective,root/'input','agent','milestone-e-itsdangerous-final',
        tuple(sorted({p.split('/')[0] for p in manifest['input_inventory']})),(),(checks()[-1],),
        location='a100',profile=ARM,complexity=4,mode='engineering',write_roots=PATHS,
        commands=checks(),baseline_check=True,min_context=32768,timeout=720,attempts=1,
        tool_operations=96,edit_reserve=8,public_test_reserve=8,model_requests=64,compaction_limit=4)


def prepare(source,base_config,endpoint,root,image):
    root=root.resolve();root.mkdir(exist_ok=False)
    source=source.resolve(strict=True)
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if commit!=COMMIT or subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip():
        raise ValueError('expected clean pinned ItsDangerous source')
    cfg=Config.load(base_config);profile=next(p for p in cfg.profiles if p.id==ARM)
    live=json.loads(endpoint.read_bytes());props=live['props']['data']
    if (not live['health']['data']['status']=='ok' or props['model_path']!=profile.model
            or props['model_ftype']!='Q6_K' or props['default_generation_settings']['n_ctx']<65536):
        raise ValueError('expected healthy existing A100 model and context')
    if profile.managed or profile.location!='a100' or profile.harness!='opencode' or profile.engine!='llamacpp':
        raise ValueError('existing unmanaged A100 OpenCode profile required')
    profile=replace(profile,context=65536,output_tokens=4096,temperature=0,seed=1729,reasoning_effort='none')
    profile.validate()
    image_id=runner_status(root,image)['image_id'];binary=opencode_path(cfg.opencode)
    if not image_id or not binary:raise ValueError('existing offline verifier and OpenCode required')
    pristine=snapshot(source,root/'source',())
    if digest(pristine)!=PRISTINE_HASH:raise ValueError('original pristine byte inventory changed')
    snapshot(root/'source',root/'input',())
    for src,dst in [('FEATURE.md','FEATURE.md'),('PUBLIC-VERIFICATION.md','PUBLIC-VERIFICATION.md'),
                    ('checks.py','_aiwork_checks.py'),('original_checks.py','_aiwork_original_checks.py'),
                    ('public-cases.json','_aiwork_public.json'),('expanded-cases.json','_aiwork_expanded.json')]:
        (root/'input'/dst).write_bytes((ASSETS/src).read_bytes())
    write(root/'input/_aiwork_contract.json',{'original_doc_sha256':pristine['docs/timed.rst']['sha256']})
    manifest={'schema':1,'kind':'milestone-e-final-itsdangerous','status':'PREPARED_NOT_AUTHORIZED',
        'execution_allowed':False,'arm':ARM,'bundle':str(root),'repository':'https://github.com/pallets/itsdangerous',
        'commit':COMMIT,'pristine_inventory':pristine,'input_inventory':inventory(root/'input'),
        'profile':asdict(profile),'request_options':request_options(profile),
        'ssh':{'alias':cfg.ssh['alias'],'remote_port':cfg.ssh['remote_port']},
        'endpoint_identity':identity(props),'endpoint_evidence_sha256':file_hash(endpoint),
        'opencode':{'path':binary,'sha256':file_hash(Path(binary))},'runner':image_id,
        'implementation_sha256':implementation(),'asset_hashes':{p.name:file_hash(p) for p in sorted(ASSETS.iterdir()) if p.is_file()},
        'execution_state':str((REPO/'.aiwork').resolve()),'phase_limits':LIMITS,
        'capture_policy':{'payload_bytes':DEFAULT_CAPTURE_BYTES,'disk_headroom_bytes':DEFAULT_HEADROOM_BYTES,'metadata_bytes':16777216,'request_attribution_limit':1024},
        'public_protocol':PUBLIC,'worker':WORKER,
        'permissions':{'write_paths':list(PATHS),'tools':['checks_focus','checks_edit','checks_check','checks_diff'],
            'inference':'existing A100 only through existing SSH alias','verification':'local offline Docker only',
            'cloud_lifecycle':False,'remote_writes':False,'service_changes':False,'native_shell':False,'fallback':False},
        'cache_protocol':'No warmup generation or cache/slot clearing; record existing shared server state and returned usage. No cold/cache-equality claim.',
        'independent_evaluation':{'cases':24,'created_after_freeze':True,'worker_feedback':False,
            'categories':['integer/None compatibility','fractional/zero/negative/multi-day durations','future/expired/signature metadata',
                          'malformed signatures','serializer/URL-safe/unsafe paths','key rotation/custom signer'],
            'expected_outputs_mounted':False,'sealed_results_select_candidate':False,'expanded_payload_required':True},
        'completion':'Model source edit; worker acceptance call; original 12/12 and combined 48/48 public; upstream, deterministic authored tests, annotations/docstrings/documentation and syntax all pass before freeze; 24/24 new independent cases afterwards. No guidance.',
        'stop_policy':'Any interruption, catalog/provider/harness failure or failed owned cleanup quarantines; no retry/resume. Clean quota exhaustion is partial, never automatic success.',
        'selection':'Final export versus baseline using identical combined public cases; preserve all prior passes. Every mandatory gate and clean completed harness required before any freeze; incomplete work retained without final grading.',
        'after_trial':'Stop and assess Milestone E; no automatic ItsDangerous repetition or new campaign.'}
    forbidden=set(json.loads((ASSETS/'diagnostic-exclusions.json').read_bytes())['fingerprints'])
    for path in ['public-cases.json','expanded-cases.json']:
        forbidden.update(fingerprint(case) for case in json.loads((ASSETS/path).read_bytes()))
    write(root/'evaluation-exclusions.json',{'fingerprints':sorted(forbidden)})
    manifest['evaluation_exclusions_sha256']=file_hash(root/'evaluation-exclusions.json')
    baseline=evaluate(root,root/'input',root/'baseline',manifest)
    if baseline['original_passed']!=3 or baseline['passed_cases']!=22 or baseline['total']!=48 or not baseline['compiled'] or not baseline['upstream_passed']:
        raise ValueError('unmodified baseline did not reproduce 3/12 plus upstream success')
    manifest['baseline']=baseline
    t=task(root,manifest);t.validate();r=routes(t,(profile,),{})
    if len(r)!=1 or r[0].profile.id!=ARM:raise ValueError('A100 route not exclusive')
    manifest['route']={'profile':ARM,'reason':r[0].reason,'local_fallback':False}
    write(root/'manifest.json',manifest);(root/'manifest.sha256').write_text(digest(manifest)+'\n')
    write(root/'operator-approval.example.json',{'approval_digest':digest(manifest),'authorize':[ARM],'operator_approved':False})
    return manifest


def load(root):
    m=json.loads((root/'manifest.json').read_bytes())
    if digest(m)!=(root/'manifest.sha256').read_text().strip():raise ValueError('manifest digest mismatch')
    if m['implementation_sha256']!=implementation():raise ValueError('controller implementation changed')
    if m['asset_hashes']!={p.name:file_hash(p) for p in sorted(ASSETS.iterdir()) if p.is_file()}:
        raise ValueError('trial implementation or frozen assets changed')
    if inventory(root/'input')!=m['input_inventory'] or inventory(root/'source')!=m['pristine_inventory']:
        raise ValueError('frozen source changed')
    if digest(m['pristine_inventory'])!=PRISTINE_HASH:raise ValueError('original pristine inventory changed')
    if file_hash(Path(m['opencode']['path']))!=m['opencode']['sha256']:raise ValueError('OpenCode changed')
    if file_hash(root/'evaluation-exclusions.json')!=m['evaluation_exclusions_sha256']:raise ValueError('evaluation exclusion policy changed')
    if m['capture_policy']!={'payload_bytes':DEFAULT_CAPTURE_BYTES,'disk_headroom_bytes':DEFAULT_HEADROOM_BYTES,'metadata_bytes':16777216,'request_attribution_limit':1024}:
        raise ValueError('capture policy changed')
    p=Profile(**m['profile']);p.validate()
    if (m['kind']!='milestone-e-final-itsdangerous' or m['arm']!=ARM or m['phase_limits']!=LIMITS
            or p.id!=ARM or p.location!='a100' or p.managed or p.harness!='opencode' or p.local_calibration):
        raise ValueError('unsupported A100 trial contract')
    if (m['worker']!=WORKER or m['public_protocol']!=PUBLIC or (p.context,p.output_tokens,p.temperature,p.seed,p.reasoning_effort)!=(65536,4096,0,1729,'none')
            or m['permissions']['write_paths']!=list(PATHS) or p.engine!='llamacpp' or p.model!=m['endpoint_identity']['model_path'] or m['request_options']!=request_options(p)):
        raise ValueError('reviewed resource/public/scope protocol changed')
    return m


def authorize(root,approval):
    m=load(root);grant=json.loads(approval.read_bytes())
    if grant!={'approval_digest':digest(m),'authorize':[ARM],'operator_approved':True}:
        raise ValueError('separate exact operator approval required')
    return m


def evaluate(root,source,destination,m):
    destination.mkdir(parents=True,exist_ok=False);work=destination/'workspace';snapshot(source,work,())
    validate_changes(delta(m['input_inventory'],inventory(work)),PATHS)
    before=inventory(work)
    receipt=invoke(checks()[-1],work,destination/'home',m['runner']);write(destination/'acceptance.json',receipt)
    unchanged=inventory(work)==before
    try:results=json.loads(receipt['stdout'])['results']
    except (ValueError,KeyError):results={a:{'passed':False} for a in ACTIONS[:-1]}
    for action,value in results.items():write(destination/(action+'.json'),value)
    public=results['public_expanded'];original=results['public_original']
    return {'corpus_sha256':digest([m['input_inventory'][p]['sha256'] for p in ['_aiwork_public.json','_aiwork_expanded.json']]),'runner':m['runner'],
        'total':48,'compiled':results['syntax']['passed'],'passed_cases':public.get('passed_cases',0),
        'original_passed':original.get('passed_cases',0),'original_total':12,
        'missing':[] if (work/PATHS[2]).is_file() else [PATHS[2]],
        'cases':[{'case':i,'verdict':'pass' if r['passed'] else 'fail'} for i,r in enumerate(public.get('cases',[]),1)],
        'public':public,'upstream_passed':results['upstream']['passed'],
        'authored_passed':results['authored']['passed'],'interfaces_passed':results['interfaces']['passed'],
        'gates':{action:value['passed'] for action,value in results.items()},'verification_workspace_unchanged':unchanged,
        'all_gates_passed':unchanged and receipt['passed'] and all(v['passed'] for v in results.values())}


def warm(root,m):
    cfg=config(root,m);p=cfg.profiles[0]
    with a100_session(cfg,p,dispatch=False,timeout=15) as owned:
        Inference(p).ready();base=p.endpoint.removesuffix('/v1')
        props=read_json(base+'/props');slots=read_json(base+'/slots')
        ready_identity(m,props,slots)
        write(root/'warm-readiness.json',{'identity':identity(props),'slots':slots,'owned_forward_pid':owned.pid,'generation_requests':0})
    if owned.poll() is None:raise RuntimeError('owned forward cleanup failed')


def work(root,m):
    cfg=config(root,m);controller=Controller(cfg);result=controller.run_submitted(controller.submit_task(task(root,m)))
    write(root/'engineering-result.json',result)
    attempts=list(cfg.state.glob('runs/*/attempt-*'))
    if len(attempts)!=1:raise ValueError('one worker attempt required')
    attempt=attempts[0];receipt=json.loads((attempt/'execution-receipt.json').read_bytes())
    if receipt['status'] not in {'completed','resource_exhausted'} or not receipt['cleanup_passed']:
        raise RuntimeError('worker failed to close cleanly')
    candidate=evaluate(root,attempt/'workspace',root/'candidate-public',m)
    decision=compare(m['baseline'],candidate,protect_passing=True)
    calls=[json.loads(line) for line in (attempt/'mcp.jsonl').read_text().splitlines() if line.strip()]
    if not qualified(candidate,receipt,decision,calls,result):
        decision.update(accepted=False,reason='mandatory_acceptance_or_clean_worker_closure_incomplete')
    write(root/'selection.json',{'decision':decision,'candidate':candidate,'worker_receipt':receipt})
    if not decision['accepted']:
        write(root/'engineering-incomplete.json',{'at':time(),'reason':decision['reason'],'no_freeze_or_grade':True});return
    hashes=snapshot(root/'candidate-public/workspace',root/'frozen',())
    write(root/'frozen.json',{'inventory':hashes,'hash':digest(hashes),'frozen_at':time(),
        'accepted_model_source':True,'public_complete':candidate['passed_cases']==48,'all_gates_passed':True,
        'sealed_feedback_used':False})


def qualified(candidate,receipt,decision,calls,result):
    return (decision['accepted'] and receipt['status']=='completed' and receipt['cleanup_passed']
        and result['status']=='verified' and candidate['passed_cases']==48 and candidate['original_passed']==12
        and set(candidate['gates'])==set(ACTIONS[:-1]) and all(candidate['gates'].values()) and candidate['all_gates_passed']
        and any(row.get('applied') for row in calls if row['tool']=='edit')
        and any(row['tool']=='check' and row.get('index')==7 and row.get('passed') for row in calls))


def closed(root):
    state=json.loads((root/'state'/FILE).read_bytes())
    if state.get('quarantined') or state['phases']['work']['status']!='FINISHED' or (root/'quarantine.json').exists():
        raise ValueError('engineering did not close cleanly; no grading')
    frozen=json.loads((root/'frozen.json').read_bytes())
    if not frozen.get('all_gates_passed') or not frozen.get('accepted_model_source') or not frozen.get('public_complete'):
        raise ValueError('mandatory public closure missing; no grading')
    if inventory(root/'frozen')!=frozen['inventory']:raise ValueError('frozen candidate changed')
    return frozen


def run(root,approval):
    m=authorize(root,approval)
    if runner_status(root,m['runner'])['image_id']!=m['runner']:raise ValueError('frozen image unavailable')
    with file_lock(root/'run.lock'):
        if (root/'execution-started.json').exists():raise ValueError('trial consumed; no retry/resume')
        write(root/'execution-started.json',{'approval_digest':digest(m),'started':time()})
        (root/'operator-approval.json').write_bytes(approval.read_bytes())
        create(root/'state',digest(m),ARM,LIMITS,reviewed_caps=LIMITS,quotas={'sessions':1,'planner_requests':0})
    for phase in ('warm','work'):
        result=run_phase(root/'state',phase,[sys.executable,str(ASSETS/'trial.py'),'_'+phase,str(root)],REPO)
        write(root/(phase+'-process.json'),result)
        if result['code'] or result['timed_out'] or not result['cleanup']['passed']:
            write(root/'quarantine.json',{'phase':phase,'reason':'execution or owned cleanup failure'})
            raise RuntimeError('trial quarantined; no retry/resume')
    if (root/'engineering-incomplete.json').exists():return
    closed(root);write(root/'engineering-closed.json',{'at':time(),'next':'independently author 24 new sealed cases; do not reuse public or diagnostic inputs'})


def grade(root,m):
    frozen=closed(root);p=root/'private/cases.json';cases=json.loads(p.read_bytes())
    if any(case.get('expanded') is not True for case in cases):raise ValueError('final sealed evaluation requires the expanded payload schema')
    if len(cases)!=24 or len({c['id'] for c in cases})!=24 or p.stat().st_mtime<=frozen['frozen_at']:
        raise ValueError('24 fresh named sealed cases must be authored after freeze')
    strip=lambda c:{k:v for k,v in c.items() if k not in {'id','expected'}}
    payloads=[strip(c) for c in cases];hashes={digest(c) for c in payloads}
    semantic={fingerprint(c) for c in payloads}
    excluded=set(json.loads((root/'evaluation-exclusions.json').read_bytes())['fingerprints'])
    if len(hashes)!=24 or len(semantic)!=24 or semantic&excluded:raise ValueError('sealed inputs must be distinct and new relative to public and prior diagnostics')
    binding={'sha256':file_hash(p),'candidate':frozen['hash']};record=root/'sealed-input.json'
    if record.exists() and json.loads(record.read_bytes())!=binding:raise ValueError('sealed input changed')
    write(record,binding);results=[]
    for case,payload in zip(cases,payloads):
        result=invoke(Check(('python','_aiwork_checks.py','sealed'),timeout=10),root/'frozen',root/'grade-home',
            m['runner'],stdin=json.dumps(payload).encode(),sealed=True)
        try:ok=result['passed'] and json.loads(result['stdout'])==case['expected']
        except ValueError:ok=False
        results.append({'id':case['id'],'passed':ok,'raw':result})
        write(root/'sealed-results.json',binding|{'passed':sum(c['passed'] for c in results),'total':24,'cases':results})
    closed(root)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('inspect');p.add_argument('root',type=Path);p.add_argument('--config',type=Path,required=True)
    p=sub.add_parser('prepare');p.add_argument('root',type=Path);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--endpoint-evidence',type=Path,required=True);p.add_argument('--image',required=True)
    for action in ('validate','run','grade','_warm','_work','_grade'):
        p=sub.add_parser(action);p.add_argument('root',type=Path)
        if action in {'run','grade'}:p.add_argument('--approval',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    if args.action=='inspect':
        data=inspect_endpoint(args.config,root);print(json.dumps({'ready':data['health']['data'],'generation_requests':0}));return
    if args.action=='prepare':m=prepare(args.source,args.config,args.endpoint_evidence,root,args.image)
    elif args.action=='validate':m=load(root)
    elif args.action=='run':run(root,args.approval);m=load(root)
    elif args.action=='grade':
        m=authorize(root,args.approval);closed(root)
        result=run_phase(root/'state','grade',[sys.executable,str(ASSETS/'trial.py'),'_grade',str(root)],REPO)
        write(root/'grade-process.json',result)
        if result['code'] or result['timed_out'] or not result['cleanup']['passed']:raise RuntimeError('grading failed closed')
    else:
        lease=current(root/'state');phase=args.action[1:]
        if not lease or lease['phase']!=phase or (root/'quarantine.json').exists():raise ValueError('live matching phase lease required')
        m=load(root);{'warm':warm,'work':work,'grade':grade}[phase](root,m);return
    status=('ENGINEERING_CLOSED' if (root/'engineering-closed.json').exists() else 'ENGINEERING_INCOMPLETE') if args.action=='run' else 'GRADED' if args.action=='grade' else m['status']
    print(json.dumps({'status':status,'approval_digest':digest(m),'automatic_dispatch_allowed':False}))


if __name__=='__main__':main()
