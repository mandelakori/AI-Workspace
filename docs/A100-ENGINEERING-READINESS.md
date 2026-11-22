# Original Milestone E — A100 autonomous engineering readiness

**Historical preparation at `de38d35`.** The exact trial was subsequently approved,
executed once and quarantined on a provider/template incompatibility. Read the
[execution result](A100-ENGINEERING-RESULT.md); the approval is consumed and this
trial must not resume. Preparation facts and the frozen review below are retained.

2026-11-22, starting at `8c2a417` on `phase61/autonomous-completion`.
The original Milestones A–E remain authoritative. This is experimental evaluation
inside Milestone E, not a new phase, harness survey or architecture redesign.

## Readiness findings

| Check | Result |
| --- | --- |
| Existing `ssh aisak` | **VERIFIED** reachable with batch mode, strict host-key checking, no credential/configuration changes |
| Hardware | **VERIFIED** NVIDIA A100-SXM4-40GB; 40960 MiB total, 10144 MiB free in the first inventory |
| Inference service | **VERIFIED** remote loopback port 18080, healthy llama.cpp `b12063-2cbca389f` |
| Loaded model | **VERIFIED server-reported** `/models/Qwen3.6-35B-A3B-Abliterated-Heretic-Q6_K/Qwen3.6-35B-A3B-Abliterated-Heretic-Q6_K.gguf`; Q6_K, 34660610688 parameters, 28503163392 model bytes |
| Capacity | **VERIFIED** one idle slot, `n_ctx=131072`, trained context 262144; not an 8K server |
| Existing tunnel helper | **VERIFIED** `127.0.0.1:18881 → aisak:127.0.0.1:18080`; exact model inventory matches, test-owned forward PID 64356 closed after inspection |
| Reproducible inspection entrypoint | **VERIFIED** same read-only checks through an independently created/closed forward; raw endpoint and cleanup receipts preserved |
| Remote engineering trial | **UNTESTED**, PREPARED_NOT_AUTHORIZED; zero inference requests, no worker dispatched |

Identity is confirmed against API metadata/props/slot capacity, not a fresh hash
of the 28.5 GB remote weight file. No remote service/storage/model configuration
was changed, no bootstrap or billable lifecycle API was called, and no inference
warmup, throughput probe, SSH recovery experiment or cache-clearing command ran.
Only newly created forwarding subprocesses were closed; existing sessions and
services were not interrupted. There is no remote availability blocker or need
for cloud/service authorization at this checkpoint.

The old checked-in example/local A100 profile advertised 16K. The new reviewed
example uses a **65536-token harness context** and 4096-token completion ceiling,
below the live 131072-token slot. This changes controller-side task configuration,
not server allocation. Original private configuration is untouched.

`router.py` already supports A100 eligibility and complexity preference; historical
verified rates can precede the compute preference in automatic ranking. This trial
explicitly sets `profile=a100-existing`, `location=a100`, complexity 4 and minimum
context 32768. Tests prove even a laptop with better prior scores cannot replace
that route. No cost-based optimization, local fallback or router redesign is needed.
The A100 scheduler serializes the existing inference lane; compilation and
verification remain in the existing local offline Docker pipeline.

## Fresh task and frozen baseline

Repository: [Pallets ItsDangerous](https://github.com/pallets/itsdangerous/tree/672971d66a2ef9f85151e53283113f33d642dabd),
BSD-3-Clause, pinned at `672971d66a2ef9f85151e53283113f33d642dabd`.
This repository has not been used as a prior AI-Workspace engineering target. That
does not assert it was absent from the model's training data. It is neither Click,
HTTPX, python-dotenv nor a generated benchmark utility.

The operator-defined feature adds duration-valued `max_age` support to the existing
timestamp signer and timed serializer APIs. Applications can use `timedelta`
expiry settings without changing token format, cryptography, integer/None behavior,
boundary rules, signature errors, metadata, key rotation or unsafe-load semantics.
This is a new requested feature, not a claim of an upstream-reported security bug.
The [worker specification](../examples/milestone-e-a100/FEATURE.md) contains no
source correction. Workers inspect source through the normal scoped tools.

Frozen permissions allow changes only to:

- `src/itsdangerous/timed.py`
- `docs/timed.rst`
- `tests/test_itsdangerous/test_timedelta_max_age.py`

Baseline: **3/12 public behaviors**, production syntax passes, **297/297 upstream
tests pass, no skips**. Duration annotations and the new authored tests are absent,
as expected. These expected baseline failures are preserved, not repaired by the
operator. The source snapshot, 12 public inputs, complete upstream tests, command
recipes, image and all source/editor permissions are hashed before authorization.
The fresh 24-case sealed suite does **not exist yet**.

The verifier extends the installed Python/pytest image with three pinned test
wheels (freezegun, python-dateutil, six), built with network disabled. Final image:
`sha256:00d3d7e3d1e32064b5bf313cc788fb91945c0c5fa000856513f490f2c8087645`.
Baseline imports come from the copied `/work/src`, not an installed ItsDangerous.
No production implementation was written or supplied by the operator.

## Exact proposed authorization — not executed

Bundle: `.aiwork/a100-readiness/trial-final`

Approval digest:
`150b82b49ebf8235fb0482d70bbcb75d3e3e1556334dd44406f5af3d69fab4af`

Authorize exactly `["a100-existing"]`. The [manifest](evidence/milestone-e-a100/trial-final/manifest.json)
and deliberately false approval example are preserved for review.

| Resource / boundary | Frozen protocol |
| --- | --- |
| Harness / model | Existing OpenCode binary, SHA pinned; existing A100 Qwen3.6 35B-A3B derivative Q6_K; no provider/model fallback |
| Context / output | 65536 / 4096 tokens; temperature 0, seed 1729, reasoning disabled, `chat_template_kwargs.enable_thinking=false` |
| Worker | One implementation session, one 720-second attempt, zero planner requests, no automatic second attempt or mid-run implementation guidance |
| Phase reservations | 20 seconds read-only readiness, 900 seconds engineering/public selection, 120 seconds independent grading; 1040 seconds total reserved |
| Accounting | Startup, SSH, inference, inspection, edits and tests consume the attempt; controller retains its existing 20-second final-verification reservation inside it. The outer 900-second phase also covers final selection/freezing. Existing bounded cancellation/container cleanup is additional safety work, not usable inference time |
| Operations | 96 total MCP operations, with eight reserved for editing and eight for public testing; up to 64 model requests including at most four compactions |
| Tools | Only source focus, exact/hash-validated edit, approved check index and diff; native shell/mutation disabled |
| Public commands | Indices 0–4: public cases, original upstream suite, authored tests, API annotations, production syntax |
| Endpoint gate | Require pinned model/build/template/capacity and one known idle slot; refuse busy/unknown slots rather than disturbing them |
| Cache state | Existing shared server, no generation warmup or cache/slot clearing; preserve actual token/cache counters. No cold-start or cache-equivalence claim |
| Selection | Compare final export with baseline on the same public corpus; reject lost public passes, syntax failures and upstream regression. Preserve intermediate snapshots but do not claim every intermediate is ranked |
| Stop | Interruption, missing catalog, provider/harness failure, timeout or failed owned cleanup stops/quarantines the trial. No resume/retry or automatic additional experiment |
| Independent evaluation | After clean closure/freeze only: independently author 24 distinct fresh cases over the frozen categories. Only payloads reach read-only offline candidate containers; expected values remain outside all worker/container contexts |

The 720-second attempt and 96 operations replace neither old benchmark budgets nor
global production settings. They are reviewed allowances for this single A100 task.
Earlier reasoning-disabled A100 evidence demonstrated visible answers and short
request latency, but is not a throughput forecast for a repository task. Full-loop
latency, coding quality and 64K usefulness remain **UNTESTED** until this trial.
The slot is already allocated for 131K; no memory reconfiguration is requested.

Completion requires model-authored source changes, an executed worker public test,
12/12 public, all upstream regressions, authored tests, annotations/documentation,
and 24/24 fresh independent cases without mid-run implementation guidance. Report
partial progress, no edits, semantic failures and harness failures separately.
Sealed feedback may neither revise nor select the frozen candidate.

## Verification, reproducibility and remaining work

The existing **178-test baseline passed** with installed inert OpenCode/Pi and offline
Docker before this preparation. Four focused guards cover exact approval/consumption,
source drift/managed-profile rejection, A100-only routing and busy/unknown capacity,
and bounded `/slots` array handling. Full regression results and baseline receipts
are in [evidence](evidence/milestone-e-a100/). The expanded **182/182** suite passed
in 162.239 seconds without skips. The final focused tests ran again after
guard review (4/4 in 0.853 seconds). No real inference was used for infrastructure testing.

No controller, router, editor or harness implementation changed. The new narrowly
scoped trial entrypoint handles array-valued `/slots` without relaxing the existing
object-only HTTP API, and uses this checkout rather than a stale installed wheel.
Both issues were found before worker dispatch. The first preparation remains
unchanged as a stale draft; only `trial-final` and its digest are proposed.

Use the [operator commands](../examples/milestone-e-a100/README.md) for read-only
inspection, preparation, validation, approval-gated execution and independent
grading. They require Python, Git, OpenCode, SSH and the offline Docker image;
operating the platform requires no Codex or proprietary model API.

Remaining work, within the original roadmap:

1. Separately approve and execute this one A100 trial; preserve failures and grade
   the frozen result. Decide about harness replacement only from that evidence.
2. Validate the existing REA/Ghidra workbench on authorized targets, reusing its
   preserved reconstruction evidence and requesting any new remote experiment scope.
3. Validate model/compute routing using measured capability and health; preserve
   demanding-task access to A100 and operator overrides.
4. Complete original final acceptance: Windows/operator workflows, ownership and
   interruption handling, reproducibility and operation without Codex.

The Pi/OpenCode comparison remains separately **PREPARED_NOT_AUTHORIZED** for its
original `26c715e...` digest. It is not the next campaign. Historical approvals,
quarantines, frozen Click, existing models and `main` are preserved.
