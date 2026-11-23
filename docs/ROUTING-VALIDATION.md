# Local and A100 routing validation

Validated from `bac5fad` on `phase61/autonomous-completion`. No live engineering
worker was dispatched. Measurements below come from the installed inert harness,
read-only host observations, or the preserved local calibration, as indicated.

## What the controller actually does

| Capability | Validation | Observed policy |
| --- | --- | --- |
| Profile eligibility and overrides | Verified | The router filters by declared tool support, minimum context, explicit location and exact profile ID. A CLI profile override replaces the manifest profile and resets location to automatic. The local-only source-proposal constraint still applies. No compatible profile means no dispatch. Engineering capability admission separately rejects adapters that lack any required safeguard. |
| History and task complexity | Verified | The eligible planner preference ranks first, then same-category `(verified + 1) / (graded + 2)`, then complexity's preferred plane, then mean verified-attempt time and stable profile ID. Complexity 1–3 favors local and 4–5 favors A100 on a tie. Failed and partial attempts count toward the grading denominator. Blocked attempts, other categories, current queue time and current endpoint health do not affect this score. The isolated history case selected local for a complex task. |
| Local GPU and context admission | Verified | Explicit VRAM minima apply to a nonresident local model, including when GPU telemetry is missing. A positive Ollama residency signal avoids recharging the load minimum, and reported resident context can reject a route that passed the declared context filter. Shared-server jobs without a runtime context report use the declared limit. |
| Local RAM, cold time and offload | Partially verified | The calibrated path uses current RAM and VRAM headroom and measured context, residency/offload and a cold request estimate. It admits the smallest qualifying measured window. Synthetic rejection cases and the preserved calibration were checked. Ordinary noncalibrated jobs have no comparable RAM or cold-time forecast. Calibration does not predict software-engineering completion. |
| A100 health, concurrency and reservations | Verified in isolation and read-only preflight | The existing configuration uses one host-side lane lock and an owned localhost SSH forward. Busy and unavailable cases exercised the timeout, release and fallback paths with isolated state. Read-only preflight observed one idle slot on the existing endpoint. The generic router does not schedule across independent lock roots or inspect live backend slots to rerank. The prepared arm verifies the actual slot during preflight. |
| Local concurrency and reservations | Verified | A laptop Ollama or VRAM-constrained reservation is exclusive across controllers using the same execution-state root. An unconstrained profile uses a single configured slot. A separate A100 lane can remain available. The Windows lock test used a second process and different configured slot counts. |
| Independent acceptance and retry | Verified | The controller hashes and scope-checks staged changes and runs independent checks in the offline verifier. An ordinary unsuccessful attempt can advance only within the existing eligible list and attempt budget. The last eligible profile can be reused if attempts remain. Ranked retries retain or roll back in-policy candidates against public checks. Independent sealed verdicts are not used to select ranked checkpoints. |
| Interruption, resource limits and cleanup | Verified deterministically | Resource receipts distinguish clean exhaustion, provider failures and owned cleanup failures. Measured work uses a one-shot phase lease with absolute deadlines, planner/session quotas, quarantine on interrupted inference, and no resume of consumed phases. Ordinary jobs may be explicitly resumed under a new invocation budget. A reported worker cleanup failure prevents acceptance and automatic fallback. Backend cancellation under new live load remains unmeasured. |
| Verification and evidence | Verified with installed inert OpenCode | Unapproved paths were rejected. Raw forwarded bytes matched recorded hashes. The verifier can reject a scoped edit and a passing worker public test. The existing isolation tests prove the private oracle is not mounted for the candidate. |

Routing order is predictive. Admission, queue waits, and independent verdicts
are measured later. This validation established one host's lock and routing
behavior and did not exercise managed cloud lifecycle or cross-host arbitration.

## Reproduced defects and fixes

1. A local job marked exclusive held slot zero only. A peer exposing two slots
   could then enter slot one. Exclusive local reservations now acquire all
   supported slot locks, releasing partial acquisitions before the next bounded
   try. The lock names and the A100 lane are unchanged.
2. A configured VRAM minimum admitted a nonresident local model when the GPU
   readings were empty. An absent reading now records an admission rejection
   before harness execution. An explicitly confirmed resident model retains its
   existing exemption.
3. An attempt with a valid edit could be accepted despite failed cleanup of the
   provider relay or the isolated local inference process. The controller reads
   both ownership receipts, retains the attempt evidence, classifies it as a
   cleanup failure, and stops before acceptance or automatic fallback.
4. The installed OpenCode sent `max_completion_tokens`, whereas Ollama 0.40.17
   reads `max_tokens` for this endpoint. OpenCode's Ollama requests now also
   include the configured ceiling under `max_tokens`. The inert payload asserts
   the effective field on each request. The llama.cpp request is unchanged.
   [Pinned Ollama request parser](https://github.com/ollama/ollama/blob/v0.40.17/openai/openai.go#L103-L123)

The pre-fix targeted run recorded four failed assertions across the lock,
telemetry and relay-cleanup defects. A separate reproduction covered owned
local inference cleanup after a clean relay exit. The final targeted run passed
11/11 tests, and the complete installed suite passed 246/246 in 217.778 seconds
with zero skips. History and attempt outcomes were created in isolated test
state. The existing direct fixture also passed without requesting a model.

### Installed inert execution

Both paths used installed OpenCode, the provider relay and local Docker. The
A100 tunnel was replaced by a local inert endpoint for this test. Each path used
five scripted requests, 550 prompt tokens and 55 completion tokens as reported
by the fixture, with no reasoning-token breakdown. Each used four MCP operations
and retained 44. The operation sequence was inspect, rejected out-of-scope edit,
accepted scoped edit and passing public check. Both cleanup receipts passed.
Independent verification accepted the local fixture and rejected the A100 fixture
whose scripted answer was deliberately incorrect. This does not compare models.
The synthetic local/A100 harness times were 3.531/3.704 seconds. All 30 captured
files matched their receipt hashes and byte counts, totaling 106,609/110,127
bytes by lane, with zero outstanding evidence reservations. Per-request payloads,
streams, timing and receipts are archived with hashes.
[Deterministic evidence](evidence/routing-validation/README.md)

## Prepared cross-plane check

Both arms use the original two-file `examples/project` Celsius conversion
fixture. Pristine verification passes 1/4 public and 0/6 independent cases.
`units.py` is the only writable file. The worker must apply a scoped edit and
successfully run public check 0. The controller reruns all four public checks.
Clean harness closure and phase cleanup are required before candidate freeze.
The independent grader then runs six common input/output cases under a
read-only, network-disabled Docker runner, with expected outputs held outside
the candidate workspace. An incomplete grade is a phase failure.

| Frozen setting | Local | A100 |
| --- | --- | --- |
| Profile and model | `measured-opencode`, Ollama `qwen3.5:9b` Q4_K_M, exact local manifest and eight blob hashes | `a100-existing`, Qwen3.6 35B-A3B Q6_K, exact loaded GGUF path, llama.cpp build `b12063-2cbca389f` and chat-template hash |
| Thermal and residency protocol | Owned isolated Ollama, cold model start, calibrated 16K admission | Existing resident server, one idle 131,072-token slot checked read-only |
| Thinking OFF | `reasoning_effort: none` | `reasoning_effort: none` and `chat_template_kwargs.enable_thinking: false` |
| Approval arm | `["local"]` | `["a100"]` |
| Approval digest | `104261027ac6cb375643266f1f58ba0fefc3c832a8a166b086a36b4798296568` | `38e4cbbc7d1cd5d1b01696c0858a1858e06dcd94948fdbdfd0eb101b9cf2d3de` |

Common limits are OpenCode, 16,384 harness context, 1,536 output tokens per
request, temperature 0, seed 1729, one 240-second attempt, 12 total model requests,
one compaction, and 20 MCP operations with four reserved edits and four reserved
public checks. Phase reservations are 20/265/45 seconds for preflight, work and
grading. The work lease includes the laptop cold start. The existing 64 MiB
capture limit and 32 MiB headroom apply. There is no planner, retry, fallback,
mid-run guidance, or remote lifecycle action. The backend model and warm/cold
starting state differ by design. Report readiness, first response, first edit,
first public check, prompt/completion/reasoning usage if reported, verification,
and queue/worker/cleanup time separately. This is a cross-plane reliability
check across the established profiles, with no causal hardware-speed claim.

The local preflight saw 8,263,827,456 free GPU bytes and 11,311,628,288 available
RAM bytes. It selected 16,384 using the prior observed 7,440-token OpenCode
envelope plus output and reserve, a conservative planning input for this smaller
fixture. The 171.923-second cold request estimate is derived from calibration.
The A100 identity is the server's reported loaded path, quantization, build and
template. The remote weight file was not read or hashed. The Ollama thinking
setting follows its Boolean-model API contract. The prepared arms have no live
reasoning-emission measurements. [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility#v1chatcompletions)

The prepared bundle is `.aiwork/routing-validation/cross-plane-final` on the operator
checkout. Both arms are `PREPARED_NOT_AUTHORIZED`. Manifest validation rejected
six invalid grants and a modified source copy before dispatch. The exact
manifests, hash inventories and redacted pristine receipts are versioned.
The private case bytes and any future approval files stay outside Git.

```powershell
$bundle = '.aiwork/routing-validation/cross-plane-final'
.\.venv\Scripts\python.exe examples/native/cross_plane_trial.py validate "$bundle/local"
.\.venv\Scripts\python.exe examples/native/cross_plane_trial.py validate "$bundle/a100"
```

For a separately approved arm, create an external JSON file with only
`approval_digest`, `authorize` containing that exact single arm, and
`operator_approved` set to `true`. Use `run <bundle/arm> <approval.json>` in place
of `validate`. Compare the two independently recorded arms only after separate
approval. Stop on failed preflight, interruption or cleanup failure. The live
runner's immutable approval, scope, resource and grade paths have been reviewed
and the invalid-grant path exercised offline. The live paths remain unexecuted.
