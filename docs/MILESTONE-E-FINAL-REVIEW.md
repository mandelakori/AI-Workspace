# Milestone E: final autonomous acceptance trial review

**PREPARED_NOT_AUTHORIZED. No live inference.** This prepares one final
ItsDangerous attempt using the existing A100/OpenCode combination. After that
separately authorized attempt, stop and assess Milestone E; do not automatically
repeat ItsDangerous, change harnesses or begin another phase.

Bundle: `.aiwork/milestone-e-final/acceptance-trial`.

Approval digest:

`b6d7338aad1fa82343277ab37ac7c4afb946ec4da7353a6040e3abda977a71f6`

Separate approval must authorize exactly `["a100-existing"]`. The example grant
is false, no real approval/execution marker/state/frozen candidate/private cases
exist, and all three consumed approval digests were rejected against this bundle.

## Public verification and clean baseline

The original **FEATURE.md and twelve public cases are byte-identical**, as is the
original observer/verifier. The **42-file pristine inventory** is unchanged at
ItsDangerous `672971d66a2ef9f85151e53283113f33d642dabd`. All target production,
documentation and upstream-test bytes start clean. No historical implementation,
diagnostic driver or source correction is copied into the **49-file worker input**.
The authored test file is absent: the worker must create it.

[PUBLIC-VERIFICATION.md](../examples/milestone-e-final/PUBLIC-VERIFICATION.md)
clarifies the existing specification. The added 36 public behavior cases cover
integer equality/expiry beyond floating-point exactness, very large integer
limits, None, unsupported types, signature-before-age validation, negative/zero
durations, equality, fractional durations, future timestamps, unsafe paths,
rotation, UTC metadata and custom separators. Inputs and expected observations
come from the frozen requirements and pristine behavior, not a proposed solution.

| Pristine measurement | Result |
| --- | --- |
| Original public behavior | **3/12** |
| Additional public behavior | **19/36** |
| Expanded combined behavior | **22/48** |
| Original upstream suite | **297/297** |
| Syntax | PASS |
| Authored tests, interfaces, documentation | FAIL as expected before implementation |

The combined score includes the original twelve; it is not another 48 independent
cases or a feature-completion percentage. Original and expanded scores remain
separate in receipts. Public expectations are development material, not sealed
acceptance or operator implementation guidance.

The authored-test gate requires at least six passing collected tests, assertions
or raises, no skipped/xfail results, six duration API calls, integer/None/unsupported
coverage and an integer beyond 2**53. It runs twice in isolated child interpreters
under different frozen UTC clocks, forbids real sleeps including aliases, and
rejects direct bytes-separator encoding. Runtime profiling observes target calls
without replacing their behavior. Parameterized tests are supported. Unit-only
pristine-reference fixtures validate the verifier; they are **not worker inputs
or supplied feature tests/solutions**.

Bounded per-test node IDs and assertion/error details survive both child test
runs and the concise tool summary. A dedicated assertion-canary regression checks
this path. A never-authorized development snapshot was superseded to fix lost
diagnostic detail before final freeze; its manifest and source snapshot remain
preserved and the current loader rejects its stale assets.

Documentation must change meaningfully and mention duration/seconds/fractions,
zero/negative limits and inclusive equality. Relevant docstrings and all public
max_age annotations/overloads are checked. These are bounded structural checks;
semantic prose review and general proofs of test determinism remain outside what
two clock runs/lexical checks establish.

## Mandatory closure and evaluation independence

The public command menu has eight indices: original, expanded, upstream, authored,
interfaces, documentation, syntax, then **acceptance at index 7**. Acceptance runs
all seven gates in one offline container, reducing repeated startup overhead. The
clean-source aggregate took **13.235 seconds** in the preparation receipt, below
the existing 20-second controller verification reserve; expensive/failing future
tests still face the unchanged hard deadlines.

Successful engineering closure requires a clean **completed** harness, verified
controller result, model-authored edits, a successful worker acceptance call,
**12/12 original and 48/48 combined behavior**, every mandatory gate passing, no
lost public passes and an unchanged verification workspace. There is no freeze of
the pristine baseline as a substitute. Clean partial/quota-exhausted work is
retained in `engineering-incomplete.json`, without a freeze or grade. Provider,
interruption, catalog or cleanup failures quarantine and cannot resume.

Only after successful closure and freeze may an independent evaluator author 24
new sealed cases. None exist now. A controller-only list contains **83 unique
public/prior-diagnostic input fingerprints**, outside the worker input. Novelty
keys ignore cosmetic IDs/messages, normalize equivalent durations and API aliases,
and reject duplicate/reused public or diagnostic inputs. This is a conservative
input identity guard, not a universal semantic-equivalence proof. The independent
author must still construct genuinely fresh cases from the specification.
Sealed feedback cannot repair prompts, select candidates or reach the worker.

New sealed payloads must set `expanded:true`, using the public runner's documented
API/limit fields. Expected observations stay in the independent case file; only
payloads enter read-only, network-disabled grading containers. The original
20/900/120 phase protocol and twenty-four-case grading reservation remain.

## Output ceiling and resources

Historical requests **43 and 44** finished at **4096 output tokens** with incomplete
tool arguments. Their already-generated decoded replacement prefixes were
**4980 and 7100 UTF-8 bytes**, each exceeding the editor's **3000-byte** new-text
limit before completion. Raising output tokens would not make those edits valid
and would increase generation/trace volume. **Retain 4096**. The upfront contract
requires short edits/inspected locations rather than oversized file rewrites;
there is no new evidence justifying a larger ceiling. Not every pathological
maximum-size JSON/anchor combination is guaranteed to fit the token ceiling.

Unchanged: Qwen3.6 35B-A3B Q6_K, OpenCode, **65536 context**, output 4096,
temperature 0, seed 1729, reasoning disabled; one worker/720-second attempt,
96 MCP operations (eight reserved edits/eight reserved public tests), 64 model
requests/four compactions; no planner, retries, fallback or mid-run guidance.
Only `src/itsdangerous/timed.py`, `docs/timed.rst` and the requested authored-test
file are writable. Model, image, binary, permissions and resource fields match
the last reviewed profile. The read-only endpoint snapshot matches the prior
model/template/build identity and idle 131072-token slot; owned forward closed.
No remote service/model/storage configuration changed or new weight hash claimed.

The verified capture implementation is unchanged: **64 MiB payload /32 MiB disk
headroom**, 16 MiB metadata and 1024 admitted request ceiling. A separate **64-request
inert replay**, padded on every request with all **28755 bytes** of current public
material and using the final contract/menu, archives **25215306 bytes**. All **192
payload hashes** and stream completions pass; **41893558 bytes** of payload margin
remain. Disk free was 262658777088 bytes. This measured conservative trace mix
fits the proposed policy; it does not guarantee every possible maximum-size model
output/context sequence. Hard limits and clean resource exhaustion remain enforced.
Replayed response usage events are historical data, not new model tokens.

## Verification, artifacts and operator commands

**231/231 controller regressions pass, zero skips, 213.292 seconds**, including
installed inert OpenCode/Pi conformance. Eleven new tests exercise closure gates,
incomplete-work retention, tamper rejection, source/approval/resource drift,
novelty, original/expanded baseline, deterministic authored-test validation and
the actual final OpenCode command menu. One intermediate inert assertion assumed
the API key `max_tokens`; it was corrected to accept the existing equivalent
`max_completion_tokens` spelling, with the 4096 value strictly checked. No runtime
generation setting changed.

[Manifest](evidence/milestone-e-final/prepared/manifest.json),
[verification](evidence/milestone-e-final/verification.json),
[preparation checks](evidence/milestone-e-final/preparation-verification.json),
[capacity proof](evidence/milestone-e-final/capture-admission/summary.json),
[preservation](evidence/milestone-e-final/preservation.json).
All **4031 historical indexed entries** and main are unchanged. The core editor,
capture, harness and original trial assets were not modified. New code is limited
to this dedicated public verifier/protocol and its regression tests.

Validation only, with no model dispatch:

```powershell
.\.venv\Scripts\python.exe examples/milestone-e-final/trial.py validate .aiwork/milestone-e-final/acceptance-trial
```

Only after explicit approval of this digest:

```powershell
# Create an exact operator-approved grant using the false example's schema.
# Revalidate all hashes, dependencies, endpoint identity, slot and tool catalog.
.\.venv\Scripts\python.exe examples/milestone-e-final/trial.py run .aiwork/milestone-e-final/acceptance-trial --approval <approval.json>
# After successful engineering-closed.json/frozen.json only, independently author
# 24 genuinely fresh private/cases.json entries, then invoke the gated grade command.
```

No environment/settings incompatibility was detected. Live capability under the
stronger gates remains **UNTESTED**. Stop at **PREPARED_NOT_AUTHORIZED**. After its
one eventual authorized execution, assess whether this model/harness has met
Milestone E; do not automatically prepare or repeat another ItsDangerous campaign.
