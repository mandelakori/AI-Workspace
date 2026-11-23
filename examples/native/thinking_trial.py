"""One reviewed A100 thinking pair using the existing native verifier and trial budgets."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
import sys
from time import monotonic, time

import ledger_trial as native
from aiwork.oracle import evaluate, load_cases
from aiwork.selection import score


MODES = ('off', 'on')
LIMITS = {'warm': 20, 'work': 270, 'grade': 90}
WORKER = dict(timeout=210, attempts=1, min_context=65536, tool_operations=24,
              edit_reserve=4, public_test_reserve=4, model_requests=18, compaction_limit=1)
FINAL_COUNT = 12
OBJECTIVE = (
    'Reconstruct the authorized byte-stride utility in candidate.c. Read ghidra.json '
    'and examples.json for its input limits, decimal-step handling, output and exit '
    'status. Inspect the starter source and replace its placeholder using a small '
    'hash-bound edit. Run approved command 0 to compile and check all five public '
    'observations. Command 1 only compiles. Preserve exact stdout and stderr. '
    'Use C11 and the standard library. Only candidate.c may change.'
)


def make_task(root: Path, manifest: dict) -> native.Task:
    task = native.task(root, manifest)
    return replace(task, objective=OBJECTIVE, category='native-stride-thinking', **WORKER)


def bindings(root: Path) -> dict:
    return {name: native.inventory(root / name) for name in ('input', 'target', 'development')} | {
        'script': native.file_hash(Path(__file__)), 'helpers': native.file_hash(Path(native.__file__)),
        'controller': native.implementation(), 'template_evidence': native.inventory(root / 'template'),
        'exclusions': native.file_hash(root / 'exclusions.json'),
    }


def prepare(pair: Path, archive: Path, template: Path, settings: Path) -> None:
    pair.mkdir()
    old = native.read(archive / 'run.json')
    cfg = native.Config.load(settings)
    original = next(p for p in cfg.profiles if p.id == native.ARM)
    profile = replace(original, context=65536, output_tokens=4096, temperature=0, seed=1729,
                      reasoning_effort='', enable_thinking=False)
    binary = native.opencode_path(cfg.opencode)
    if not binary or native.runner_status(pair, old['image'])['image_id'] != old['image']:
        raise ValueError('pinned existing Docker runner or OpenCode unavailable')
    receipt = native.read(template / 'receipt.json')
    if (receipt['generation_requests'] != 0 or not receipt['owned_forward_closed']
            or native.file_hash(template / 'pinned.jinja') != receipt['endpoint']['template_sha256']
            or receipt['endpoint']['model_path'] != profile.model
            or len(receipt['vectors']) != 4):
        raise ValueError('required active-server template validation is missing')

    off = pair / 'off'
    target = native.snapshot(archive / 'target', off / 'target', ())
    development = native.snapshot(archive / 'development', off / 'development', ())
    if target != old['target'] or development != old['development']:
        raise ValueError('archived stride target or public corpus changed')
    work = off / 'input'
    work.mkdir()
    for name, origin in [('examples.json', archive / 'candidate/examples.json'),
                         ('binary.json', archive / 'analysis/binary/analysis.json'),
                         ('ghidra.json', archive / 'analysis/ghidra-00/analysis.json')]:
        shutil.copyfile(origin, work / name)
    if not native.read(work / 'ghidra.json').get('decompilation'):
        raise ValueError('pinned stride decompilation missing')
    public = load_cases(work / 'examples.json', public=True)
    if len(public) != 5 or [{k: v for k, v in x.items() if k not in {'name', 'group'}}
                            for x in public] != load_cases(off / 'development/cases.json'):
        raise ValueError('archived public evidence does not match the frozen corpus')
    (work / native.OUTPUT).write_bytes(b'int main(void) { return 1; }\n')
    build, candidate, reference = (native.recipe(old, key) for key in ('build_candidate', 'candidate', 'reference'))
    native.install_public_check(work, build, candidate)
    stimuli = {native.digest([row.get('stdin', ''), row.get('argv', [])]) for row in public}
    for inputs in archive.glob('final/*/inputs.json'):
        stimuli.update(native.digest(list(case.stimulus)) for case in native.read_inputs(inputs, 512))
    native.write(off / 'exclusions.json', {'stimulus_sha256': sorted(stimuli)})
    native.snapshot(template, off / 'template', ('pinned.jinja', 'receipt.json'))
    reference_result = evaluate(replace(reference, oracle='cases.json'), off / 'target', pair / 'home',
                                off / 'development', old['image'], 60, None, public=True)
    native.snapshot(work, pair / 'baseline-build', ())
    baseline = score(build, candidate, work / 'examples.json', pair / 'baseline-build', pair / 'home',
                     old['image'], monotonic() + 60, pair / 'STOP', [])
    if reference_result['passed_cases'] != 5 or not baseline['compiled'] or baseline['passed_cases'] != 0:
        raise ValueError('reference or starting baseline differs from the review contract')
    native.write(pair / 'baseline.json', {'placeholder': baseline, 'reference': reference_result})

    common = {key: old[key] for key in ('image', 'build_candidate', 'candidate', 'reference')}
    common.update(status='PREPARED_NOT_AUTHORIZED', objective=OBJECTIVE, order=list(MODES),
                  target=target, development=development, baseline={'compiled': True, 'score': 0, 'total': 5},
                  limits=LIMITS, worker=WORKER, capture=native.CAPTURE, final_count=FINAL_COUNT,
                  deliverables=[native.OUTPUT], ssh=cfg.ssh, execution_state=str(cfg.execution_state or cfg.state),
                  opencode={'path': binary, 'sha256': native.file_hash(Path(binary))}, endpoint=receipt['endpoint'])
    on = pair / 'on'
    native.snapshot(off, on, ())
    for mode in MODES:
        root = pair / mode
        arm = replace(profile, enable_thinking=mode == 'on')
        manifest = common | {'mode': mode, 'profile': asdict(arm), 'generation': native.request_options(arm),
                             'bindings': bindings(root)}
        native.write(root / 'manifest.json', manifest)
        (root / 'manifest.sha256').write_text(native.digest(manifest) + '\n', encoding='ascii')
    pair_manifest(pair)


def pair_manifest(pair: Path) -> dict[str, dict]:
    manifests = {}
    for mode in MODES:
        root = pair / mode
        m = native.read(root / 'manifest.json')
        p = native.Profile(**m['profile'])
        p.validate()
        make_task(root, m).validate()
        if (native.digest(m) != (root / 'manifest.sha256').read_text().strip()
                or bindings(root) != m['bindings'] or mode != m['mode'] or p.enable_thinking is not (mode == 'on')
                or (p.context, p.output_tokens, p.temperature, p.seed) != (65536, 4096, 0, 1729)
                or p.reasoning_effort or p.managed or p.location != 'a100' or p.engine != 'llamacpp'
                or p.harness != 'opencode' or p.id != native.ARM or p.model != m['endpoint']['model_path']
                or m['generation'] != native.request_options(p) or m['limits'] != LIMITS or m['worker'] != WORKER
                or m['capture'] != native.CAPTURE or m['objective'] != OBJECTIVE or m['order'] != list(MODES)
                or m['final_count'] != FINAL_COUNT or m['deliverables'] != [native.OUTPUT]
                or m['target'] != m['bindings']['target'] or m['development'] != m['bindings']['development']
                or native.file_hash(Path(m['opencode']['path'])) != m['opencode']['sha256']):
            raise ValueError(f'frozen {mode} arm drifted')
        manifests[mode] = m
    def normalize(m):
        return {k: v for k, v in m.items() if k not in {'mode', 'profile', 'generation'}} | {
            'profile': {k: v for k, v in m['profile'].items() if k != 'enable_thinking'},
            'generation': {k: v for k, v in m['generation'].items() if k != 'chat_template_kwargs'},
        }
    if normalize(manifests['off']) != normalize(manifests['on']):
        raise ValueError('paired settings differ beyond thinking mode')
    return manifests


def work(root: Path, manifest: dict) -> None:
    ctl = native.Controller(native.config(root, manifest))
    result = ctl.run_submitted(ctl.submit_task(make_task(root, manifest), profile_id=native.ARM))
    native.write(root / 'engineering-result.json', result)
    attempt, = Path(result['artifacts']).glob('attempt-*')
    receipt = native.read(attempt / 'execution-receipt.json')
    if receipt['status'] not in {'completed', 'resource_exhausted'} or not receipt['cleanup_passed']:
        raise RuntimeError('worker or cleanup failed closed')
    gate = native.read(attempt / 'provider-gate.json')
    for req in (r for r in gate['requests'] if r['forwarded']):
        body = native.read(attempt / f"provider-forwarded-{req['request']:03}.json")
        if (body.get('reasoning_effort') or body.get('chat_template_kwargs') != manifest['generation']['chat_template_kwargs']):
            raise ValueError('forwarded thinking mode drifted')
    checkpoint = attempt / 'checkpoint.json'
    if result['status'] != 'verified' or not checkpoint.exists():
        return
    calls = [json.loads(line) for line in (attempt / 'mcp.jsonl').read_text().splitlines() if line.strip()]
    selected = native.read(checkpoint)
    if (receipt['status'] == 'completed' and selected['selection']['accepted'] and selected['public']['passed_cases'] == 5
            and any(c['tool'] == 'edit' and c.get('applied') for c in calls)
            and any(c['tool'] == 'check' and c.get('index') == 0 and c.get('passed') for c in calls)):
        native.write(root / 'qualified.json', {'workspace': str(attempt / 'workspace'),
                                               'source': selected['inventory'][native.OUTPUT]})


def phase(root: Path, name: str) -> None:
    result = native.run_phase(root / 'state', name, [sys.executable, str(Path(__file__).resolve()),
                              '_' + name, str(root.parent), root.name], native.REPO)
    native.write(root / (name + '-process.json'), result)
    if result['code'] or result['timed_out'] or not result['cleanup']['passed']:
        raise RuntimeError(f'{name} failed closed; stop the pair')


def run(root: Path, m: dict, grant: dict) -> None:
    pair = root.parent
    with native.file_lock(pair / 'pair.lock'):
        if ((root / 'execution-started.json').exists() or (pair / 'private').exists()
                or shutil.disk_usage(root).free < sum(native.CAPTURE.values())):
            raise ValueError('consumed arm, premature private data, or insufficient disk')
        if root.name == 'on':
            prior = native.read(pair / 'off/state' / native.FILE)
            if (prior['quarantined'] or prior['phases']['work']['status'] != 'FINISHED'
                    or not (pair / 'off/engineering-closed.json').is_file()):
                raise ValueError('OFF must finish without a safety failure before ON')
        if native.runner_status(root, m['image'])['image_id'] != m['image']:
            raise ValueError('pinned image unavailable')
        native.write(root / 'execution-started.json', {'approval': native.digest(m), 'started': time()})
        native.write(root / 'operator-approval.json', grant)
        native.create(root / 'state', native.digest(m), root.name, LIMITS, reviewed_caps=LIMITS,
                      quotas={'sessions': 1, 'planner_requests': 0})
        phase(root, 'warm')
        phase(root, 'work')
        qualified = root / 'qualified.json'
        frozen_hash = None
        if qualified.exists():
            q = native.read(qualified)
            frozen = native.snapshot(Path(q['workspace']), root / 'frozen', (native.OUTPUT,))
            if frozen != {native.OUTPUT: q['source']}:
                raise ValueError('selected candidate drifted before freeze')
            native.write(root / 'frozen.json', frozen)
            frozen_hash = native.digest(frozen)
        native.write(root / 'engineering-closed.json', {'frozen_sha256': frozen_hash, 'closed_at': time()})


def final_inputs(root: Path) -> Path:
    pair = root.parent
    completed = [native.read(pair / mode / 'engineering-closed.json') for mode in MODES]
    for mode in MODES:
        state = native.read(pair / mode / 'state' / native.FILE)
        if state['quarantined'] or state['phases']['work']['status'] != 'FINISHED':
            raise ValueError('both engineering arms must close safely before grading')
    frozen = completed[MODES.index(root.name)]['frozen_sha256']
    if not frozen or frozen != native.digest(native.inventory(root / 'frozen')):
        raise ValueError('arm has no eligible frozen candidate')
    cases = pair / 'private/cases.json'
    rows = native.read_inputs(cases, FINAL_COUNT)
    if (len(rows) != FINAL_COUNT or cases.stat().st_mtime <= max(x['closed_at'] for x in completed)
            or set(native.read(root / 'exclusions.json')['stimulus_sha256'])
            & {native.digest(list(case.stimulus)) for case in rows}):
        raise ValueError('expected 12 fresh post-closure cases disjoint from historical cases')
    binding = pair / 'sealed-input.sha256'
    expected = native.file_hash(cases)
    if binding.exists() and binding.read_text().strip() != expected:
        raise ValueError('paired final suite changed')
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'validate', 'run', 'grade', '_warm', '_work', '_grade'))
    parser.add_argument('pair', type=Path)
    parser.add_argument('mode', nargs='?', choices=MODES)
    for name in ('archive', 'template', 'config', 'approval'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    pair = args.pair.resolve()
    if args.action == 'prepare':
        prepare(pair, args.archive, args.template, args.config)
    manifests = pair_manifest(pair)
    if args.action not in {'prepare', 'validate'}:
        m = manifests[args.mode]
        root = pair / args.mode
        if args.action in {'run', 'grade'}:
            grant = {'approval_digest': native.digest(m), 'authorize': [args.mode], 'operator_approved': True}
            if not args.approval or native.read(args.approval) != grant:
                raise ValueError('exact separate arm approval required')
            if args.action == 'run':
                run(root, m, grant)
            else:
                with native.file_lock(pair / 'pair.lock'):
                    final_inputs(root)
                    phase(root, 'grade')
        else:
            lease = native.current(root / 'state')
            if not lease or lease['phase'] != args.action[1:]:
                raise ValueError('matching measured phase lease required')
            if args.action == '_warm':
                ready = native.endpoint(native.config(root, m))
                if ready != m['endpoint']:
                    raise ValueError('A100 template, model or slot drifted')
                native.write(root / 'warm-readiness.json', ready)
            elif args.action == '_work':
                work(root, m)
            else:
                cases = final_inputs(root)
                (pair / 'sealed-input.sha256').write_text(native.file_hash(cases) + '\n', encoding='ascii')
                native.write(root / 'run.json', m)
                report = native.grade(native.Controller(native.config(root, m)), root, cases, [], 4)
                native.write(root / 'grade-result.json', report)
    print(json.dumps({mode: native.digest(m) for mode, m in manifests.items()}))


if __name__ == '__main__':
    main()
