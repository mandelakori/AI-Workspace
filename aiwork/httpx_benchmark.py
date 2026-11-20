"""Frozen approval bundle and one-shot, local-only HTTPX comparison runner."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from dataclasses import asdict, replace
from pathlib import Path
from time import time

from .changes import validate_changes, delta
from .controller import Controller, write_json
from .harness import opencode_path, request_options
from .http import request
from .inference import Inference, ollama_inventory
from .lock import file_lock
from .oracle import load_cases
from .planner import planned
from .schema import Check, Config, Profile, Task
from .selection import compare
from .trial_budget import FILE, PHASE_LIMITS, claim, create, current, remaining, run_phase
from .verify import invoke, runner_status
from .workspace import contained, inventory, snapshot

ARMS = ("direct", "hierarchical")
PATHS = ("httpx/_utils.py", "httpx/_client.py", "tests/test_path_mounts.py", "docs/advanced/transports.md")
ASSETS = Path(__file__).resolve().parents[1] / "examples/phase61"


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def implementation() -> dict:
    return {path.name:file_hash(path) for path in sorted(Path(__file__).parent.glob("*.py"))}


def model_metadata(profile: Profile) -> dict:
    api = profile.endpoint.rstrip('/').removesuffix('/v1')
    tags = request(api+'/api/tags', timeout=5)['models']
    model = next(row for row in tags if row['name'] == profile.model)
    shown = request(api+'/api/show', 'POST', {'model':profile.model}, timeout=5)
    return {'digest':model['digest'], 'parameters':shown.get('parameters'),
            'parameters_sha256':digest(shown.get('parameters')), 'details':model.get('details')}


def config(root: Path, arm: str, manifest: dict) -> Config:
    return Config(root/'arms'/arm/'state', (Profile(**manifest['profile']),),
                  opencode=manifest['harness']['path'], verification_image=manifest['runner'],
                  local_slots=1, execution_state=Path(manifest['execution_state']))


def prepare(review_path: Path, root: Path) -> dict:
    original = json.loads(review_path.read_bytes())
    old_digest = original.pop('approval_digest')
    # Preserve the canonicalization used by the original Phase 6.1 review.
    if hashlib.sha256(json.dumps(original,sort_keys=True,default=str).encode()).hexdigest() != old_digest:
        raise ValueError('original review digest mismatch')
    source = review_path.parent/'httpx-input-freeze'
    if inventory(source) != original['inventory'] or inventory(review_path.parent/'httpx-task') != original['inventory']:
        raise ValueError('prepared HTTPX inputs changed')
    checkout = review_path.parent/'httpx-upstream'
    head = subprocess.run(['git','rev-parse','HEAD'],cwd=checkout,capture_output=True,text=True,check=True).stdout.strip()
    clean = subprocess.run(['git','status','--porcelain'],cwd=checkout,capture_output=True,text=True,check=True).stdout
    if head != original['base_commit'] or clean or tuple(original['write_roots']) != PATHS:
        raise ValueError('checkout or approved scopes changed')
    for filename, wanted in [('FEATURE.md',original['feature_sha256']),('_public_checks.py',original['public_sha256'])]:
        if file_hash(source/filename) != wanted:
            raise ValueError('frozen specification/public corpus changed')
    cfg = Config.load(review_path.parent/'local.toml')
    profile, = cfg.profiles
    if asdict(profile) != original['profile'] or profile.location != 'local' or profile.managed:
        raise ValueError('local profile changed')
    if runner_status(review_path.parent,original['runner'])['image_id'] != original['runner']:
        raise ValueError('verification image is unavailable or changed')
    binary = opencode_path(cfg.opencode)
    if not binary:
        raise ValueError('installed OpenCode is required')
    root.mkdir(parents=True,exist_ok=False)
    snapshot(source,root/'original-input',())
    (root/'assets').mkdir()
    for name in ['trial_score.py','sealed_probe.py']:
        shutil.copyfile(ASSETS/name,root/'assets'/name)
    commands = [Check.read(row) for row in original['commands']]
    metadata = model_metadata(profile)  # Inventory only; no inference.
    original_docs = (source/'docs/advanced/transports.md').read_text(encoding='utf-8')
    starts = {}
    for arm in ARMS:
        target = root/'arms'/arm/'input'
        snapshot(source,target,())
        shutil.copyfile(root/'assets/trial_score.py',target/'_trial_score.py')
        write_json(target/'_trial_policy.json',{'upstream':commands[1].argv,
                   'original_docs_text_sha256':hashlib.sha256(original_docs.encode()).hexdigest()})
        starts[arm] = inventory(target)
    if starts['direct'] != starts['hierarchical']:
        raise ValueError('arm starting snapshots differ')
    probe_start = time()
    probe = invoke(Check(('python','-I','-c',
        "import json,shutil,time; print(json.dumps({'timeout':shutil.which('timeout'),'utc':time.time()}))")),
        root/'assets',root/'probe-home',original['runner'],sealed=True)
    probe_end = time()
    observed = json.loads(probe['stdout']) if probe['passed'] else {}
    if not observed.get('timeout') or not probe_start-.25 <= observed.get('utc',0) <= probe_end+.25:
        raise ValueError('image watchdog/clock preflight failed')
    manifest = {
        'format':1,'status':'PREPARED_NOT_AUTHORIZED','execution_allowed':False,'bundle':str(root.resolve()),
        'source_commit':head,'original_review_digest':old_digest,
        'specification_sha256':original['feature_sha256'],'public_corpus_sha256':original['public_sha256'],
        'original_inventory':original['inventory'],'starting_inventories':starts,
        'profile':asdict(profile),'profile_sha256':digest(asdict(profile)), 'model':metadata,
        'runner':original['runner'],'harness':{'path':binary,'sha256':file_hash(Path(binary))},
        'execution_state':str(cfg.execution_state),'platform':platform.system(),'implementation_sha256':implementation(),
        'asset_inventory':inventory(root/'assets'),'write_roots':list(PATHS),
        'commands':[asdict(c) for c in commands],
        'worker_policy':{'sessions':2,'planner_requests':1,'mcp_calls_per_session':16,'workers':1,
                         'per_request_output_tokens':2048,'total_token_cap':None,
                         'retain_isolated_worker_source':True,
                         'native_shell':False,'network_in_verifier':False,'read_scope':'identical staged public inputs only'},
        'phase_seconds':PHASE_LIMITS,'total_seconds_per_arm':240,'total_seconds_pair':480,
        'clock_policy':'Cumulative execution reservations: warm/preflight 20 + engineering/public verification 180 + independent grading 40. No transfers, refunds, restarts or resumed worker sessions.',
        'cleanup_policy':'Warm phase forbids verification/container launches and has no container cleanup. Work/grade cleanup commands share one absolute 10-second allowance, without a shorter per-command cap. Only cancellation/owned-container deletion may run after a deadline. No new inference, tools or verification. Unknown ownership or cleanup failure quarantines the trial.',
        'provider_cancellation':'Owned clients are terminated at the deadline; the existing shared server is never killed. Backend cancellation latency is not measured during preparation. Inference interruption or a work/warm watchdog timeout quarantines the pair: no further arm/grade dispatch.',
        'warm_protocol':{'order':list(ARMS),'neutral_requests_per_arm':1,'max_tokens':4,
                         'prompt':'Reply with exactly READY.','temperature':0,'reasoning_effort':profile.reasoning_effort,
                         'resident_context_required':8192,'fresh_harness_home':True,'no_restart_unload_or_model_changes':True,
                         'minimum_residency_ttl_seconds':185,
                         'exclusive_operator_window_required':True,
                         'cache_limitation':'Same neutral latest-prompt protocol; no claim of purging all provider KV caches. One ordered pair is exploratory, not a causal architecture benchmark.'},
        'arm_recipes':{'direct':'One monolithic job, up to two worker attempts.',
                       'hierarchical':'One model-proposed graph, exactly two scoped steps, one attempt each, sequential; integration and all verification share the same deadline. Invalid plans receive no extra planner request.'},
        'selection':'Both arms: identical post-run public selector, upstream gate, original 16 public cases, authored-tests/documentation gate; reject lost public passes, ties retain predecessor.',
        'sealed_policy':{'required_cases':24,'same_cases_both_arms':True,'author_after_all_work_closed':True,
                          'worker_feedback':False,'grader':'assets/sealed_probe.py','private_cases':'private/cases.json',
                          'expected_results_mounted':False},
        'authorization':'Requires a separate operator grant naming this exact digest and both arms. No such grant is created by preparation.',
        'mid_run_guidance':'Prohibited. Any operator implementation guidance invalidates the unassisted classification.',
        'probe':{'passed':True,'image_watchdog':observed['timeout'],'clock_within_host_roundtrip':True},
    }
    manifest['approved_public_commands']=[asdict(c) for c in task(root,'direct',manifest).commands]
    manifest['tasks']={arm:{**asdict(task(root,arm,manifest)),'workspace':f'arms/{arm}/input','verification_dir':None} for arm in ARMS}
    write_json(root/'manifest.json',manifest)
    (root/'manifest.sha256').write_text(digest(manifest),encoding='ascii')
    return {'status':manifest['status'],'approval_digest':digest(manifest),'manifest':str(root/'manifest.json')}


def load(root: Path) -> dict:
    manifest=json.loads((root/'manifest.json').read_bytes())
    if digest(manifest)!=(root/'manifest.sha256').read_text().strip() or str(root.resolve())!=manifest['bundle']:
        raise ValueError('approval manifest identity changed')
    if implementation()!=manifest['implementation_sha256'] or inventory(root/'assets')!=manifest['asset_inventory']:
        raise ValueError('approved execution implementation changed')
    if inventory(root/'original-input')!=manifest['original_inventory']:
        raise ValueError('original frozen inputs changed')
    for arm in ARMS:
        if inventory(root/'arms'/arm/'input')!=manifest['starting_inventories'][arm]:
            raise ValueError('clean starting snapshot changed')
    if file_hash(Path(manifest['harness']['path']))!=manifest['harness']['sha256']:
        raise ValueError('harness executable changed')
    return manifest


def authorize(root: Path, grant: Path) -> dict:
    manifest=load(root)
    approval=json.loads(grant.read_bytes())
    if approval != {'approval_digest':digest(manifest),'authorize':list(ARMS),'operator_approved':True}:
        raise ValueError('explicit operator authorization for this manifest is required')
    return manifest


def warm(root: Path, arm: str, manifest: dict) -> None:
    cfg=config(root,arm,manifest);profile,=cfg.profiles
    if platform.system()!=manifest['platform'] or model_metadata(profile)!=manifest['model']:
        raise ValueError('model or host changed')
    if runner_status(root,manifest['runner'])['image_id']!=manifest['runner']:
        raise ValueError('runner changed')
    payload={'model':profile.model,'messages':[{'role':'user','content':manifest['warm_protocol']['prompt']}],
             'temperature':0,'max_tokens':4,**request_options(profile)}
    with Controller(cfg).planes['local'].reserve(profile,max(.01,remaining(current()))):
        before=ollama_inventory(profile.endpoint)
        write_json(root/'arms'/arm/'warm-request.json',payload)
        try:
            response=request(profile.endpoint.rstrip('/')+'/chat/completions','POST',payload,
                             timeout=max(.01,remaining(current())),key=Inference(profile).key(),
                             capture=lambda kind,body:(root/'arms'/arm/('warm-wire-'+kind+'.json')).write_bytes(body))
        except OSError:
            from .trial_budget import inference_interrupted
            inference_interrupted()
            raise
        write_json(root/'arms'/arm/'warm-response.json',response)
        inventory_=ollama_inventory(profile.endpoint)
        resident=next((m for m in inventory_['resident'] if m.get('name')==profile.model),None)
        if (not resident or resident.get('context_length')!=8192
                or resident.get('digest')!=manifest['model']['digest']):
            raise ValueError('required warm serving context unavailable')
        if datetime.fromisoformat(resident['expires_at']).timestamp()<time()+185:
            raise ValueError('model residency TTL is too short for a matched warm run')
        write_json(root/'arms'/arm/'warm-state.json',{'before':before,'resident':resident,'protocol':manifest['warm_protocol']})


def task(root: Path, arm: str, manifest: dict) -> Task:
    work=root/'arms'/arm/'input'
    row=dict(manifest['commands'][1]);row['argv']=list(row['argv'])
    upstream=Check.read(row)
    all_public=Check(('python','_public_checks.py'),timeout=60)
    names=['test_async_mount_integration','test_sync_mount_integration']
    basic_source=(work/'_public_checks.py').read_text()
    import ast
    cls=next(n for n in ast.parse(basic_source).body if isinstance(n,ast.ClassDef) and n.name=='PublicPathMounts')
    basic=tuple('PublicPathMounts.'+n.name for n in cls.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_') and n.name not in names)
    commands=(all_public,Check(('python','_public_checks.py',*basic),timeout=60),
              Check(('python','_public_checks.py',*('PublicPathMounts.'+name for name in names)),timeout=60),
              upstream,Check(('python','_trial_score.py','artifacts'),timeout=75))
    profile=manifest['profile']
    return Task((work/'FEATURE.md').read_text()+'\nUse approved public commands and bounded inspection. Complete source, authored tests and documentation without asking for implementation guidance.',
                work,'agent','httpx-autonomy',tuple(sorted({name.split('/')[0] for name in manifest['starting_inventories'][arm]})),
                (), (all_public,upstream,commands[4]), mode='engineering',write_roots=PATHS,
                profile=profile['id'],location='local',agent_role='implementation',min_context=8192,
                attempts=2 if arm=='direct' else 1,timeout=120,commands=commands,baseline_check=True)


def task_file(value: Task, path: Path) -> None:
    data=asdict(value);data['workspace']=str(value.workspace)
    data.pop('verification_dir')
    checks={key:data.pop(key) for key in ['checks','commands','setup']}
    text=''.join(f'{key} = {json.dumps(val)}\n' for key,val in data.items())
    for group, rows in checks.items():
        for row in rows:
            text+='\n[['+group+']]\n'+''.join(f'{key} = {json.dumps(val)}\n' for key,val in row.items() if val is not None)
    path.write_text(text,encoding='utf-8')


def score(root: Path, arm: str, source: Path, destination: Path, manifest: dict) -> dict:
    frozen=snapshot(source,destination,())
    validate_changes(delta(manifest['starting_inventories'][arm],frozen),PATHS)
    out=invoke(Check(('python','_trial_score.py','score'),timeout=120),destination,destination.parent/'home',manifest['runner'],sealed=True)
    write_json(destination.parent/(destination.name+'-raw.json'),out)
    parsed=json.loads(out['stdout']) if out['passed'] else None
    receipt={'runner':manifest['runner'],'corpus_sha256':manifest['public_corpus_sha256'],'total':16,
             'inventory':frozen,'compiled':bool(parsed and parsed['upstream']['passed']),
             'cases':parsed['cases'] if parsed else [],
             'missing':[] if parsed and parsed['artifacts']['passed'] else ['authored tests / documentation'],
             'public_passed':bool(parsed and parsed['upstream']['passed'] and parsed['artifacts']['passed'] and all(c['verdict']=='pass' for c in parsed['cases']))}
    receipt['passed_cases']=sum(c['verdict']=='pass' for c in receipt['cases'])
    write_json(destination.parent/(destination.name+'-score.json'),receipt)
    return receipt


def publish(root: Path, arm: str, source: Path, receipt: dict, delivery: bool) -> None:
    active=current();out=root/'arms'/arm
    frozen=out/('frozen-'+hashlib.sha256(json.dumps(receipt['inventory'],sort_keys=True).encode()).hexdigest()[:16])
    if not frozen.exists():snapshot(source,frozen,())
    if inventory(frozen)!=receipt['inventory']:raise ValueError('frozen checkpoint changed')
    current()
    write_json(out/'frozen.json',{'path':str(frozen),'inventory':receipt['inventory'],
        'inventory_sha256':digest(receipt['inventory']),'frozen_at':time(),'public':receipt,
        'model_source_delivery':delivery,'phase_deadline':active['deadline_utc']})


def work(root: Path, arm: str, manifest: dict) -> None:
    cfg=config(root,arm,manifest);controller=Controller(cfg);value=task(root,arm,manifest)
    out=root/'arms'/arm; grades=out/'selection';grades.mkdir()
    incumbent=score(root,arm,value.workspace,grades/'baseline',manifest)
    selected=grades/'baseline';publish(root,arm,selected,incumbent,False)
    try:
        if arm=='direct':
            job=controller.submit_task(value);result=controller.run_submitted(job)
        else:
            path=out/'task.toml';task_file(value,path)
            result=planned(controller,path,'measured',1,False,value.profile,False,2,True,2)
        write_json(out/'engineering-result.json',result)
    except (OSError,RuntimeError,ValueError,KeyError) as error:
        write_json(out/'engineering-error.json',{'error':str(error)})
    history=[]
    candidates=set(cfg.state.glob('runs/*/attempt-*/workspace'))
    for record in cfg.state.glob('plans/*/result.json'):
        combined=json.loads(record.read_bytes()).get('combined')
        if combined:candidates.add(Path(combined))
    for number,path in enumerate(sorted(candidates),1):
        current()
        try:
            challenger=score(root,arm,path,grades/f'candidate-{number}',manifest)
            decision=compare(incumbent,challenger,protect_passing=True)
            if decision['accepted']:
                incumbent=challenger;selected=grades/f'candidate-{number}'
                publish(root,arm,selected,incumbent,True)
        except (ValueError,OSError,RuntimeError) as error:
            decision={'accepted':False,'reason':str(error)}
        history.append({'candidate':str(path),**decision})
        write_json(out/'selection-history.json',history)


def closed(root: Path) -> None:
    for arm in ARMS:
        data=json.loads((root/'arms'/arm/'state'/FILE).read_bytes())
        if data['phases']['warm']['status']=='FAILED':continue
        if data['phases']['work']['status'] not in {'FINISHED','FAILED'}:
            raise ValueError('all engineering must close before sealed cases are accepted')


def sealed_match(row: dict, raw: dict) -> bool:
    return (not raw['timed_out'] and not raw['truncated'] and raw['code']==row.get('code',0)
            and raw['stdout'].replace('\r\n','\n')==row['stdout']
            and raw['stderr'].replace('\r\n','\n')==row.get('stderr',''))


def grade(root: Path, arm: str, cases: Path, manifest: dict) -> None:
    closed(root)
    saved=json.loads((root/'arms'/arm/'frozen.json').read_bytes())
    if inventory(Path(saved['path']))!=saved['inventory']:raise ValueError('frozen candidate changed')
    rows=load_cases(cases)
    if len(rows)!=manifest['sealed_policy']['required_cases']:raise ValueError('sealed protocol requires exactly 24 cases')
    workroot=root/'arms'/arm/'independent';workroot.mkdir()
    candidate=workroot/'candidate';snapshot(Path(saved['path']),candidate,())
    shutil.copyfile(root/'assets/sealed_probe.py',candidate/'_sealed_probe.py')
    results=[]
    for number,row in enumerate(rows,1):
        current()
        raw=invoke(Check(('python','_sealed_probe.py'),timeout=40),candidate,workroot/'home',manifest['runner'],
                   stdin=row.get('stdin','').encode(),sealed=True,extra_args=tuple(row.get('argv',[])))
        write_json(workroot/f'case-{number:02}.json',raw)
        passed=sealed_match(row,raw)
        results.append({'case':number,'passed':passed,'elapsed':raw['elapsed']})
        write_json(workroot/'receipt.json',{'completed':len(results),'total':len(rows),'passed':sum(r['passed'] for r in results),
                   'cases':results,'candidate_inventory_sha256':saved['inventory_sha256'],'cases_sha256':file_hash(cases)})
    if any(inventory(candidate).get(name)!=entry for name,entry in saved['inventory'].items()):
        raise ValueError('candidate changed during independent grading')
    write_json(workroot/'final.json',{'public_passed':saved['public']['public_passed'],
        'sealed_passed':sum(r['passed'] for r in results),'sealed_total':len(rows),
        'feature_verified':saved['public']['public_passed'] and all(r['passed'] for r in results),
        'model_source_delivery':saved['model_source_delivery'],'candidate_unchanged':True,
        'candidate_inventory_sha256':saved['inventory_sha256']})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('review',type=Path);prep.add_argument('root',type=Path)
    for name in ['run','grade']:
        action=sub.add_parser(name);action.add_argument('root',type=Path);action.add_argument('--arm',choices=ARMS,required=True)
        action.add_argument('--authorization',type=Path,required=True)
        if name=='grade':action.add_argument('--cases',type=Path,required=True)
    internal=sub.add_parser('_phase');internal.add_argument('root',type=Path);internal.add_argument('arm',choices=ARMS);internal.add_argument('phase',choices=PHASE_LIMITS);internal.add_argument('--cases',type=Path)
    args=parser.parse_args();root=args.root.resolve()
    if args.action=='prepare':print(json.dumps(prepare(args.review.resolve(),root),indent=2));return
    if args.action=='_phase':
        lease=current(root/'arms'/args.arm/'state')
        if not lease or lease['phase']!=args.phase:
            raise ValueError('internal phase requires its exact active budget lease')
        manifest=load(root)
        {'warm':lambda:warm(root,args.arm,manifest),'work':lambda:work(root,args.arm,manifest),
         'grade':lambda:grade(root,args.arm,args.cases.resolve(),manifest)}[args.phase]();return
    manifest=authorize(root,args.authorization.resolve())
    with file_lock(root/'pair.lock'):
        for path in root.glob('arms/*/state/'+FILE):
            if json.loads(path.read_bytes()).get('quarantined'):
                raise ValueError('trial quarantined by failed ownership cleanup')
        arm=root/'arms'/args.arm;state=arm/'state'
        if args.action=='run':
            if args.arm=='hierarchical':
                direct=json.loads((root/'arms/direct/state'/FILE).read_bytes())
                if direct['phases']['warm']['status']!='FAILED' and direct['phases']['work']['status'] not in {'FINISHED','FAILED'}:
                    raise ValueError('fixed arm order requires direct to close first')
            create(state,digest(manifest),args.arm)
            for phase in ['warm','work']:
                result=run_phase(state,phase,[sys.executable,'-m','aiwork.httpx_benchmark','_phase',str(root),args.arm,phase],Path(__file__).parents[1])
                write_json(arm/(phase+'-process.json'),result)
                if result['code'] or result['timed_out'] or not result['cleanup']['passed']:break
        else:
            closed(root);cases=args.cases.resolve()
            if len(load_cases(cases))!=manifest['sealed_policy']['required_cases']:raise ValueError('sealed protocol requires exactly 24 cases')
            if cases != contained(root,'private/cases.json').resolve():
                raise ValueError('sealed inputs require the approved private path')
            cutoff=max([json.loads((root/'arms'/a/'frozen.json').read_bytes())['frozen_at'] for a in ARMS if (root/'arms'/a/'frozen.json').exists()]+
                       [json.loads((root/'arms'/a/'state'/FILE).read_bytes())['phases']['work'].get('finished_utc',0) for a in ARMS])
            if cases.stat().st_mtime<=cutoff:raise ValueError('sealed inputs must be authored after all work closed')
            record=root/'sealed-input-hash.json';identity={'sha256':file_hash(cases),'count':len(load_cases(cases))}
            if record.exists() and json.loads(record.read_bytes())!=identity:raise ValueError('both arms require identical sealed cases')
            write_json(record,identity)
            result=run_phase(state,'grade',[sys.executable,'-m','aiwork.httpx_benchmark','_phase',str(root),args.arm,'grade','--cases',str(cases)],Path(__file__).parents[1])
            write_json(arm/'grade-process.json',result)
    print(json.dumps({'arm':args.arm,'budget':str(state/FILE)},indent=2))


if __name__=='__main__':main()
