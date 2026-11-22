# Original Milestone E: one fresh A100 engineering trial

This is a preparation and approval entrypoint, not authorization. It uses the
existing deterministic controller, OpenCode, scoped editor, context epochs and
trial watchdogs. It neither replaces a harness nor introduces a new milestone.
No Codex or proprietary API is required to operate it.

ItsDangerous is pinned at `672971d66a2ef9f85151e53283113f33d642dabd` (BSD-3-Clause).
`FEATURE.md` freezes a duration-valued expiry feature. `public-cases.json` contains
12 public behaviors. The complete original upstream test suite, all API overload
annotations, an authored test file and documentation are also required. The worker
receives no implementation solution. Private cases do not exist during preparation.

Read the current operator review in `docs/A100-ENGINEERING-READINESS.md` for the
exact prepared digest. Do not edit a prepared bundle, reuse consumed approvals,
or execute the separate Pi/OpenCode comparison. If anything pinned changes, prepare
a new bundle and obtain approval for its new digest.

From the repository in PowerShell:

```powershell
$py = '.\.venv\Scripts\python.exe'
# The existing prepared checkout/image need no download or rebuild.
& $py examples/milestone-e-a100/trial.py validate .aiwork/a100-readiness/trial-final
# Only following separate explicit approval of this digest:
& $py examples/milestone-e-a100/trial.py run .aiwork/a100-readiness/trial-final --approval .aiwork/a100-readiness/trial-final/operator-approval.json
# Only after engineering-closed.json and frozen.json exist without quarantine:
# An independent evaluator authors private/cases.json: 24 distinct new payloads.
& $py examples/milestone-e-a100/trial.py grade .aiwork/a100-readiness/trial-final --approval .aiwork/a100-readiness/trial-final/operator-approval.json
```

`operator-approval.example.json` deliberately records `operator_approved:false`.
An approval must match the digest and authorize exactly `["a100-existing"]`.
The script rejects false, absent or mismatched approval before dispatch. One
attempt is consumed before launch; no restart, retry, laptop fallback, service
change, model download or cloud lifecycle action is permitted.

For a new machine/bundle (review required, no inference):

```powershell
git clone https://github.com/pallets/itsdangerous.git .aiwork/itsdangerous-new
git -C .aiwork/itsdangerous-new checkout 672971d66a2ef9f85151e53283113f33d642dabd
# Existing offline base image must already be installed. Download test wheels only
# if absent, recording their hashes; no inference model is downloaded.
New-Item -ItemType Directory .aiwork/itsdangerous-image/wheels -Force
& $py -m pip download --only-binary=:all: --dest .aiwork/itsdangerous-image/wheels -r examples/milestone-e-a100/requirements.txt
Copy-Item examples/milestone-e-a100/Dockerfile .aiwork/itsdangerous-image/Dockerfile
docker build --network=none --pull=false -t aiwork-milestone-e-itsdangerous:20261122 .aiwork/itsdangerous-image
# Record fresh read-only endpoint health/models/props/slots; zero inference:
& $py examples/milestone-e-a100/trial.py inspect .aiwork/a100-new-readiness --config examples/milestone-e-a100/controller.toml
& $py examples/milestone-e-a100/trial.py prepare .aiwork/a100-new-trial --source .aiwork/itsdangerous-new --config examples/milestone-e-a100/controller.toml --endpoint-evidence .aiwork/a100-new-readiness/endpoint.json --image aiwork-milestone-e-itsdangerous:20261122
```

The pinned final image ID, wheels, source inventories and verification receipts
are recorded by the prepared trial/evidence. Never substitute a new image under
an existing approval. The base image is the installed Python/pytest environment;
ItsDangerous itself is always imported from the isolated `/work/src` snapshot.

Sealed case schema: `{"id":"unique", "api":"signer", "age":..., "delta":{...},
"expected":{...}}`. Payload fields use the frozen public runner schema; expected
is the independently specified normalized observation (result and metadata), not
code or a mounted oracle. Only payloads are sent into a read-only, network-disabled
candidate container. Expected values stay outside it. Case IDs/payloads must be
distinct and new relative to the public corpus, and authored after final freeze.
Sealed results cannot prompt repairs or select a checkpoint.
