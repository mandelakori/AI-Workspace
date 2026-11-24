"""Review and, with a separate grant, run one calibrated local load-only check."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import monotonic

from cross_plane_trial import REPO, RESOURCES, digest, file_hash, implementation, local_identity, read, readiness, task

from aiwork.local_runtime import calibrated_runtime
from aiwork.lock import file_lock
from aiwork.router import Plane
from aiwork.schema import Profile
from aiwork.trial_budget import create, current, remaining, run_phase, write


ARM = 'local-initialization'
LIMITS = {'warm': 20, 'work': 240, 'grade': 1}
BASE = REPO / '.aiwork/routing-validation'
SOURCE = BASE / 'cross-plane-final/local'
ROOT = BASE / 'local-initialization-check'
ORIGINAL = '104261027ac6cb375643266f1f58ba0fefc3c832a8a166b086a36b4798296568'


def reviewed_inputs() -> dict:
    original = read(SOURCE / 'manifest.json')
    if digest(original) != ORIGINAL:
        raise ValueError('original reviewed profile changed')
    return {'status': 'PREPARED_NOT_AUTHORIZED', 'arm': ARM, 'original_profile_digest': ORIGINAL,
            'profile': original['profile'], 'identity': original['identity'],
            'execution_state': original['execution_state'], 'phase_limits': LIMITS,
            'workload_envelope': RESOURCES, 'model_load_requests': 1, 'generation_requests': 0,
            'controller': implementation(), 'runner': file_hash(Path(__file__)),
            'review_helpers': {name:file_hash(Path(__file__).with_name(name))
                               for name in ('cross_plane_trial.py','ledger_trial.py')}}


def validate(manifest: dict) -> Profile:
    if manifest != reviewed_inputs():
        raise ValueError('reviewed model, startup policy or implementation changed')
    profile = Profile(**manifest['profile'])
    profile.validate()
    return profile


def run(manifest: dict, manifest_path: Path, approval_path: Path) -> None:
    approval = read(approval_path)
    if approval != {'approval_digest': digest(manifest), 'authorize': [ARM], 'operator_approved': True}:
        raise ValueError('exact separate load-only approval required')
    ROOT.mkdir(exist_ok=False)  # One fixed state directory for this grant.
    with file_lock(ROOT / 'run.lock'):
        write(ROOT / 'operator-approval.json', approval)
        create(ROOT / 'state', digest(manifest), ARM, LIMITS, reviewed_caps=LIMITS,
               quotas={'sessions': 0, 'planner_requests': 0})
        for phase in ('warm', 'work'):
            result = run_phase(ROOT / 'state', phase,
                               [sys.executable, str(Path(__file__).resolve()), '_' + phase, str(manifest_path)],
                               REPO, containers=False)
            write(ROOT / f'{phase}-process.json', result)
            if result['code'] or result['timed_out'] or not result['cleanup']['passed']:
                raise RuntimeError(f'{phase} failed under the load-only protocol')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('validate', 'run', '_warm', '_work'))
    parser.add_argument('manifest', type=Path)
    parser.add_argument('approval', type=Path, nargs='?')
    args = parser.parse_args()
    path = args.manifest.resolve(strict=True)
    manifest = read(path)
    profile = validate(manifest)
    if args.action == 'validate':
        print(digest(manifest))
    elif args.action == 'run':
        if not args.approval:
            parser.error('run requires a separate load-only approval file')
        run(manifest, path, args.approval)
    else:
        lease = current(ROOT / 'state')
        if not lease or lease['phase'] != args.action[1:]:
            raise ValueError('load-only phase lease required')
        if args.action == '_warm':
            if local_identity(profile) != manifest['identity']:
                raise ValueError('reviewed local model or Ollama changed')
            write(ROOT / 'preflight.json', readiness(SOURCE, manifest | {'arm':'local'}))
        else:
            deadline = monotonic() + remaining(lease)
            plane = Plane('local', 1, ROOT, Path(manifest['execution_state']))
            with plane.reserve(profile, min(5, max(0, deadline-monotonic()))):
                with calibrated_runtime(profile, task(SOURCE, profile), ROOT, deadline):
                    pass  # The runtime has recorded residency. Exit without generating tokens.


if __name__ == '__main__':
    main()
