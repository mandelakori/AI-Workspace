# Reviewable Click feature

[click-iso-datetime.patch](click-iso-datetime.patch) applies to Pallets Click 8.3.2,
commit `052c006033729bbb422cbdad0c4fee988ecb5aa5`. Five files change. The original
BSD license is included as [CLICK-LICENSE.txt](CLICK-LICENSE.txt).

The feature implementation and tests are model-authored, with operator-guided
recovery and operator-assisted documentation cleanup. See the
[engineering report](../../docs/PHASE6-REPORT.md), [candidate hashes](candidate.json),
[model evidence](evidence-summary.json) and [sealed summary](sealed-summary.json).
Private case inputs and expected results are excluded. This is a reviewable local
patch, not an upstream pull request or release.

```powershell
# From AI-Workspace. Choose a new checkout; the preserved baseline stays unchanged.
$patch = (Resolve-Path 'deliverables/phase6/click-iso-datetime.patch').Path
git clone --config core.autocrlf=false --branch 8.3.2 --depth 1 https://github.com/pallets/click.git .aiwork/click-review
git -C .aiwork/click-review rev-parse HEAD # verify the commit above
git -C .aiwork/click-review apply --check $patch
git -C .aiwork/click-review apply $patch
$checkout = (Resolve-Path '.aiwork/click-review').Path
$image = 'sha256:885f0aefe0ae650b7115ca729d533b74f092712a0b5b340262090d5ccfc8ffeb'
docker run --rm --pull=never --network=none --read-only --tmpfs /tmp --mount "type=bind,src=$checkout,dst=/work,readonly" -w /work $image python -m pytest -q -p no:cacheprovider tests
```

Expected default repository result: 1,392 passed, 21 skipped, 30,000 stress cases
deselected, 1 xfailed. The baseline was 1,385 passes with identical exclusions.
The image already exists locally; [staging instructions](../../examples/phase6/README.md)
describe a reproducible offline build from hash-pinned wheels.
The patch uses portable LF line endings. The manifest records both raw frozen
hashes and delivery hashes; only line endings differ, with identical Python ASTs.
Its cleanly applied result was independently retested.

Public verification of the immutable preserved result requires no inference:

```powershell
$workspace = (Resolve-Path '.aiwork/phase6/final-frozen').Path
docker run --rm --pull=never --network=none --read-only --tmpfs /tmp --mount "type=bind,src=$workspace,dst=/work,readonly" -w /work $image python _aiwork_verify.py public
docker run --rm --pull=never --network=none --read-only --tmpfs /tmp --mount "type=bind,src=$workspace,dst=/work,readonly" -w /work $image python _aiwork_verify_install.py
docker run --rm --pull=never --network=none --read-only --tmpfs /tmp --mount "type=bind,src=$workspace,dst=/work,readonly" -w /work $image python _aiwork_verify_docs.py
$env:AIWORK_TEST_DOCKER_IMAGE='aiwork-engineering:phase3'
$env:AIWORK_TEST_OPENCODE_BOUNDARY='1'
.venv/Scripts/python.exe -m unittest discover -s tests -q
```

Public acceptance is 31/31; fresh sealed acceptance is 32/32. The original 31/32
sealed grading receipt is preserved privately; an evaluator-only error-hint
correction is [documented](grader-correction.json). Candidate hashes never changed
after freeze. Style/type checks and the full Sphinx build are untested. No model
repair is authorized by running these verification commands.
