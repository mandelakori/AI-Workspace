"""Bind one reviewed ledger trial to the existing controller and native verifier."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import asdict, replace
from pathlib import Path
from time import time
from urllib.request import ProxyHandler, build_opener

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from aiwork.controller import Controller
from aiwork.evidence_capture import DEFAULT_CAPTURE_BYTES, DEFAULT_HEADROOM_BYTES
from aiwork.harness import opencode_path, request_options
from aiwork.http import NoRedirect, request
from aiwork.httpx_benchmark import digest, file_hash, implementation
from aiwork.lock import file_lock
from aiwork.native import grade, install_public_check, read_inputs, recipe
from aiwork.oracle import evaluate, load_cases
from aiwork.remote import a100_session
from aiwork.schema import Check, Config, Profile, Task
from aiwork.trial_budget import FILE, create, current, run_phase, write
from aiwork.verify import runner_status
from aiwork.workspace import inventory, snapshot


ARM = 'a100-existing'
LIMITS = {'warm': 20, 'work': 900, 'grade': 120}
RESOURCES = dict(timeout=720, attempts=1, min_context=65536, tool_operations=96,
                 edit_reserve=8, public_test_reserve=8, model_requests=64, compaction_limit=4)
OUTPUT = 'candidate.c'
FINAL_CASES = 32
CAPTURE = {'limit_bytes': DEFAULT_CAPTURE_BYTES, 'headroom_bytes': DEFAULT_HEADROOM_BYTES}
OBJECTIVE = (
    'Reconstruct the approved line-oriented account ledger in candidate.c, from scratch. '
    'Read binary.json, ghidra.json and examples.json for the public evidence. '
    'Each process starts at balance zero and reads commands until EOF. Preserve framing, '
    'parsing, state transitions, and exact stdout, stderr and exit behavior. '
    'Use C11 and the standard library only. Run public command 0 to compile and compare '
    'all 18 approved observations. Command 1 compiles only. Work with small hash-bound '
    'edits. Only candidate.c may change. No external tools, alternate implementation '
    'inputs or post-freeze feedback are available.'
)


def read(path: Path):
    return json.loads(path.read_bytes())


def config(root: Path, manifest: dict) -> Config:
    return Config(root / 'state', profiles=(Profile(**manifest['profile']),),
                  opencode=manifest['opencode']['path'], ssh=manifest['ssh'],
                  execution_state=Path(manifest['execution_state']),
                  verification_image=manifest['image'])


def task(root: Path, manifest: dict) -> Task:
    compiler, candidate = (recipe(manifest, key) for key in ('build_candidate', 'candidate'))
    public = Check(('{python}', 'native_feedback.py', json.dumps(asdict(compiler)),
                    json.dumps(asdict(candidate))), 30)
    return Task(OBJECTIVE, root / 'input', 'agent', 'native-ledger-a100', (), (OUTPUT,),
                (compiler, candidate), profile=ARM, location='a100', mode='engineering',
                write_roots=(OUTPUT,), commands=(public, compiler), rank_public=True, **RESOURCES)


def endpoint(cfg: Config) -> dict:
    profile = cfg.profiles[0]
    base = profile.endpoint.removesuffix('/v1')
    with a100_session(cfg, profile, dispatch=False, timeout=12) as forward:
        if request(base + '/health', timeout=2).get('status') != 'ok':
            raise ValueError('A100 endpoint is unhealthy')
        props = request(base + '/props', timeout=2)
        models = request(base + '/v1/models', timeout=2)
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(base + '/slots', timeout=2) as response:
            slots = json.loads(response.read(65537))
        if (props['model_path'] != profile.model or props['model_ftype'] != 'Q6_K'
                or profile.model not in {model['id'] for model in models['data']}
                or props['total_slots'] != 1 or len(slots) != 1
                or slots[0].get('is_processing') is not False or slots[0]['n_ctx'] < profile.context):
            raise ValueError('A100 model or idle context slot does not match this trial')
    if forward.poll() is None:
        raise RuntimeError('owned SSH forward did not close')
    return {key: props[key] for key in ('model_path', 'model_ftype', 'build_info', 'total_slots')} | {
        'slot_context': slots[0]['n_ctx'], 'idle': True, 'generation_requests': 0,
        'template_sha256': hashlib.sha256(props['chat_template'].encode()).hexdigest(),
    }


def bindings(root: Path) -> dict:
    return {name: inventory(root / name) for name in ('target', 'input', 'development')} | {
        'exclusions': file_hash(root / 'exclusions.json'), 'runner': file_hash(Path(__file__)),
        'controller': implementation(),
    }


def prepare(root: Path, source: Path, public: Path, static: Path, config_file: Path,
            prior_suites: list[Path]) -> dict:
    root.mkdir()
    old = read(source / 'run.json')
    public_run = read(public / 'run.json')
    if old['target'] != public_run['target'] or old['image'] != public_run['image']:
        raise ValueError('public observations and target must share the pinned fixture')
    if snapshot(source / 'target', root / 'target', ()) != old['target']:
        raise ValueError('target bytes differ from archived receipt')
    if snapshot(public / 'development', root / 'development', ()) != public_run['development']:
        raise ValueError('public oracle bytes differ from archived receipt')
    work = root / 'input'
    work.mkdir()
    shutil.copyfile(public / 'candidate/examples.json', work / 'examples.json')
    observed = load_cases(work / 'examples.json', public=True)
    expected = load_cases(root / 'development/cases.json')
    if len(expected) != 18 or [{k: v for k, v in row.items() if k not in {'name', 'group'}}
                               for row in observed] != expected:
        raise ValueError('public examples differ from the archived observations')
    for output, folder in [('binary.json', 'elf-metadata'), ('ghidra.json', 'elf-ghidra')]:
        result = read(static / folder / 'analysis.json')
        if result['binary'] != 'reference.elf' or (output == 'ghidra.json' and not result.get('decompilation')):
            raise ValueError('required target analysis missing')
        if inventory(static / folder / 'target') != old['target']:
            raise ValueError('static evidence is not bound to this binary')
        shutil.copyfile(static / folder / 'analysis.json', work / output)
    install_public_check(work, recipe(old, 'build_candidate'), recipe(old, 'candidate'))
    exclusion_hashes = {digest([row.get('stdin', ''), row.get('argv', [])]) for row in expected}
    for path in prior_suites:
        exclusion_hashes.update(digest(list(case.stimulus)) for case in read_inputs(path, 512))
    write(root / 'exclusions.json', {'stimulus_sha256': sorted(exclusion_hashes)})

    existing = Config.load(config_file)
    profile = next(p for p in existing.profiles if p.id == ARM)
    profile = replace(profile, context=65536, output_tokens=4096, temperature=0, seed=1729,
                      reasoning_effort='none')
    binary = opencode_path(existing.opencode)
    if not binary or not runner_status(root, old['image'])['image_id']:
        raise ValueError('pinned offline verification image or installed OpenCode unavailable')
    reference = replace(recipe(old, 'reference'), oracle='cases.json')
    replay = evaluate(reference, root / 'target', root / 'home', root / 'development',
                      old['image'], 60, None, public=True)
    write(root / 'reference-public.json', replay)
    if replay['passed_cases'] != 18:
        raise ValueError('reference no longer matches the frozen public observations')
    manifest = {key: old[key] for key in ('image', 'target', 'build_candidate', 'candidate', 'reference')}
    manifest.update(status='PREPARED_NOT_AUTHORIZED', arm=ARM, objective=OBJECTIVE,
                    profile=asdict(profile), generation=request_options(profile), ssh=existing.ssh,
                    opencode={'path': binary, 'sha256': file_hash(Path(binary))},
                    execution_state=str(existing.execution_state or existing.state),
                    limits=LIMITS, worker=RESOURCES, capture=CAPTURE,
                    final_cases=FINAL_CASES, deliverables=[OUTPUT],
                    baseline={'compiled': False, 'public_passed': 0, 'total': 18},
                    development=inventory(root / 'development'), bindings=bindings(root))
    task(root, manifest).validate()
    manifest['endpoint'] = endpoint(config(root, manifest))
    write(root / 'manifest.json', manifest)
    (root / 'manifest.sha256').write_text(digest(manifest) + '\n', encoding='ascii')
    return manifest


def validate(root: Path) -> dict:
    manifest = read(root / 'manifest.json')
    profile = Profile(**manifest['profile'])
    profile.validate()
    if (digest(manifest) != (root / 'manifest.sha256').read_text().strip()
            or manifest['bindings'] != bindings(root) or manifest['arm'] != ARM
            or manifest['limits'] != LIMITS or manifest['worker'] != RESOURCES
            or manifest['capture'] != CAPTURE
            or manifest['objective'] != OBJECTIVE or manifest['final_cases'] != FINAL_CASES
            or manifest['deliverables'] != [OUTPUT] or manifest['generation'] != request_options(profile)
            or profile.managed or profile.location != 'a100' or profile.id != ARM
            or profile.engine != 'llamacpp' or profile.harness != 'opencode'
            or (profile.context, profile.output_tokens, profile.temperature, profile.seed,
                profile.reasoning_effort) != (65536, 4096, 0, 1729, 'none')
            or inventory(root / 'target') != manifest['target']
            or inventory(root / 'development') != manifest['development']
            or set(inventory(root / 'input')) != {'binary.json', 'ghidra.json', 'examples.json', 'native_feedback.py'}
            or file_hash(Path(manifest['opencode']['path'])) != manifest['opencode']['sha256']):
        raise ValueError('reviewed ledger trial inputs, profile or implementation changed')
    return manifest


def work(root: Path, manifest: dict) -> None:
    ctl = Controller(config(root, manifest))
    result = ctl.run_submitted(ctl.submit_task(task(root, manifest), profile_id=ARM))
    write(root / 'engineering-result.json', result)
    attempt, = Path(result['artifacts']).glob('attempt-*')
    receipt = read(attempt / 'execution-receipt.json')
    if receipt['status'] != 'completed' or not receipt['cleanup_passed']:
        raise RuntimeError('worker did not complete with owned cleanup')
    checkpoint = read(attempt / 'checkpoint.json')
    calls = [json.loads(line) for line in (attempt / 'mcp.jsonl').read_text().splitlines() if line.strip()]
    if (result['status'] != 'verified' or not checkpoint['selection']['accepted']
            or checkpoint['public']['passed_cases'] != 18
            or not any(call['tool'] == 'edit' and call.get('applied') for call in calls)
            or not any(call['tool'] == 'check' and call['index'] == 0 and call['passed'] for call in calls)):
        raise RuntimeError('mandatory public closure incomplete')
    # Outer phase cleanup must pass before the runner exports or marks a freeze.
    write(root / 'qualified.json', {'workspace': str(attempt / 'workspace'),
                                    'source': checkpoint['inventory'][OUTPUT]})


def run(root: Path, manifest: dict, approval: Path) -> None:
    authorize(manifest, approval)
    if runner_status(root, manifest['image'])['image_id'] != manifest['image']:
        raise ValueError('reviewed offline image unavailable')
    if shutil.disk_usage(root).free < sum(CAPTURE.values()):
        raise ValueError('insufficient disk for evidence capture and headroom')
    with file_lock(root / 'run.lock'):
        marker = root / 'execution-started.json'
        if marker.exists() or (root / 'private').exists():
            raise ValueError('trial already consumed or premature private material exists')
        write(marker, {'approval': digest(manifest), 'started': time()})
        write(root / 'operator-approval.json', read(approval))
        create(root / 'state', digest(manifest), ARM, LIMITS, reviewed_caps=LIMITS,
               quotas={'sessions': 1, 'planner_requests': 0})
    phase(root, 'warm')
    phase(root, 'work')
    qualified = read(root / 'qualified.json')
    frozen = snapshot(Path(qualified['workspace']), root / 'frozen', (OUTPUT,))
    if frozen != {OUTPUT: qualified['source']}:
        raise ValueError('qualified candidate bytes changed before freeze')
    write(root / 'frozen.json', frozen)
    write(root / 'engineering-closed.json', {'frozen_at': time(), 'hash': digest(frozen)})


def phase(root: Path, name: str) -> None:
    result = run_phase(root / 'state', name,
                       [sys.executable, str(Path(__file__).resolve()), '_' + name, str(root)], REPO)
    write(root / (name + '-process.json'), result)
    if result['code'] != 0 or result['timed_out'] or not result['cleanup']['passed']:
        write(root / 'failed-phase.json', {'phase': name, 'consumed': True})
        raise RuntimeError(f'{name} did not close under the reviewed protocol')


def authorize(manifest: dict, approval: Path) -> None:
    if read(approval) != {'approval_digest': digest(manifest), 'authorize': [ARM], 'operator_approved': True}:
        raise ValueError('exact separate approval required')


def final_inputs(root: Path) -> Path:
    ledger = read(root / 'state' / FILE)
    closed = read(root / 'engineering-closed.json')
    if (ledger['quarantined'] or ledger['phases']['work']['status'] != 'FINISHED'
            or closed['hash'] != digest(inventory(root / 'frozen'))
            or inventory(root / 'frozen') != read(root / 'frozen.json')):
        raise ValueError('only cleanly frozen bytes may be graded')
    cases = root / 'private/cases.json'
    rows = read_inputs(cases, FINAL_CASES)
    if (len(rows) != FINAL_CASES or cases.stat().st_mtime <= closed['frozen_at']
            or set(read(root / 'exclusions.json')['stimulus_sha256'])
            & {digest(list(case.stimulus)) for case in rows}):
        raise ValueError('independent input suite must be fresh and disjoint')
    return cases


def final_grade(root: Path, manifest: dict) -> None:
    cases = final_inputs(root)
    write(root / 'run.json', manifest)
    result = grade(Controller(config(root, manifest)), root, cases, [], 4)
    write(root / 'grade-result.json', result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'validate', 'run', 'grade', '_warm', '_work', '_grade'))
    parser.add_argument('root', type=Path)
    for option in ('source', 'public', 'static', 'config', 'approval'):
        parser.add_argument('--' + option, type=Path)
    parser.add_argument('--exclude', type=Path, action='append', default=[])
    args = parser.parse_args()
    root = args.root.resolve()
    action = args.action
    if action == 'prepare':
        manifest = prepare(root, args.source, args.public, args.static, args.config, args.exclude)
    else:
        manifest = validate(root)
        if action == 'run':
            run(root, manifest, args.approval)
        elif action == 'grade':
            authorize(manifest, args.approval)
            final_inputs(root)
            phase(root, 'grade')
        elif action.startswith('_'):
            lease = current(root / 'state')
            if not lease or lease['phase'] != action[1:]:
                raise ValueError('matching active measured phase required')
            if action == '_warm':
                receipt = endpoint(config(root, manifest))
                if receipt != manifest['endpoint']:
                    raise ValueError('A100 endpoint drifted')
                write(root / 'warm-readiness.json', receipt)
            else:
                {'_work': work, '_grade': final_grade}[action](root, manifest)
    print(json.dumps({'arm': ARM, 'approval_digest': digest(manifest), 'action': action}))


if __name__ == '__main__':
    main()
