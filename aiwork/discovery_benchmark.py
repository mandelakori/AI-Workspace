"""One prepared, matched source-supplied/source-discovery repository comparison."""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from collections.abc import Sequence
import hashlib
from dataclasses import asdict
import json
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import sys
from time import time

from .changes import delta, validate_changes
from .controller import Controller
from .httpx_benchmark import digest, file_hash, implementation, model_metadata, warm
from .lock import file_lock
from .schema import Config, Profile, Task, Check
from .selection import compare
from .trial_budget import FILE, PHASE_LIMITS, create, current, run_phase, write
from .verify import invoke, runner_status
from .workspace import inventory, snapshot

COMMIT = '4fbc6ff07215367ece731006855e732d1405992c'
ARMS = ['A', 'B']
PATHS = ('src/dotenv/variables.py', 'tests/test_nested_defaults.py')
ASSETS = Path(__file__).resolve().parents[1] / 'examples/phase61-discovery'


def order(seed: str) -> list[str]:
    return ARMS[:] if int(digest({'randomization_seed':seed}),16) % 2 == 0 else ARMS[::-1]


def commands() -> tuple[Check, ...]:
    return tuple(Check(('python','_benchmark_checks.py',name),timeout=40)
                 for name in ['public','upstream','authored'])


def upfront(source: Path) -> str:
    module=source/PATHS[0];caller=source/'src/dotenv/main.py'
    text=caller.read_bytes().decode('utf-8')
    node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='resolve_variables')
    excerpt=''.join(text.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    return (f'Verbatim starting source; no solution or repair hints. Commit {COMMIT}.\n'
            f'{PATHS[0]} SHA-256 {file_hash(module)}; complete module:\n```python\n'
            + module.read_bytes().decode('utf-8') + '\n```\n'
            f'Caller interface and existing behavior: src/dotenv/main.py lines {node.lineno}-{node.end_lineno}; '
            f'whole-file SHA-256 {file_hash(caller)}:\n```python\n' + excerpt + '\n```\n')


def source_spans(source: Path) -> list[dict]:
    caller=source/'src/dotenv/main.py'
    node=next(n for n in ast.parse(caller.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='resolve_variables')
    return [{'path':PATHS[0],'sha256':file_hash(source/PATHS[0]),'first':1,'last':len((source/PATHS[0]).read_bytes().splitlines())},
            {'path':'src/dotenv/main.py','sha256':file_hash(caller),'first':node.lineno,'last':node.end_lineno}]


def prepare(upstream: Path, root: Path, previous: Path, image: str, readiness: Path) -> dict:
    upstream=upstream.resolve(strict=True);root=root.resolve()
    actual=subprocess.run(['git','-C',str(upstream),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    dirty=subprocess.run(['git','-C',str(upstream),'status','--porcelain'],capture_output=True,text=True,check=True).stdout
    if actual!=COMMIT or dirty: raise ValueError('pinned upstream checkout must be clean')
    old=json.loads(previous.read_bytes());profile=Profile(**old['profile'])
    if (profile.location!='local' or profile.context!=8192 or profile.output_tokens!=2048
            or profile.managed or profile.engine!='ollama' or profile.harness!='opencode'
            or profile.model!='aiwork-qwen35-phase4:8k' or profile.reasoning_effort!='none'):
        raise ValueError('expected the unchanged local Qwen3.5 9B/8K profile')
    metadata=model_metadata(profile)
    if metadata!=old['model']: raise ValueError('existing model identity or configured parameters changed')
    runner=runner_status(root.parent,image)['image_id']
    if not runner or not runner.startswith('sha256:'): raise ValueError('immutable local image required')
    harness=old['harness']
    if file_hash(Path(harness['path']))!=harness['sha256']: raise ValueError('installed OpenCode changed')
    proof=json.loads(readiness.read_bytes())
    if (proof['scoped_tools_first_present_at_agent_request']!=1 or proof['result_code']!=0
            or proof['implementation_sha256']!=implementation() or not proof['readiness']['cleanup_passed']
            or proof['provider_gate']['failed_closed'] or proof['auxiliary_requests_without_tools']):
        raise ValueError('a current passing first-request inert catalog proof is required')
    root.mkdir(parents=True,exist_ok=False)
    original=root/'original-input';snapshot(upstream,original,())
    for src,dst in [('FEATURE.md','FEATURE.md'),('checks.py','_benchmark_checks.py'),('public_cases.json','_public_cases.json')]:
        shutil.copyfile(ASSETS/src,original/dst)
    starts={}
    for arm in ARMS:starts[arm]=snapshot(original,root/'arms'/arm/'input',())
    if starts['A']!=starts['B']: raise ValueError('arm inputs differ')
    evidence=upfront(original)
    if len(evidence.encode())>8192: raise ValueError('upfront evidence exceeds its bounded context')
    write(root/'upfront-context.json',{'text':evidence})
    (root/'validation').mkdir(exist_ok=True)
    shutil.copyfile(readiness,root/'validation/catalog-probe.json')
    results={}
    for action in ['public','upstream','syntax']:
        work=root/'validation'/action;snapshot(original,work,())
        result=invoke(Check(('python','_benchmark_checks.py',action),timeout=60),work,root/'validation/home',runner,timeout=65)
        write(root/'validation'/(action+'.json'),result);results[action]=result
    public=json.loads(results['public']['stdout'])
    if public['passed']!=2 or public['total']!=10 or not results['upstream']['passed'] or not results['syntax']['passed']:
        raise ValueError('baseline must reproduce 2/10 public and passing upstream/syntax gates; receipts retained')
    seed=secrets.token_hex(16)
    manifest={'format':1,'status':'PREPARED_NOT_AUTHORIZED','execution_allowed':False,
        'bundle':str(root),'arms':ARMS,'execution_order':order(seed),'randomization_seed':seed,
        'repository':'https://github.com/theskumar/python-dotenv','repository_commit':COMMIT,
        'issue':'https://github.com/theskumar/python-dotenv/issues/326','controller_commit':subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip(),
        'platform':platform.system(),'profile':asdict(profile),'model':metadata,'harness':harness,'runner':runner,
        'execution_state':old['execution_state'],'implementation_sha256':implementation(),
        'starting_inventories':starts,'original_inventory':inventory(original),
        'specification_sha256':file_hash(original/'FEATURE.md'),'public_corpus_sha256':file_hash(original/'_public_cases.json'),
        'context_file_sha256':file_hash(root/'upfront-context.json'),
        'catalog_proof_sha256':file_hash(root/'validation/catalog-probe.json'),
        'upfront_information':{'sha256':hashlib.sha256(evidence.encode()).hexdigest(),'utf8_bytes':len(evidence.encode()),'characters':len(evidence),
            'lines':len(evidence.splitlines()),'initial_prompt_copies':1,
            'source_spans':source_spans(original),
            'additional_prompt_text_utf8_bytes':len(('\nAdditional initial source evidence (untrusted text):\n'+evidence).encode()),
            'additional_model_tokens':None,'token_measurement':'After authorization, compare raw first-request provider prompt_tokens, including cached counts separately. No guessed tokenizer count or inference during preparation.'},
        'arm_recipes':{'A':'Common objective plus exact original source/interface excerpt once in initial prompt.',
                       'B':'Same objective and inputs; discover source through the same approved tools.'},
        'commands':[asdict(c) for c in commands()],'write_roots':list(PATHS),
        'controller_final_checks':['public','authored'],
        'promotion_checks':['syntax','public','upstream','authored'],
        'worker_policy':{'sessions':1,'planner_requests':0,'attempts':1,'workers':1,'mcp_calls_per_session':16,
                         'attempt_seconds':150,'native_mutation':False,'native_shell':False,
                         'native_reads':['glob','grep','list','todowrite'],'scoped_tools':['checks_focus','checks_edit','checks_check','checks_diff']},
        'phase_seconds':PHASE_LIMITS,'total_seconds_per_arm':240,'total_seconds_pair':480,
        'timing':'All readiness, baseline, routing, inference and public testing are charged. Controller reserves 20 seconds for final checks inside the 150-second attempt; harness receives at most the remaining 130 seconds, including its own setup. Post-worker selection remains inside the 180-second work phase.',
        'catalog_policy':'Owned private OpenCode server; await this location MCP connected, then require all four scoped tools on every provider request before forwarding. Unexpected tools or model, missing/schemaless catalog, relay failure or nonzero harness exit stops and quarantines the pair. No schema/prompt/model argument rewriting; fixed session title prevents auxiliary title inference.',
        'evidence_limits':{'agent_stdout_bytes':8*1024*1024,'provider_wire_bytes':16*1024*1024},
        'warm_protocol':{'order':order(seed),'neutral_requests_per_arm':1,'max_tokens':4,'prompt':'Reply with exactly READY.',
                         'temperature':0,'reasoning_effort':profile.reasoning_effort,'resident_context_required':8192,
                         'minimum_residency_ttl_seconds':185,'fresh_harness_home':True,'no_restart_unload_or_model_changes':True,
                         'exclusive_operator_window_required':True,'cache_limitation':'No claim of purging all KV caches; preserve residency receipts and cache counters. One randomized pair is exploratory.'},
        'selection':'Final in-policy candidate versus original baseline, using the same complete public corpus. Reject syntax failures, upstream regressions and lost public passes; deterministic ties keep baseline. Record authored-test status separately; retain all edit/check traces and intermediate public observations without claiming every intermediate snapshot was ranked.',
        'milestones':{'first_applied_edit_at_most':8,'first_public_test_at_most':12},
        'completion':'All ten public cases, frozen whole upstream suite (documented platform skips), authored tests, twelve fresh sealed cases and both operation milestones; no scope violations or mid-run implementation guidance.',
        'sealed_policy':{'required_cases':12,'same_cases_both_arms':True,'author_after_both_engineering_close_and_freeze':True,
                         'private_path':'private/cases.json','expectations_mounted':False,'feedback_to_worker':False},
        'cleanup_policy':'Existing trial-budget ownership checks, container cleanup and interruption quarantine; private server owns a separate process group/job and relay sockets are closed. No extensions, resumes, retries or service changes.',
        'baseline':{'public':public,'upstream':results['upstream'],'syntax':results['syntax']},
        'authorization':'Separate explicit approval of this canonical digest and exactly [A,B]; no grant created by preparation.'}
    write(root/'manifest.json',manifest)
    (root/'manifest.sha256').write_text(digest(manifest)+'\n',encoding='utf-8')
    write(root/'operator-approval.example.json',{'approval_digest':digest(manifest),'authorize':ARMS,'operator_approved':False})
    return manifest


def load(root: Path) -> dict:
    manifest=json.loads((root/'manifest.json').read_bytes())
    if (digest(manifest)!=(root/'manifest.sha256').read_text().strip()
            or manifest['status']!='PREPARED_NOT_AUTHORIZED' or manifest['execution_allowed']
            or manifest['arms']!=ARMS or manifest['execution_order']!=order(manifest['randomization_seed'])):
        raise ValueError('manifest, preparation state or randomized order changed')
    if implementation()!=manifest['implementation_sha256']: raise ValueError('approved execution implementation changed')
    if file_hash(Path(manifest['harness']['path']))!=manifest['harness']['sha256']: raise ValueError('harness changed')
    if inventory(root/'original-input')!=manifest['original_inventory']: raise ValueError('frozen original changed')
    for arm in ARMS:
        if inventory(root/'arms'/arm/'input')!=manifest['starting_inventories'][arm]: raise ValueError('arm input changed')
    if file_hash(root/'upfront-context.json')!=manifest['context_file_sha256']: raise ValueError('upfront evidence changed')
    if file_hash(root/'validation/catalog-probe.json')!=manifest['catalog_proof_sha256']: raise ValueError('catalog proof changed')
    return manifest


def authorize(root: Path, grant: Path) -> dict:
    manifest=load(root)
    if json.loads(grant.read_bytes())!={'approval_digest':digest(manifest),'authorize':ARMS,'operator_approved':True}:
        raise ValueError('explicit approval of this exact digest and both arms is required')
    return manifest


def config(root: Path, arm: str, manifest: dict) -> Config:
    return Config(root/'arms'/arm/'state',(Profile(**manifest['profile']),),opencode=manifest['harness']['path'],
                  verification_image=manifest['runner'],execution_state=Path(manifest['execution_state']),local_slots=1)


def task(root: Path, arm: str, manifest: dict) -> Task:
    work=root/'arms'/arm/'input';checks=commands()
    return Task((root/'original-input/FEATURE.md').read_text(encoding='utf-8'),work,'agent','dotenv-nested-defaults',
                tuple(sorted({n.split('/')[0] for n in manifest['original_inventory']})),(),(checks[0],checks[2]),
                location='local',profile=manifest['profile']['id'],mode='engineering',write_roots=PATHS,
                commands=checks,baseline_check=True,min_context=8192,agent_role='implementation',timeout=150,attempts=1)


def score(root, arm, source, destination, manifest):
    snapshot(source,destination,());validate_changes(delta(manifest['starting_inventories'][arm],inventory(destination)),PATHS)
    outputs={}
    for action in ['syntax','public','upstream','authored']:
        current()
        outputs[action]=invoke(Check(('python','_benchmark_checks.py',action),timeout=40),destination,destination.parent/'home',manifest['runner'])
        write(destination.parent/('candidate-'+action+'.json'),outputs[action])
    try:public=json.loads(outputs['public']['stdout'])
    except ValueError:public={'cases':[],'passed':None,'total':10,'evaluation_complete':False}
    return {'corpus_sha256':manifest['public_corpus_sha256'],'runner':manifest['runner'],'total':10,
            'compiled':outputs['syntax']['passed'],'syntax_passed':outputs['syntax']['passed'],
            'upstream_passed':outputs['upstream']['passed'],'authored_tests_passed':outputs['authored']['passed'],
            'missing':[] if (destination/PATHS[1]).exists() else [PATHS[1]],
            'cases':[{'case':i,'verdict':'pass' if r['passed'] else 'fail'} for i,r in enumerate(public['cases'],1)],
            'passed_cases':public['passed'],'public':public,'outputs':outputs}


def milestones(state: Path, supplied_spans: Sequence[dict] = ()) -> dict:
    rows=[]
    for path in state.glob('runs/*/attempt-*/mcp.jsonl'):
        rows.extend(json.loads(s) for s in path.read_text().splitlines() if s.strip())
    first_edit=next((r['call'] for r in rows if r.get('tool')=='edit' and r.get('applied')),None)
    first_check=next((r['call'] for r in rows if r.get('tool')=='check'),None)
    supplied={(s['path'],s['sha256']):set(range(s['first'],s['last']+1)) for s in supplied_spans}
    seen=defaultdict(set);returned=repeated=upfront_repeated=0
    for row in rows:
        if row.get('tool')!='focus' or not row.get('source'):continue
        marks=set(range(row['line'],row['line']+len(row['source'].splitlines())))
        key=(row['path'],row['sha256']);returned+=len(marks)
        repeated+=len(marks&seen[key]);upfront_repeated+=len(marks&supplied.get(key,set()));seen[key].update(marks)
    metrics=[];usages=[];first_edit_time=first_check_time=None
    budget=state/FILE
    origin=json.loads(budget.read_bytes())['phases']['work'].get('started_utc') if budget.exists() else None
    for path in state.glob('runs/*/attempt-*'):
        if (path/'agent-metrics.json').exists():metrics.append(json.loads((path/'agent-metrics.json').read_bytes()))
        for response in sorted(path.glob('provider-response-*.sse')):
            usage=None
            for line in response.read_text(errors='replace').splitlines():
                try:
                    packet=json.loads(line.removeprefix('data:').strip())
                    if packet.get('usage'):usage=packet['usage']
                except (ValueError,AttributeError):pass
            usages.append({'response':response.name,'last_usage':usage})
        trace=path/'agent.jsonl'
        if not trace.exists():continue
        for line in filter(str.strip,trace.read_text().splitlines()):
            try:
                event=json.loads(line);part=event.get('part',{});tool=part.get('tool');detail=part.get('state',{})
                output=json.loads(detail.get('output','{}'))
                ended=detail.get('time',{}).get('end')
                elapsed=round(ended/1000-origin,3) if origin is not None and ended is not None else None
                if tool=='checks_edit' and output.get('applied') and first_edit_time is None:first_edit_time=elapsed
                if tool=='checks_check' and 'remaining_calls' in output and first_check_time is None:first_check_time=elapsed
            except (ValueError,TypeError,AttributeError):pass
    first_usage=usages[0]['last_usage'] if usages else None
    return {'first_successful_edit_operation':first_edit,'first_public_test_operation':first_check,
            'first_edit_seconds_from_engineering_start':first_edit_time,'first_test_seconds_from_engineering_start':first_check_time,
            'edit_by_8':first_edit is not None and first_edit<=8,'test_by_12':first_check is not None and first_check<=12,
            'edit_rejections':sum(r.get('tool')=='edit' and not r.get('applied',False) for r in rows),
            'duplicates_suppressed':sum(r.get('already_inspected',False) for r in rows),
            'diagnostic_reinspections':sum(r.get('reinspection_after_edit_error',False) for r in rows),
            'returned_source_lines':returned,'unchanged_version_tool_overlap_lines':repeated,
            'lines_repeating_upfront_evidence':upfront_repeated,'harness_metrics':metrics,'raw_provider_usage':usages,
            'first_provider_prompt_tokens':first_usage.get('prompt_tokens') if first_usage else None}


def quarantine(state: Path, reason: str):
    with file_lock((state/FILE).with_suffix('.lock')):
        value=json.loads((state/FILE).read_bytes());value.update(quarantined=True,quarantine_reason=reason);write(state/FILE,value)


def work(root: Path, arm: str, manifest: dict):
    cfg=config(root,arm,manifest);out=root/'arms'/arm
    extra=json.loads((root/'upfront-context.json').read_bytes())['text'] if arm=='A' else ''
    controller=Controller(cfg,initial_context=extra)
    result=controller.run_submitted(controller.submit_task(task(root,arm,manifest)))
    write(out/'engineering-result.json',result)
    attempts=sorted(cfg.state.glob('runs/*/attempt-*'))
    if len(attempts)!=1: quarantine(cfg.state,'expected exactly one attempt');raise ValueError('attempt count mismatch')
    attempt=attempts[0]
    provider=json.loads((attempt/'provider-gate.json').read_bytes()) if (attempt/'provider-gate.json').exists() else {}
    process=json.loads((attempt/'agent-process.json').read_bytes()) if (attempt/'agent-process.json').exists() else {}
    if (provider.get('failed_closed',True) or not provider.get('requests')
            or process.get('code',1)!=0 or process.get('timed_out',True) or process.get('truncated',True)):
        quarantine(cfg.state,'catalog, harness or inference interruption failure');raise ValueError('comparison stopped before candidate grading')
    incumbent_public=manifest['baseline']['public']
    incumbent={'corpus_sha256':manifest['public_corpus_sha256'],'runner':manifest['runner'],'total':10,'compiled':True,
               'missing':[PATHS[1]],'cases':[{'case':i,'verdict':'pass' if r['passed'] else 'fail'} for i,r in enumerate(incumbent_public['cases'],1)]}
    candidate=score(root,arm,attempt/'workspace',out/'public-selection',manifest)
    decision=compare(incumbent,candidate,protect_passing=True)
    if not candidate['upstream_passed']:decision.update(accepted=False,reason='upstream_regression')
    chosen=out/'public-selection' if decision['accepted'] else out/'input'
    public=candidate['public'] if decision['accepted'] else incumbent_public
    frozen=out/'frozen';frozen_inventory=snapshot(chosen,frozen,())
    measured=milestones(cfg.state,manifest['upfront_information']['source_spans'] if arm=='A' else ())
    write(out/'selection.json',{'decision':decision,'candidate':candidate,'milestones':measured})
    write(out/'frozen.json',{'path':str(frozen),'inventory':frozen_inventory,'inventory_sha256':digest(frozen_inventory),
          'frozen_at':time(),'model_source_delivery':decision['accepted'],'public':public,
          'authored_tests_passed':decision['accepted'] and candidate['authored_tests_passed'],
          'milestones':measured})


def closed(root: Path):
    for arm in ARMS:
        state=root/'arms'/arm/'state';data=json.loads((state/FILE).read_bytes())
        if data.get('quarantined') or data['phases']['work']['status']!='FINISHED' or not (state.parent/'frozen.json').exists():
            raise ValueError('both engineering phases must close cleanly and freeze before sealed input exists')


def grade(root: Path, arm: str, manifest: dict):
    closed(root);path=root/'private/cases.json';cases=json.loads(path.read_bytes())
    if len(cases)!=12 or len({c['id'] for c in cases})!=12:raise ValueError('exactly twelve uniquely named fresh cases required')
    payloads=[{k:v for k,v in case.items() if k not in {'expected','id'}} for case in cases]
    if any(set(p) not in ({'value','env'},{'stream'}) for p in payloads):raise ValueError('unsupported sealed input fields')
    public=json.loads((root/'original-input/_public_cases.json').read_bytes())
    prior={digest({k:v for k,v in c.items() if k not in {'expected','id'}}) for c in public}
    identities={digest(p) for p in payloads}
    if len(identities)!=12 or identities & prior:raise ValueError('sealed inputs must be distinct and new, not renamed public cases')
    if path.stat().st_mtime<=max(json.loads((root/'arms'/a/'frozen.json').read_bytes())['frozen_at'] for a in ARMS):
        raise ValueError('cases must be authored after both candidates freeze')
    identity={'sha256':file_hash(path),'count':12};binding=root/'sealed-input.json'
    if binding.exists() and json.loads(binding.read_bytes())!=identity:raise ValueError('sealed cases changed between arms')
    write(binding,identity)
    saved=json.loads((root/'arms'/arm/'frozen.json').read_bytes());source=Path(saved['path'])
    if inventory(source)!=saved['inventory']:raise ValueError('frozen candidate changed')
    results=[]
    for case in cases:
        current();payload={k:v for k,v in case.items() if k not in {'expected','id'}}
        if set(payload) not in ({'value','env'},{'stream'}):raise ValueError('unsupported sealed input fields')
        raw=invoke(Check(('python','_benchmark_checks.py','sealed'),timeout=10),source,root/'arms'/arm/'grade-home',manifest['runner'],
                   stdin=json.dumps(payload).encode(),sealed=True)
        try:passed=raw['passed'] and json.loads(raw['stdout'])==case['expected']
        except ValueError:passed=False
        results.append({'id':case['id'],'passed':passed,'raw':raw})
        write(root/'arms'/arm/'sealed-results.json',{'candidate':saved['inventory_sha256'],'cases':results,'passed':sum(r['passed'] for r in results),'total':12})
    if inventory(source)!=saved['inventory']:raise ValueError('candidate changed during grading')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('upstream',type=Path);p.add_argument('root',type=Path);p.add_argument('--profile-manifest',type=Path,required=True);p.add_argument('--image',required=True);p.add_argument('--readiness',type=Path,required=True)
    for action in ['validate','run','grade']:
        p=sub.add_parser(action);p.add_argument('root',type=Path)
        if action in {'run','grade'}:p.add_argument('--approval',type=Path,required=True)
    p=sub.add_parser('_phase');p.add_argument('root',type=Path);p.add_argument('arm',choices=ARMS);p.add_argument('phase',choices=PHASE_LIMITS)
    args=parser.parse_args();root=args.root.resolve()
    if args.action=='prepare':
        manifest=prepare(args.upstream,root,args.profile_manifest,args.image,args.readiness);print(json.dumps({'status':manifest['status'],'digest':digest(manifest),'order':manifest['execution_order']}));return
    if args.action=='validate':
        manifest=load(root);print(json.dumps({'status':manifest['status'],'digest':digest(manifest),'order':manifest['execution_order']}));return
    if args.action=='_phase':
        current(root/'arms'/args.arm/'state');manifest=load(root)
        {'warm':warm,'work':work,'grade':grade}[args.phase](root,args.arm,manifest);return
    manifest=authorize(root,args.approval)
    with file_lock(root/'comparison.lock'):
        if args.action=='run':
            if any((root/'arms'/a/'state'/FILE).exists() for a in ARMS):raise ValueError('one-shot comparison cannot resume or restart')
            for arm in manifest['execution_order']:
                state=root/'arms'/arm/'state';create(state,digest(manifest),arm,quotas={'sessions':1,'planner_requests':0})
                for phase in ['warm','work']:
                    result=run_phase(state,phase,[sys.executable,'-m','aiwork.discovery_benchmark','_phase',str(root),arm,phase],Path(__file__).parents[1])
                    write(state.parent/(phase+'-process.json'),result)
                    data=json.loads((state/FILE).read_bytes())
                    if result['code'] or result['timed_out'] or data.get('quarantined') or not result['cleanup']['passed']:return
            results={a:json.loads((root/'arms'/a/'frozen.json').read_bytes()) for a in ARMS}
            tokens={a:results[a]['milestones']['first_provider_prompt_tokens'] for a in ARMS}
            delta_tokens=tokens['A']-tokens['B'] if all(type(t) is int for t in tokens.values()) else None
            write(root/'engineering-comparison.json',{'arms':results,'first_prompt_token_delta_A_minus_B':delta_tokens,
                  'interpretation':'Observed prompt delta includes wrappers/path token differences; a single pair is not a reliable success-rate estimate.'})
        else:
            closed(root)
            for arm in manifest['execution_order']:
                state=root/'arms'/arm/'state'
                result=run_phase(state,'grade',[sys.executable,'-m','aiwork.discovery_benchmark','_phase',str(root),arm,'grade'],Path(__file__).parents[1])
                write(state.parent/'grade-process.json',result)
                if result['code'] or result['timed_out'] or not result['cleanup']['passed']:return


if __name__=='__main__':main()
