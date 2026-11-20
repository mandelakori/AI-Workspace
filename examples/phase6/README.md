# Click feature experiment

This is an operator-specified additive feature for unmodified Pallets Click 8.3.2,
commit `052c006033729bbb422cbdad0c4fee988ecb5aa5`. It is not an upstream issue or
an accepted upstream API. [FEATURE.md](FEATURE.md) is the frozen contract. All
target implementation and test additions come from the existing local open-weight
worker. Documentation required operator-assisted review cleanup, recorded in
the delivery receipts. Controller-authored files here contain verification
and experiment assembly only; no production implementation corrections.

Run from the AI-Workspace repository in PowerShell. Use its existing configured
Python environment, local model and Docker Desktop. Dependency downloads below
are Python wheels, not models. The build and every candidate test run offline.

```powershell
$root = '.aiwork/phase6-replay' # choose a new directory; evidence is never overwritten
git clone --branch 8.3.2 --depth 1 https://github.com/pallets/click.git "$root/upstream-click"
git -C "$root/upstream-click" rev-parse HEAD # must match the commit above
New-Item -ItemType Directory -Force "$root/image/wheels" | Out-Null
.venv/Scripts/python.exe -m pip download --only-binary=:all: --no-deps --require-hashes -r examples/phase6/requirements-download.lock -d "$root/image/wheels"
Copy-Item examples/phase6/Dockerfile "$root/image/Dockerfile"
docker build --network=none --pull=false -t aiwork-phase6-click:20261120 "$root/image"
.venv/Scripts/python.exe examples/phase6/stage.py $root --config .aiwork/phase4-followup.local.toml
```

Supply a different existing configuration using `--config` if necessary; staging
requires the reviewed `laptop-ollama-8k` profile and pins the local image ID.
The original upstream checkout is read-only to workers. Staging creates the
workspace, original 25 public cases, baseline receipt, ranked task and planning
manifest. It does not send inference requests. Review generated scopes and
commands before dispatching either manifest through the existing CLI.

The preserved experiment under `.aiwork/phase6` includes reviewed plans, bounded
context excerpts, failed traces, warm starts and public repair reviews. The
original planning attempt did not complete the feature. Recovery used the
existing `component_source.propose_source`, offline verifier and ranked selector
through `repair_source.py`; it did not add a new execution engine.

```powershell
# Reproduce a public verification of the preserved selected workspace.
$workspace = (Resolve-Path '.aiwork/phase6/final-frozen').Path
$image = 'sha256:885f0aefe0ae650b7115ca729d533b74f092712a0b5b340262090d5ccfc8ffeb'
docker run --rm --network=none --read-only --tmpfs /tmp --mount "type=bind,src=$workspace,dst=/work,readonly" -w /work $image python _aiwork_verify.py public
docker run --rm --network=none --read-only --tmpfs /tmp --mount "type=bind,src=$workspace,dst=/work,readonly" -w /work $image python _aiwork_verify.py all

# A NEW inference campaign requires reviewing its local profile, scopes and budget.
# This example is deliberately not part of verification or bootstrap.
$warmstart = (Resolve-Path '.aiwork/phase6/refined-recovery/selected').Path
.venv/Scripts/python.exe examples/phase6/repair_source.py .aiwork/phase6-new-repair --start $warmstart --config .aiwork/phase6/thinking.local.toml --components api-method,tests,docs --review-artifacts --documentation-base .aiwork/phase6/upstream-click
```

Each repair experiment permits at most two single-response requests per listed
unit (six total for three units), 2,048 output tokens and 45 seconds per request.
`--attempts 1` narrows that limit. Individual reviewed recovery campaigns are
counted separately; the complete Phase 6 history contains 20 source requests,
eight tool sessions and one planning request, not a six-request overall trial.
One second documentation request had already started when its stop flag arrived.
It copies the incumbent, validates assembly scope, runs all default upstream
tests, compares every proposal on the same frozen public corpus, and rejects
lost public passes. Original whole-class failures and subsequent narrower
method trials remain distinct experiments. Reasoning is selected by the
reviewed profile; it changes request options only. Raw requests and responses,
token receipts, inventories, decisions and predecessors remain in each root.
Failed staging and queue stops sent no inference requests.

`review_public.py` supplies public timezone-object diagnostics.
`authored_checks.py` checks actual execution of the authored CLI test and required
documentation examples. These are public requirements, not sealed feedback.
Every additional public case is frozen before its campaign and all candidates
in that campaign use that same corpus. Never use final sealed failures to repair
the frozen result. Private final inputs are kept outside candidate workspaces
and are not included in the patch or repository.

The final public corpus contains 31 checks. `verify_docs.py` also executes the
documented usage and rejection examples; `verify_install.py` builds and installs
a wheel without network access. `repair_docs_example.py` preserves the final
unsuccessful single-request documentation edit. Its regression was rejected;
the final report labels subsequent documentation review as operator-assisted.
`summarize.py` reconstructs public model/tool counters and evidence hashes.
See [the engineering report](../../docs/PHASE6-REPORT.md) and
[reviewable delivery](../../deliverables/phase6/README.md) for final results.
