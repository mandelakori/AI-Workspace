# Phase 6 engineering report

Working feature delivered on `phase6/real-world-engineering`, based on `ebdd2cb`.
Phase 5 remains at that commit on `phase5/hierarchical-engineering`; `main` remains
`cf50e89`. No remote inference, service restart, deployment or merge was performed.

## Feature and independent results

The target is [Pallets Click 8.3.2](https://github.com/pallets/click/tree/052c006033729bbb422cbdad0c4fee988ecb5aa5),
an unfamiliar real package with approximately 11,000 source lines and a substantial
existing integration suite. This is an operator-specified additive feature, not
an upstream issue or upstream-approved API. The pinned BSD-licensed checkout was
preserved. [FEATURE.md](../examples/phase6/FEATURE.md) was frozen before inference.

`click.ISODateTime` adds standard-library ISO parsing, timezone requirements,
UTC normalization, introspection and CLI integration while preserving `DateTime`.
The patch changes five related files: implementation, public export, seven new
tests, parameter documentation and API documentation. It contains 248 insertions
and one deletion. No experiment helpers or private evaluation inputs are in it.
Export normalizes CRLF to LF without changing text or Python ASTs; the manifest
distinguishes raw frozen hashes from portable delivery hashes. A clean patch
application was separately retested against the default repository suite.

| Verification | Result |
| --- | --- |
| Unmodified baseline | 1,385 passed, 21 skipped, 30,000 stress cases deselected by upstream defaults, 1 xfailed; feature absent, 0/25 original public checks |
| Final public acceptance | **31/31**, including CLI behavior, datetime-object policies, actual execution of authored CLI tests and documented examples |
| Final repository suite | **1,392 passed**, same 21 skips, 30,000 default deselections and 1 xfail; no lost upstream passes |
| Offline package integration | Wheel built and installed in a temporary directory; isolated Python imported the installed wheel and passed valid/error CLI checks |
| Fresh sealed acceptance | **32/32** after an independently documented evaluator correction; identical frozen source throughout |
| Controller regression | **90/90**, preserving all existing 83 tests; installed OpenCode boundary check enabled; direct fixture verified |

The image is pinned to `sha256:885f0aefe0ae650b7115ca729d533b74f092712a0b5b340262090d5ccfc8ffeb`.
All candidate tests used local offline Docker. This feature is Python; C compiler
and UBSan stages are inapplicable. Production imports, Python syntax, repository
behavior and package build/install are separate from behavioral acceptance.
Upstream formatting/type checks and a complete Sphinx build remain **UNTESTED**.

The final inventory was frozen at **2026-11-20 08:43:23 UTC**, hash
`e692e0930abe59b27ae820aeeb1eeae59a51a5f9fc638250886505b34fcd1f04`.
Only then were 32 fresh sealed cases authored. They cover additional ISO grammar,
fractions and offsets, normalization across boundaries, object identity,
offset-None timezone policies, unsupported values, introspection and CLI paths.
Expected results stayed outside the candidate mount. Every execution used a
read-only candidate and no network; source hashes matched before and after.
No subsequent model requests or source repairs occurred.

The first sealed pass was 31/32 because the checker assumed an argument-name
hint. Unchanged upstream `Argument.get_error_hint` uses `make_metavar`, so the
frozen `ISO_DATETIME` contract was correct. Only the evaluator literal was fixed;
identical inputs and candidate then passed 32/32. Original grading and raw
responses remain preserved. See [grader correction](../deliverables/phase6/grader-correction.json).
This was an evaluator correction, not a candidate repair from sealed feedback.

## Autonomous work and intervention

The existing model planner proposed API/tests followed by documentation. Operator
review corrected command ownership so the first component did not depend on
documentation that had not yet run. The two-stage hierarchy never completed its
API gate. Eight tool sessions produced one partial implementation and repeatedly
lost task context after oversized reads. New generated tests initially failed
11/23 cases, including duplicate package imports and a raises block with no call.

Recovery used the existing scoped source adapter, component contracts, offline
verification, ranked selection and hash-checked integration. It retained the
model-authored partial implementation, then narrowed repairs to the timezone
method and the existing CLI test method. Public diagnostics and unmodified
upstream examples were supplied as evidence. A public standard-library interface
contract was needed to distinguish the two timezone offset method signatures.
Reasoning was enabled per request for later trials using the same local model
and 8K serving context, without changing model files or server configuration.

All production implementation and test corrections were authored by the local
model. The controller supplied no replacement production code. However, this was
**operator-guided completion, not unassisted end-to-end autonomy**. Scope design,
context preparation, API contract lookup, public diagnoses, stopped sessions and
integration required intervention. Documentation was additionally operator-assisted:
after a model edit lost required text, review retained its valid unused-flag removal,
removed the duplicate docstring it introduced and removed a false error transcript.
That cleanup is explicitly recorded, not attributed to autonomous repair.
Python trailing whitespace was normalized with identical ASTs; selected raw
model checkpoints were preserved.

## Measurements and failure preservation

Only the existing local `aiwork-qwen35-phase4:8k` model was used: Qwen3.5 9B Q4_K_M,
8,192 serving tokens, at most 2,048 output tokens per scoped source request.
Source requests were bounded to 45 seconds and one or two proposals per reviewed
unit. All separate campaign budgets and actual requests remain recorded.

| Measure | Recorded result |
| --- | --- |
| Planning | 1 request, 2,176 input / 262 output tokens |
| Tool sessions | 8; none independently completed the feature |
| Scoped source requests | 20; 5 promoted partial corrections, 15 rejected/failed (25% promotion rate) |
| Regression protection | 9 worse proposals rejected, representing 50 lost-case outcomes across overlapping public checks; not 50 distinct behaviors |
| Token counters | At least 195,716 reported input and 23,520 output tokens across planning, tool sessions and source requests |
| Worker tool calls | At least 98 recorded calls; source workers made no tool calls themselves |
| Measured execution | 1,589.923 seconds across tool attempts; 429.408 seconds for source requests with complete timing receipts |
| Staged spec to candidate freeze | 69.46 minutes, including verification, diagnosis and integration |

Two early OpenCode traces hit the old 1 MiB cap, and one HTTP request timed out
without a complete response. Token/tool totals are lower bounds, not precise
total consumption; cache fields are retained separately in receipts. No cloud or
proprietary API charges were incurred or estimated. The complete public counters,
raw-response hashes and individual decisions are in the
[evidence summary](../deliverables/phase6/evidence-summary.json).

Rejected states include unchanged-source responses, lost public behavior, malformed
response protocol, an exhausted request timeout, fabricated CLI fixtures, incorrect
callback parameters and documentation errors. Failed staging and stopped queues
are preserved separately and did not all issue inference requests. One second
documentation request was already dispatched when its stop flag arrived; it is
included in the 20-request total and was rejected. No exhausted historical Phase 5
job or benchmark was resumed or edited.

## Infrastructure corrections and limitations

Four small controller corrections were justified by observed failures: bounded
8 MiB harness trace capture; an explicit operator-task instruction file; source
adapter instructions permitting the requested tests/documentation; and public
traceback excerpts retaining the final exception. The existing compaction
threshold was restored after disabling compaction at 8K failed to help. Persistent
instructions did not resolve oversized-read context loss. Regression tests cover
trace bounds, context privacy, source-purpose wording, scoped assembly/signatures
and non-disclosure of sealed diagnostics.

Hierarchy did **not** demonstrate an improvement over simpler execution. The
hierarchical attempt failed; guided source proposals recovered its artifacts.
These runs used different contexts, prompts, reasoning settings and warm starts,
so they are not a matched performance comparison. Reliable autonomous repository
exploration and debugging remain limitations despite the correct delivered feature.
Finite test agreement is not proof of complete equivalence or upstream acceptance.

Raw plans, inputs, model responses, workspaces, checkpoints and verification
receipts remain under `.aiwork/phase6`; private final materials are confined to
`private-final`, outside worker contexts and Git. The original and selected
artifacts are retained. [Delivery instructions](../deliverables/phase6/README.md)
describe patch application and offline verification; [experiment commands](../examples/phase6/README.md)
describe staging and public replay. Further inference is not part of finalization.
