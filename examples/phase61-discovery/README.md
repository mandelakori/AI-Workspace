# Controlled source-discovery experiment

Read [operator review](../../docs/DISCOVERY-EXPERIMENT-REVIEW.md) and the frozen
manifest before approving anything. This is **PREPARED_NOT_AUTHORIZED**. Do not
reuse an HTTPX authorization or execute the example grant: its approval is false.

From the AI-Workspace root, inspect without inference:

```powershell
.\.venv\Scripts\python.exe -m aiwork.discovery_benchmark validate .aiwork/phase61-discovery/benchmark
Get-Content .aiwork/phase61-discovery/benchmark/manifest.sha256
Get-Content .aiwork/phase61-discovery/benchmark/manifest.json
```

The current approval digest is
`ee17b4c45b8b82dccc1790a91dec1dead8c2983625121b86d785e743a39443d0`.
Authorize exactly `["A", "B"]`; execution order is frozen **B, A**. Do not change
inputs, context, model settings, tools, resource limits or image after approval.

Only after separate explicit operator approval, create the actual approval file
from the reviewed example with `operator_approved: true`. It must name this exact
digest and both arms; the runner refuses incomplete or different grants.

```powershell
# AUTHORIZATION REQUIRED. Do not run during preparation.
.\.venv\Scripts\python.exe -m aiwork.discovery_benchmark run .aiwork/phase61-discovery/benchmark --approval .aiwork/phase61-discovery/benchmark/operator-approval.json
```

The runner owns the whole pair, enforces order and one-shot phase leases, and
stops on failure/quarantine. Do not invoke `_phase` manually, retry a command or
resume an exhausted state. Inspect `arms/*/state/trial-budget.json`, engineering
results, raw provider traces and frozen inventories. Successful engineering close
produces both `frozen.json` files and `engineering-comparison.json`; model failure
or a baseline fallback is not feature completion.

After both engineering phases close and candidates freeze, independently author
**twelve new** cases at `private/cases.json`. None exist during preparation.
Each object has unique `id`, `expected`, and either `value` plus `env`, or `stream`.
Use only the frozen feature contract. Inputs must be distinct from one another
and the public corpus. Do not feed results to workers. Then, under the same
separately approved protocol:

```powershell
.\.venv\Scripts\python.exe -m aiwork.discovery_benchmark grade .aiwork/phase61-discovery/benchmark --approval .aiwork/phase61-discovery/benchmark/operator-approval.json
```

Retrieve `arms/*/selection.json`, `frozen.json`, `sealed-results.json` and phase
receipts. Missing sealed results remain ungraded, not zero. Report source delivery,
public/whole-upstream correctness, authored tests, milestones, provider exit,
tokens/cache usage and time separately. An unmatched or incomplete comparison
supports no arm-superiority claim.

## Reproduction of preparation

The existing local checkout, wheels and image context are retained beneath
`.aiwork/phase61-discovery`. Source is pinned at
`4fbc6ff07215367ece731006855e732d1405992c`; the public frozen input zip is in
`deliverables/phase61-discovery`. No solution code is included.

If reconstructing the environment, obtain that public Git commit and stage the
exact wheels in `requirements.lock` before going offline. On Windows, explicitly
include all lock rows, including Linux-only pexpect/ptyprocess:

```powershell
.\.venv\Scripts\python.exe -m pip download --no-cache-dir --only-binary=:all: --platform manylinux_2_17_x86_64 --implementation cp --python-version 312 --abi cp312 --require-hashes -r examples/phase61-discovery/requirements.lock --dest .aiwork/phase61-discovery/image/wheels
```

The image context contains `Dockerfile`, `requirements.lock`, `wheels/` and an
unchanged `upstream/` source snapshot. The existing local base tag
`aiwork-phase61-httpx:local` must resolve to
`sha256:d3521c3f00c0489a2c2ddccd1975469ee5658bac4e5a79fafd94a1f4f017ada3`.
Do not rebuild or change that original image. A local derived verifier can be
built with `docker build --network none --pull=false`; benchmark execution uses
the immutable derived image digest. Candidate imports must resolve to `/work/src`,
not the installed baseline package. The one upstream test needing an executable
temporary fixture runs on the disposable bind mount; other tests use noexec
tmpfs. The upstream files and assertions are unchanged.

Recheck inert harness and protocol tests without inference:

```powershell
$env:AIWORK_TEST_OPENCODE_BOUNDARY = '1'
$env:AIWORK_TEST_CATALOG_EVIDENCE = "$PWD/.aiwork/phase61-discovery/diagnostics/catalog-ready.json"
.\.venv\Scripts\python.exe -m unittest tests.test_provider_gate tests.test_edit_harness tests.test_discovery_benchmark -v
```

To prepare a **different fresh bundle**, use the pinned clean Git checkout, a
current inert catalog proof, and a profile-manifest containing the recorded model,
harness and execution-state fields. This reads model metadata and runs offline
baseline checks; it does not generate text. It refuses an existing destination.
Every newly prepared bundle gets a new randomized order/digest and needs approval:

```powershell
.\.venv\Scripts\python.exe -m aiwork.discovery_benchmark prepare .aiwork/phase61-discovery/upstream .aiwork/phase61-discovery/benchmark-NEW --profile-manifest docs/evidence/phase61/discovery-preparation/manifest.json --image aiwork-discovery-dotenv:phase61 --readiness .aiwork/phase61-discovery/diagnostics/catalog-ready.json
```
