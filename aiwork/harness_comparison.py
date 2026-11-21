"""Fresh, authorization-gated OpenCode/Pi pair. No execution during preparation."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from time import time

from .changes import delta, validate_changes
from .controller import Controller
from .discovery_benchmark import COMMIT, PATHS, commands, upfront, score, milestones
from .harness import opencode_path
from .httpx_benchmark import digest, file_hash, implementation
from .lock import file_lock
from .pi_harness import pi_path, VERSION
from .process import executable
from .schema import Config, Task, Profile, Check
from .selection import compare
from .trial_budget import FILE, create, run_phase, write
from .verify import invoke, runner_status
from .workspace import inventory, snapshot

ARMS=['opencode','pi']
LIMITS={'warm':5,'work':330,'grade':40}  # warm is a no-inference lease startup, NOT model warming.


def runtime_hashes(sdk: Path) -> dict:
    paths=[Path(__file__).parent/'pi/bridge.mjs',Path(__file__).parents[1]/'harnesses/pi/package-lock.json']
    for package in ('pi-coding-agent','pi-ai','pi-agent-core'):
        paths.extend(sorted((sdk.parent/package/'dist').rglob('*.js')))
    return {str(p.resolve()):file_hash(p) for p in paths}


def prepare(source: Path, calibration: Path, root: Path, image: str, sdk: Path) -> dict:
    root=root.resolve();source=source.resolve(strict=True);calibration=calibration.resolve(strict=True)
    old=Path(__file__).parents[1]/'docs/evidence/phase61/discovery-result/source-receipt.json'
    root.mkdir(parents=True,exist_ok=False)
    original=root/'original-input';snapshot(source,original,())
    required={'FEATURE.md','_public_cases.json','_benchmark_checks.py',PATHS[0]}
    if not all((original/p).is_file() for p in required):raise ValueError('expected frozen dotenv input snapshot')
    if inventory(original)!=json.loads(old.read_bytes())['inventory']:
        raise ValueError('source does not match the independently archived pinned baseline')
    if len(json.loads((original/'_public_cases.json').read_bytes()))!=10:raise ValueError('ten public cases required')
    installed=pi_path(str(sdk),root)
    binary=opencode_path()
    if not installed or not binary:raise ValueError('both pinned harness installations required')
    runner=runner_status(root,image)['image_id']
    if not runner or not runner.startswith('sha256:'):raise ValueError('existing immutable Docker image required')
    report=json.loads(calibration.read_bytes())
    if report['model']!='qwen3.5:9b' or not any(r['context']==16384 and r['status']=='measured' for r in report['contexts']):
        raise ValueError('expected measured local Qwen3.5-9B/16K calibration')
    baseline={}
    for action in ('syntax','public','upstream'):
        target=root/'validation'/action;snapshot(original,target,())
        result=invoke(Check(('python','_benchmark_checks.py',action),timeout=60),target,root/'validation/home',runner,timeout=65)
        write(root/'validation'/f'{action}.json',result);baseline[action]=result
    public=json.loads(baseline['public']['stdout'])
    if public['passed']!=2 or public['total']!=10 or not baseline['upstream']['passed'] or not baseline['syntax']['passed']:
        raise ValueError('unmodified baseline did not reproduce public/upstream behavior')
    seed=secrets.token_hex(16);order=ARMS[:] if int(seed,16)%2==0 else ARMS[::-1]
    profiles={arm:asdict(Profile('local-'+arm,'qwen3.5:9b','http://127.0.0.1:11434/v1',
                 engine='ollama',harness=arm,context=16384,output_tokens=2048,reasoning_effort='none',
                 seed=1729,temperature=0,local_calibration=str(calibration),calibration_sha256=file_hash(calibration))) for arm in ARMS}
    starts={a:snapshot(original,root/'arms'/a/'input',()) for a in ARMS}
    source_text=upfront(original);write(root/'initial-context.json',{'text':source_text})
    manifest={'format':1,'status':'PREPARED_NOT_AUTHORIZED','execution_allowed':False,'kind':'local-harness-pair',
        'bundle':str(root),'arms':ARMS,'execution_order':order,'randomization_seed':seed,
        'repository':'https://github.com/theskumar/python-dotenv','repository_commit':COMMIT,
        'task_reuse':'Same frozen public problem as closed Phase 6.1; fresh workers/instances; no unfamiliar-task claim.',
        'source_receipt_reference_sha256':file_hash(old),'original_inventory':inventory(original),
        'starting_inventories':starts,'runner':runner,'public_corpus_sha256':file_hash(original/'_public_cases.json'),
        'baseline':{'public':public,'upstream':baseline['upstream'],'syntax':baseline['syntax']},
        'profiles':profiles,'opencode':{'path':binary,'sha256':file_hash(Path(binary))},
        'pi':{'path':str(installed),'version':VERSION,'runtime_sha256':runtime_hashes(installed)},
        'inference_binary':{'path':executable('ollama'),'sha256':file_hash(Path(executable('ollama')))},
        'calibration':{'path':str(calibration),'sha256':file_hash(calibration)},
        'initial_context_sha256':file_hash(root/'initial-context.json'),'initial_context_utf8_bytes':len(source_text.encode()),
        'execution_state':str((Path(__file__).parents[1]/'.aiwork').resolve()),
        'implementation_sha256':implementation(),'phase_limits':LIMITS,
        'attempt_seconds':300,'verification_reservation_seconds':20,'operations':48,
        'edit_reserve':4,'public_test_reserve':4,'model_requests':64,'compactions':4,
        'observed_input_tokens':7440,'context_reserve_tokens':512,
        'context_selection':'16K fixed for both; refuse rather than change context if current admission fails.',
        'cold_protocol':'Fresh private server and harness home per arm; no generation warmup. Cold model load and observed first-prefill initialization overhead are charged inside the 300-second attempt. OS/driver caches are not purged.',
        'permission_contract':{'write_roots':list(PATHS),'tools':['checks_focus','checks_edit','checks_check','checks_diff'],
            'native_mutation':False,'shell':False,'network':'owned loopback inference only; verification Docker offline'},
        'selection':'Final versus original using full public corpus, protected prior passes and upstream checks. Ties keep baseline; no sealed feedback. Intermediate snapshots preserved but not all ranked.',
        'sealed_policy':{'cases':12,'author_after_both_freeze':True,'expectations_mounted':False,'feedback_to_workers':False},
        'stop_policy':'Stop pair on interruption, failed catalog, unexpected provider/harness failure or failed cleanup; consumed trials cannot resume.',
        'comparison_limitations':'One pair is exploratory. Report actual CPU offload, cache tokens and timing; no causal success-rate or hierarchy claim.'}
    write(root/'manifest.json',manifest);(root/'manifest.sha256').write_text(digest(manifest)+'\n')
    write(root/'operator-approval.example.json',{'approval_digest':digest(manifest),'authorize':ARMS,'operator_approved':False})
    return manifest


def load(root: Path) -> dict:
    manifest=json.loads((root/'manifest.json').read_bytes())
    if digest(manifest)!=(root/'manifest.sha256').read_text().strip():raise ValueError('manifest digest mismatch')
    if manifest['kind']!='local-harness-pair' or manifest['arms']!=ARMS or manifest['phase_limits']!=LIMITS:
        raise ValueError('unsupported comparison protocol')
    if manifest['implementation_sha256']!=implementation():raise ValueError('execution implementation changed')
    if runtime_hashes(Path(manifest['pi']['path']))!=manifest['pi']['runtime_sha256']:
        raise ValueError('pinned Pi runtime changed')
    if file_hash(Path(manifest['opencode']['path']))!=manifest['opencode']['sha256']:
        raise ValueError('pinned OpenCode changed')
    if 'inference_binary' in manifest:
        binary=manifest['inference_binary']
        if executable('ollama')!=binary['path'] or file_hash(Path(binary['path']))!=binary['sha256']:
            raise ValueError('pinned Ollama executable changed')
    if file_hash(Path(manifest['calibration']['path']))!=manifest['calibration']['sha256']:
        raise ValueError('calibration changed')
    if file_hash(root/'initial-context.json')!=manifest['initial_context_sha256']:
        raise ValueError('initial source context changed')
    if inventory(root/'original-input')!=manifest['original_inventory']:
        raise ValueError('frozen input changed')
    for arm in ARMS:
        if inventory(root/'arms'/arm/'input')!=manifest['starting_inventories'][arm]:raise ValueError('arm input changed')
        Profile(**manifest['profiles'][arm]).validate()
    shared=[{k:v for k,v in manifest['profiles'][a].items() if k not in {'id','harness'}} for a in ARMS]
    if shared[0]!=shared[1] or any(manifest['profiles'][a]['harness']!=a for a in ARMS):
        raise ValueError('arms have unmatched model/resource settings')
    return manifest


def authorize(root: Path, approval: Path) -> dict:
    manifest=load(root);grant=json.loads(approval.read_bytes())
    if (grant.get('approval_digest')!=digest(manifest) or grant.get('authorize')!=ARMS
            or grant.get('operator_approved') is not True):raise ValueError('separate exact operator approval required')
    return manifest


def work(root: Path, arm: str, manifest: dict):
    profile=Profile(**manifest['profiles'][arm]);out=root/'arms'/arm
    config=Config(out/'state',(profile,),opencode=manifest['opencode']['path'],pi=manifest['pi']['path'],
                  verification_image=manifest['runner'],execution_state=Path(manifest['execution_state']))
    checks=commands()
    task=Task((root/'original-input/FEATURE.md').read_text(),out/'input','agent','dotenv-harness-pair',
              tuple(sorted({p.split('/')[0] for p in manifest['original_inventory']})),(),(checks[0],checks[2]),
              location='local',profile=profile.id,mode='engineering',write_roots=PATHS,commands=checks,
              baseline_check=True,min_context=manifest['observed_input_tokens']+profile.output_tokens+profile.context_reserve_tokens,
              context_input_tokens=manifest['observed_input_tokens'],agent_role='implementation',
              timeout=manifest['attempt_seconds'],attempts=1,tool_operations=manifest['operations'],
              edit_reserve=manifest['edit_reserve'],public_test_reserve=manifest['public_test_reserve'],
              model_requests=manifest['model_requests'],compaction_limit=manifest['compactions'])
    controller=Controller(config,initial_context=json.loads((root/'initial-context.json').read_bytes())['text'])
    result=controller.run_submitted(controller.submit_task(task));write(out/'engineering-result.json',result)
    attempts=list(config.state.glob('runs/*/attempt-*'))
    if len(attempts)!=1:raise RuntimeError('exactly one worker attempt required')
    attempt=attempts[0];receipt=json.loads((attempt/'execution-receipt.json').read_bytes())
    if receipt['status'] not in {'completed','resource_exhausted'} or not receipt['cleanup_passed']:
        raise RuntimeError('harness did not close cleanly; stop comparison')
    candidate=score(root,arm,attempt/'workspace',out/'public-selection',manifest)
    public=manifest['baseline']['public']
    incumbent={'corpus_sha256':manifest['public_corpus_sha256'],'runner':manifest['runner'],'total':10,
               'compiled':True,'missing':[PATHS[1]],'cases':[{'case':i,'verdict':'pass' if r['passed'] else 'fail'}
                                                           for i,r in enumerate(public['cases'],1)]}
    decision=compare(incumbent,candidate,protect_passing=True)
    if not candidate['upstream_passed']:decision.update(accepted=False,reason='upstream_regression')
    chosen=out/'public-selection' if decision['accepted'] else out/'input'
    frozen=snapshot(chosen,out/'frozen',())
    write(out/'selection.json',{'decision':decision,'candidate':candidate,'milestones':milestones(config.state)})
    write(out/'frozen.json',{'path':str(out/'frozen'),'inventory':frozen,'frozen_at':time(),
                            'model_source_delivery':decision['accepted'],'inventory_sha256':digest(frozen)})


def closed(root: Path):
    for arm in ARMS:
        out=root/'arms'/arm;budget=json.loads((out/'state'/FILE).read_bytes())
        if budget.get('quarantined') or budget['phases']['work']['status']!='FINISHED':
            raise ValueError('both engineering phases must close without quarantine')
        frozen=json.loads((out/'frozen.json').read_bytes())
        if inventory(Path(frozen['path']))!=frozen['inventory']:raise ValueError('frozen candidate changed')


def run(root: Path, approval: Path):
    manifest=authorize(root,approval)
    if runner_status(root,manifest['runner'])['image_id']!=manifest['runner']:
        raise ValueError('approved offline verification image unavailable')
    with file_lock(root/'comparison.lock'):
        if (root/'execution-started.json').exists():raise ValueError('one-shot comparison already consumed')
        write(root/'execution-started.json',{'approval_digest':digest(manifest),'started':time()})
        saved=root/'operator-approval.json'
        if saved.exists() and saved.read_bytes()!=approval.read_bytes():raise ValueError('stored approval differs')
        if not saved.exists():saved.write_bytes(approval.read_bytes())
    for arm in ARMS:create(root/'arms'/arm/'state',digest(manifest),arm,LIMITS,
                           quotas={'sessions':1,'planner_requests':0},reviewed_caps=LIMITS)
    for arm in manifest['execution_order']:
        state=root/'arms'/arm/'state'
        for phase,cmd,containers in [('warm',[sys.executable,'-c','pass'],False),
             ('work',[sys.executable,'-m','aiwork.harness_comparison','_work',str(root),arm],True)]:
            outcome=run_phase(state,phase,cmd,Path(__file__).parents[1],containers=containers)
            write(state.parent/f'{phase}-process.json',outcome)
            if outcome['code'] or outcome['timed_out'] or not outcome['cleanup']['passed']:
                write(root/'quarantine.json',{'arm':arm,'phase':phase,'reason':'execution or cleanup failure'})
                raise RuntimeError('comparison quarantined; no retry or resume')
    closed(root)
    write(root/'engineering-closed.json',{'closed_at':time(),'next':'independently author twelve new sealed cases'})


def grade(root: Path, arm: str, manifest: dict):
    closed(root);path=root/'private/cases.json';cases=json.loads(path.read_bytes())
    if len(cases)!=12 or len({r['id'] for r in cases})!=12:raise ValueError('twelve fresh named cases required')
    frozen_times=[json.loads((root/'arms'/a/'frozen.json').read_bytes())['frozen_at'] for a in ARMS]
    if path.stat().st_mtime<=max(frozen_times):raise ValueError('sealed cases must be authored after candidate freeze')
    payloads=[{k:v for k,v in r.items() if k not in {'id','expected'}} for r in cases]
    if any(set(p) not in ({'value','env'},{'stream'}) for p in payloads):raise ValueError('unsupported sealed schema')
    public=json.loads((root/'original-input/_public_cases.json').read_bytes())
    old={digest({k:v for k,v in r.items() if k not in {'id','expected'}}) for r in public}
    ids={digest(p) for p in payloads}
    if len(ids)!=12 or ids&old:raise ValueError('sealed payloads must be distinct and new')
    binding={'sha256':file_hash(path),'cases':12};record=root/'sealed-input.json'
    if record.exists() and json.loads(record.read_bytes())!=binding:raise ValueError('sealed input changed')
    write(record,binding);frozen=json.loads((root/'arms'/arm/'frozen.json').read_bytes());results=[]
    for case,payload in zip(cases,payloads):
        raw=invoke(Check(('python','_benchmark_checks.py','sealed'),timeout=10),Path(frozen['path']),
                   root/'arms'/arm/'grade-home',manifest['runner'],stdin=json.dumps(payload).encode(),sealed=True)
        try:passed=raw['passed'] and json.loads(raw['stdout'])==case['expected']
        except ValueError:passed=False
        results.append({'id':case['id'],'passed':passed,'raw':raw})
        write(root/'arms'/arm/'sealed-results.json',{'candidate':frozen['inventory_sha256'],
              'passed':sum(r['passed'] for r in results),'total':12,'cases':results})
    closed(root)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('source',type=Path);p.add_argument('calibration',type=Path)
    p.add_argument('root',type=Path);p.add_argument('--image',required=True);p.add_argument('--sdk',type=Path,required=True)
    for action in ('validate','run','grade','_work','_grade'):
        p=sub.add_parser(action);p.add_argument('root',type=Path)
        if action in ('run','grade'):p.add_argument('--approval',type=Path,required=True)
        if action.startswith('_'):p.add_argument('arm',choices=ARMS)
    args=parser.parse_args();root=args.root.resolve()
    if args.action=='prepare':result=prepare(args.source,args.calibration,root,args.image,args.sdk)
    elif args.action=='validate':result=load(root)
    elif args.action=='run':run(root,args.approval);result={'status':'ENGINEERING_CLOSED'}
    elif args.action=='grade':
        manifest=authorize(root,args.approval);closed(root)
        for arm in manifest['execution_order']:
            outcome=run_phase(root/'arms'/arm/'state','grade',
                [sys.executable,'-m','aiwork.harness_comparison','_grade',str(root),arm],Path(__file__).parents[1])
            write(root/'arms'/arm/'grade-process.json',outcome)
            if outcome['code'] or outcome['timed_out'] or not outcome['cleanup']['passed']:raise RuntimeError('grading failed closed')
        result={'status':'GRADED'}
    else:
        from .trial_budget import current
        lease=current(root/'arms'/args.arm/'state')
        if lease is None:raise ValueError('private phase requires its live controller lease')
        if lease['phase']!=('work' if args.action=='_work' else 'grade') or (root/'quarantine.json').exists():
            raise ValueError('wrong phase or quarantined comparison')
        manifest=load(root)
        if args.action=='_work':work(root,args.arm,manifest)
        else:grade(root,args.arm,manifest)
        return
    print(json.dumps({'status':result.get('status'),'approval_digest':(root/'manifest.sha256').read_text().strip()}))


if __name__=='__main__':main()
