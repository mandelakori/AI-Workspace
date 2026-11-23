"""Prepare and, only with a matching separate approval, run one cross-plane smoke arm."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import asdict, replace
from pathlib import Path

from ledger_trial import REPO, config, digest, endpoint, file_hash, implementation, read

from aiwork.controller import Controller
from aiwork.evidence_capture import DEFAULT_CAPTURE_BYTES, DEFAULT_HEADROOM_BYTES
from aiwork.harness import opencode_path, opencode_request_options
from aiwork.local_runtime import admit_context, memory_snapshot
from aiwork.lock import file_lock
from aiwork.oracle import evaluate, load_cases
from aiwork.process import executable
from aiwork.schema import Check, Config, Profile, Task
from aiwork.trial_budget import create, current, run_phase, write
from aiwork.verify import invoke, runner_status
from aiwork.workspace import inventory, snapshot


ARMS = ('local', 'a100')
LIMITS = {'warm': 20, 'work': 265, 'grade': 45}
RESOURCES = dict(timeout=240, attempts=1, min_context=8192, context_input_tokens=7440,
                 tool_operations=20, edit_reserve=4, public_test_reserve=4,
                 model_requests=12, compaction_limit=1)
INPUTS = ('units.py', 'test_units.py')
OUTPUT = ('units.py',)
PUBLIC = Check(('{python}', '-m', 'unittest', '-v', 'test_units'), 15)
SEALED = Check(('{python}', '-c', 'from units import fahrenheit_to_celsius; '
                'print(format(fahrenheit_to_celsius(float(input())), ".6f"))'), 35, oracle='cases.json')
OBJECTIVE = ('Fix the Fahrenheit to Celsius conversion in units.py using the standard formula. '
             'Inspect units.py and test_units.py, preserve the existing interface and execute public check 0. '
             'Only units.py may change.')


def task(root: Path, profile: Profile) -> Task:
    return Task(OBJECTIVE, root / 'input', 'agent', 'cross-plane-routing-smoke', INPUTS, OUTPUT,
                (PUBLIC,), location=profile.location, profile=profile.id, mode='engineering',
                write_roots=OUTPUT, commands=(PUBLIC,), **RESOURCES)


def local_identity(profile: Profile) -> dict:
    path = Path(profile.local_calibration)
    if file_hash(path) != profile.calibration_sha256:
        raise ValueError('reviewed local calibration changed')
    model = read(path)['model_copy']
    store = Path(model['destination']).resolve(strict=True)
    if store != path.parent / 'model-store' or file_hash(store / 'manifests' / model['manifest']) != model['manifest_sha256']:
        raise ValueError('reviewed isolated model manifest changed')
    for descriptor, expected in model['blobs'].items():
        with (store / 'blobs' / descriptor.replace(':', '-')).open('rb') as blob:
            actual = {'sha256': hashlib.file_digest(blob, 'sha256').hexdigest(), 'bytes': blob.tell()}
        if actual != expected:
            raise ValueError('reviewed isolated model blob changed')
    binary = executable('ollama')
    if not binary:
        raise ValueError('installed Ollama executable unavailable')
    return {'ollama': {'path': binary, 'sha256': file_hash(Path(binary))},
            'manifest_sha256': model['manifest_sha256'], 'blobs': model['blobs']}


def readiness(root: Path, manifest: dict) -> dict:
    if manifest['arm'] == 'a100':
        result = endpoint(config(root, manifest))
        if 'identity' in manifest and result != manifest['identity']:
            raise ValueError('reviewed A100 identity or slot changed')
        return result
    profile = Profile(**manifest['profile'])
    admission = admit_context(read(Path(profile.local_calibration)), input_tokens=RESOURCES['context_input_tokens'],
        output_tokens=profile.output_tokens, reserve_tokens=profile.context_reserve_tokens, maximum=profile.context,
        memory=memory_snapshot(), deadline_seconds=RESOURCES['timeout'] - 20,
        gpu_headroom_mib=profile.gpu_headroom_mib, ram_headroom_mib=profile.ram_headroom_mib)
    if admission['selected'] != profile.context:
        raise ValueError('local measured memory/context/deadline admission rejected')
    return admission


def bindings(root: Path) -> dict:
    return {'input': inventory(root / 'input'), 'oracle': inventory(root / 'private'),
            'controller': implementation(), 'runner': file_hash(Path(__file__)),
            'a100_probe': file_hash(Path(__file__).with_name('ledger_trial.py'))}


def prepare(root: Path, oracle: Path) -> None:
    if len(load_cases(oracle / 'cases.json')) != 6 or set(inventory(oracle)) != {'cases.json'}:
        raise ValueError('require exactly six reviewed cases and no other private files')
    local = Config.load(REPO / 'examples/adaptive-local.toml')
    remote = Config.load(REPO / 'examples/milestone-e-final/controller.toml')
    profiles = tuple(replace(c.profiles[0], context=16384, output_tokens=1536, temperature=0, seed=1729,
                     quantization=q, reasoning_effort='none', enable_thinking=False if arm == 'a100' else None)
                     for c, q, arm in zip((local, remote), ('Q4_K_M', 'Q6_K'), ARMS))
    binary = opencode_path(local.opencode)
    image = runner_status(REPO, local.verification_image)['image_id']
    if not binary or not image or local.execution_state != remote.execution_state:
        raise ValueError('require installed offline referee, OpenCode and common lane locks')
    root.mkdir()
    for arm, profile in zip(ARMS, profiles):
        folder = root / arm
        folder.mkdir()
        snapshot(REPO / 'examples/project', folder / 'input', INPUTS)
        snapshot(oracle, folder / 'private', ('cases.json',))
        task(folder, profile).validate()
        manifest = {'arm': arm, 'status': 'PREPARED_NOT_AUTHORIZED', 'objective': OBJECTIVE,
                    'profile': asdict(profile), 'generation': opencode_request_options(profile), 'image': image,
                    'opencode': {'path': binary, 'sha256': file_hash(Path(binary))},
                    'ssh': remote.ssh if arm == 'a100' else {}, 'execution_state': str(local.execution_state),
                    'limits': LIMITS, 'worker': RESOURCES, 'write_roots': OUTPUT,
                    'checks': {'public': asdict(PUBLIC), 'private': asdict(SEALED)},
                    'capture': {'limit_bytes': DEFAULT_CAPTURE_BYTES, 'headroom_bytes': DEFAULT_HEADROOM_BYTES},
                    'bindings': bindings(folder)}
        receipt = readiness(folder, manifest)
        manifest['identity'] = receipt if arm == 'a100' else local_identity(profile)
        write(folder / 'readiness.json', receipt)
        write(folder / 'manifest.json', manifest)
        (folder / 'manifest.sha256').write_text(digest(manifest) + '\n', encoding='ascii')


def validate(root: Path) -> dict:
    manifest = read(root / 'manifest.json')
    if (digest(manifest) != (root / 'manifest.sha256').read_text().strip()
            or manifest['arm'] != root.name or root.name not in ARMS
            or manifest['bindings'] != bindings(root)
            or file_hash(Path(manifest['opencode']['path'])) != manifest['opencode']['sha256']):
        raise ValueError('reviewed arm inputs, harness or implementation changed')
    Profile(**manifest['profile']).validate()
    return manifest


def authorize(manifest: dict, approval: Path) -> None:
    if read(approval) != {'approval_digest': digest(manifest), 'authorize': [manifest['arm']], 'operator_approved': True}:
        raise ValueError('exact separate approval required')


def work(root: Path, manifest: dict) -> None:
    cfg = config(root, manifest)
    controller = Controller(cfg)
    result = controller.run_submitted(controller.submit_task(task(root, cfg.profiles[0])))
    write(root / 'engineering-result.json', result)
    attempt, = Path(result['artifacts']).glob('attempt-*')
    receipt = read(attempt / 'execution-receipt.json')
    calls = [json.loads(line) for line in (attempt / 'mcp.jsonl').read_text(encoding='utf-8').splitlines()]
    if (result['status'] != 'verified' or receipt['status'] != 'completed' or not receipt['cleanup_passed']
            or not any(call['tool'] == 'edit' and call.get('applied') for call in calls)
            or not any(call['tool'] == 'check' and call['index'] == 0 and call['passed'] for call in calls)):
        raise RuntimeError('mandatory scope, edit, public and worker closure checks did not pass')
    write(root / 'qualified.json', {'path': str(attempt / 'workspace'), 'inventory': read(attempt / 'output-inventory.json')})


def grade(root: Path, manifest: dict) -> None:
    if inventory(root / 'frozen') != read(root / 'frozen.json'):
        raise ValueError('frozen candidate changed before grading')
    result = evaluate(SEALED, root / 'frozen', root / 'grade-home', root / 'private', manifest['image'], 35, None)
    write(root / 'grade.json', result)
    if len(result['cases']) != result['total']:
        raise RuntimeError('independent grading did not evaluate all cases')


def run(root: Path, manifest: dict, approval: Path) -> None:
    authorize(manifest, approval)
    if (runner_status(root, manifest['image']).get('image_id') != manifest['image']
            or shutil.disk_usage(root).free < sum(manifest['capture'].values())):
        raise ValueError('reviewed offline runner or evidence disk allowance unavailable')
    if root.name == 'local' and local_identity(Profile(**manifest['profile'])) != manifest['identity']:
        raise ValueError('reviewed local model or Ollama changed')
    with file_lock(root / 'run.lock'):
        create(root / 'state', digest(manifest), root.name, LIMITS, reviewed_caps=LIMITS,
               quotas={'sessions': 1, 'planner_requests': 0})
        write(root / 'operator-approval.json', read(approval))
        for name in ('warm', 'work', 'grade'):
            result = run_phase(root / 'state', name, [sys.executable, __file__, '_' + name, str(root)], REPO)
            write(root / f'{name}-process.json', result)
            if result['code'] or result['timed_out'] or not result['cleanup']['passed']:
                raise RuntimeError(f'{name} did not close under the reviewed protocol')
            if name == 'work':
                qualified = read(root / 'qualified.json')
                frozen = snapshot(Path(qualified['path']), root / 'frozen', INPUTS)
                if frozen != qualified['inventory']:
                    raise ValueError('candidate bytes changed before freeze')
                write(root / 'frozen.json', frozen)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'validate', 'run', '_warm', '_work', '_grade'))
    parser.add_argument('root', type=Path)
    parser.add_argument('asset', type=Path, nargs='?')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action in ('prepare', 'run') and not args.asset:
        parser.error('prepare requires an oracle directory; run requires a separate approval file')
    if args.action == 'prepare':
        prepare(root, args.asset.resolve())
        return
    manifest = validate(root)
    if args.action == 'validate':
        print(digest(manifest))
    elif args.action == 'run':
        run(root, manifest, args.asset)
    else:
        phase = current(root / 'state')
        if not phase or phase['phase'] != args.action[1:]:
            raise ValueError('an authorized active phase is required')
        if args.action == '_warm':
            write(root / 'warm-readiness.json', readiness(root, manifest))
        else:
            (work if args.action == '_work' else grade)(root, manifest)


if __name__ == '__main__':
    main()
