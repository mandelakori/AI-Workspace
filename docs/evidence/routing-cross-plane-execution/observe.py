"""Read-only observation of a frozen arm; does not send requests or change its runner."""
from pathlib import Path
from time import time, sleep
import json
import subprocess
import sys

arm = sys.argv[1]
base = Path('.aiwork/routing-validation').resolve()
arm_root = base / 'cross-plane-final' / arm
notes = base / 'cross-plane-execution'
assert arm in ('local', 'a100')
assert not (arm_root / 'state').exists()
if arm == 'a100':
    local = base / 'cross-plane-final/local'
    phase_state = json.loads((local / 'state/trial-budget.json').read_bytes())
    assert not phase_state.get('quarantined')
    assert all(e['status'] == 'FINISHED' and e['cleanup']['passed'] for e in phase_state['phases'].values())
    assert json.loads((local / 'grade.json').read_bytes())['passed']
    assert json.loads((local / 'work-process.json').read_bytes())['code'] == 0

events = {}
def stamp(name, **detail):
    if name not in events:
        events[name] = dict(utc_seconds=time(), **detail)
attempt = None
def sample():
    global attempt
    for phase in ('warm', 'work', 'grade'):
        if (arm_root / (phase + '-process.json')).is_file():
            stamp(phase + '_cleanup_receipt')
    if attempt is None:
        attempt = next((arm_root / 'state/runs').glob('*/attempt-001'), None)
    if not attempt:
        return
    for file, name in [('local-inference/ownership.json','ollama_ownership_receipt'),
                       ('local-context-admission.json','calibrated_admission'),
                       ('admission.json','admission_receipt'),('provider-forwarded-001.json','first_forwarded_request'),
                       ('agent-process.json','harness_process_receipt'),('check-00.json','independent_public_receipt')]:
        if (attempt / file).is_file():
            stamp(name)
    try:
        if 'ollama_listener_ready' not in events:
            ownership = attempt / 'local-inference/ownership.json'
            if ownership.is_file() and json.loads(ownership.read_bytes())['ready']:
                stamp('ollama_listener_ready')
        if 'first_response_bytes' not in events or 'first_response_delta' not in events:
            file = attempt / 'provider-response-001.sse'
            if file.is_file():
                with file.open('rb') as stream:
                    prefix = stream.read(65536)
                if prefix:
                    stamp('first_response_bytes')
                    for line in prefix.splitlines():
                        if not line.startswith(b'data: {'):
                            continue
                        value = json.loads(line[6:])
                        for choice in value.get('choices', []):
                            delta = choice.get('delta', {})
                            if any(delta.get(key) for key in ('content', 'tool_calls','reasoning_content','reasoning')):
                                stamp('first_response_delta')
        if 'first_accepted_edit' not in events or 'first_public_check' not in events:
            file = attempt / 'mcp.jsonl'
            if file.is_file():
                for line in file.read_text(encoding='utf-8').splitlines():
                    record = json.loads(line)
                    if record.get('tool') == 'edit' and record.get('applied'):
                        stamp('first_accepted_edit', operation=record['call'])
                    if record.get('tool') == 'check':
                        stamp('first_public_check', operation=record['call'], passed=record.get('passed'), elapsed=record.get('elapsed'))
    except (OSError, ValueError):
        pass  # The controller may be appending a line or replacing an atomic receipt.

stamp('command_start')
with (notes / (arm + '-console.log')).open('xb') as log:
    command = [sys.executable, 'examples/native/cross_plane_trial.py', 'run', str(arm_root),
               str(notes / ('approval-' + arm + '.json'))]
    with subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT) as process:
        while process.poll() is None:
            sample()
            sleep(.10)
        sample()
        stamp('command_end')
        (notes / (arm + '-timing.json')).write_text(json.dumps(
            {'arm':arm,'complete':True,'runner_exit':process.returncode,'poll_seconds':.1,'events':events},indent=2)+'\n',
            encoding='utf-8')
        print(f'{arm}: frozen runner exit {process.returncode}', flush=True)
        raise SystemExit(process.returncode)
