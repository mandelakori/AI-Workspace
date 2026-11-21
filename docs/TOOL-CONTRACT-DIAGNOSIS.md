# HTTPX editing and allocation diagnosis

Audit baseline: `1995687`, OpenCode 2.0.27, existing local Qwen3.5 9B
profile, 8,192-token context and 2,048-token output ceiling. This work ran
**zero inference requests** and no HTTPX checks, edits or grading. All previous
authorizations remain closed and quarantine states remain in force.

**VERIFIED:** tool-contract errors and unproductive allocation directly prevented
progress. **UNTESTED:** whether a larger model or context would complete the
feature. This trace does not isolate model size as the primary cause.

## Failed edit: two independent defects

The [saved request](evidence/phase61/httpx-editing-pilot/failed-edit.json) used the
correct current source hash, but its 469-byte anchor was reconstructed rather
than copied as a contiguous excerpt. Its first line had **four spaces instead
of twelve** at source line 178, and it omitted intervening source lines
179–182. Correcting indentation alone would still leave no exact match.
The editor correctly returned `anchor_mismatch`, zero matches, the current hash
and a line-178 inspection hint, without writing anything.

Separately, `new` begins with the entire `old` block, while `mode` is `after`:

| Mode | Effect at one matching anchor | Payload containing old + addition |
| --- | --- | --- |
| replace | Remove old; insert new | One old block followed by addition |
| before | Keep old; insert new before it | Old block duplicated |
| after | Keep old; insert new after it | Old block duplicated |

Thus a successful match alone would not rescue this proposal. Its insertion
would duplicate the block, subject also to Python syntax rejection. This audit
does not claim that the particular proposal would pass that guard. Synthetic
tests demonstrate the more general danger: a duplicated executable statement
can parse and satisfy the hash/anchor checks while changing behavior incorrectly.
No hypothetical HTTPX correction was applied or given to any worker.

The former tool description named the modes without defining anchor retention.
It also described `query` as finding a name/text without spelling out literal
substring semantics. Only those descriptions were clarified. Editor behavior,
exact matching, hashes, permissions, deadlines and quotas are unchanged.

## Complete sequence and allocation

The [audit receipt](evidence/phase61/tool-contract-audit/audit.json) joins all
25 recorded tool requests to their MCP receipts. The original
[sequence](evidence/phase61/httpx-editing-pilot/tool-sequence.json) remains intact.

| Trace request | Operation and result |
| --- | --- |
| 1 | Bare `focus`: unavailable tool name |
| 2–4 | Inspect URLPattern, its matches method, then URL |
| 5 | Natural-language query: no literal match |
| 6 | grep for the already identified class |
| 7–9 | Reopen class, matches and constructor by line |
| 10–11 | grep and glob for the already identified URL file |
| 12 | Second natural-language query: no literal match |
| 13–14 | Two more grep requests |
| 15–16 | Open URL constructor region, then start of utility file |
| 17 | Duplicate class excerpt suppressed |
| 18 | Reopen constructor by qualified symbol |
| 19 | Duplicate matches excerpt suppressed |
| 20 | MCP operation 14: sole edit rejected |
| 21 | MCP operation 15: follow the edit's inspection hint |
| 22 | MCP operation 16: reopen URL file, remaining calls = 0 |
| 23–25 | Three further inspections rejected by quota |

Of sixteen admitted MCP calls, **fifteen inspected source, one attempted an
edit, and none ran public tests**. Two failed queries and two suppressed
duplicates consumed four slots. Four native grep calls and one glob were outside
that quota but consumed wall time and inference. Seven tool-error events are
fully accounted for: one name, two queries, one anchor and three quota errors.

Before the edit, 146 of 452 returned source lines had already been returned.
Across the run this was 255 of 572, including 60 lines from the justified
post-error inspection. Overlap is not automatically waste: a method-bounded
excerpt and a line window can legitimately differ. The duplicate guard compares
exact windows, not their overlapping coverage, so these reads were not a bypass.
The constructor's later 29-line excerpt nevertheless added no new source lines.

Sixteen operations can support a compact workflow: for example, four inspections,
four edits, two checks and two recovery calls leave four slots. That arithmetic
does not validate the cap for this repository's discovery, routing semantics,
authored tests and documentation. The observed run primarily establishes poor
allocation: the first edit left only two slots for recovery **and** testing.
Simply raising the cap could enable more exploration without producing edits.

## Repeated starts, tool names and timing

The trace repeatedly says it will start inspecting, even after identifying the
class and method. The saved active objective explicitly requires implementation
and tests; preparation-only instructions were absent. Successful source responses
also repeat the objective and remaining-call count. The worker made three more
inspection requests after receiving zero remaining calls. Goal conflict or
insufficient quota visibility does not explain all of this behavior.

There is no recorded compaction event or provider request history sufficient to
prove context loss. Repeated introductory language is evidence of restarting
the exploration strategy, not proof of a harness resetting the session.

The bare `focus` name differs from the exposed `checks_focus` name. Another
real harness issue is independently established by the saved
[inert-provider probe](evidence/phase61/source-editing/catalog-probe.json): scoped
tools first appeared on its sixth tool-bearing request. Server catalog preflight
does not synchronize OpenCode's asynchronous registration. The pilot's actual
provider-request catalogs were not captured, so its first name error cannot be
attributed conclusively to that race. Once prefixed calls worked, the race does
not explain the subsequent repeated reads or malformed edit.

The approved 150-second attempt ceiling yielded 146.875 seconds at harness setup;
twenty seconds were reserved for verification, leaving a 126.875-second wrapper
allowance. Staging/catalog work left a 125.156-second subprocess, which timed out.
The outer 180-second engineering reservation did not expire; engineering closed
at 148.812 seconds plus 0.219 seconds cleanup. Reservations intentionally constrain
the inner window. Unused outer time was not a permitted extension. Exploration,
failed queries and post-quota requests consumed the available window without
feature verification. No cleanup failure is recorded in this pilot.

## What the model evidence establishes

- The configuration produced a verified 4/4 self-authored editing fixture after
  a rejected request, using 4,902 reported input and 597 output tokens. Its
  harness still exited with a provider-stream error. This proves a narrow edit
  and test capability, not reliable unfamiliar-repository completion.
- The HTTPX pilot completed 25 usage events: 29,922 input, 1,721 output and zero
  reasoning tokens; cache reads were separately reported as 92,295. A 26th step
  started without a completion receipt, so complete usage remains unknown.
- Peak completed-step output was **385**, below 2,048. There is no evidence that
  the output ceiling truncated these completed proposals. No explicit context
  overflow is recorded.
- Peak input field was 5,060; peak cache-read field was 6,805, and the largest
  same-step sum of input/cache fields was 7,298. These are recorded counters,
  not independently established context occupancy. The existing 0.6177
  input/context ratio omits separate cache fields and does not establish spare
  context or retained source history.

The 9B/8K profile has **not demonstrated suitability for the full HTTPX workload
under these limits**. The evidence supports tool-use/instruction-following
weaknesses in this configuration. It does not establish intrinsic model
incapacity, that context expansion would help, or that a different model would
solve the task. Fixture success and guided Click delivery do not establish that
claim either.

## Priorities and a controlled next experiment

1. Keep the clarified literal-search and insertion contract. Require synthetic
   conformance and exact-error recovery before an inference trial. Preserve the
   guards; behavioral verification must remain separate from an applied edit.
2. Resolve or deterministically demonstrate actual provider-facing catalog
   readiness using the existing inert test before a capability comparison.
   Capture the offered tool names for measured requests. A missing tool catalog
   is a harness failure, not a model capability score. This is a specific known
   blocker, not a reason to add more orchestration layers.
3. Prefer a new, small real-library task before HTTPX: a pinned offline checkout,
   one production module plus tests, a meaningful existing bug, a frozen spec,
   reproducible upstream baseline and 8–12 public cases. Confirm it was not a
   previous benchmark. No repository was acquired or selected by this audit.
4. Propose a **direct-only paired pilot**, requiring a fresh reviewed manifest
   and explicit approval. Keep model, 8K context, 2,048 output limit, tool catalog,
   source snapshot, public checks, write permissions, warm protocol and
   20/180/40 reservations identical; retain one attempt, the 150-second attempt
   ceiling and sixteen MCP calls. Randomize arm order. The sole intended
   difference is retrieval: one arm receives a bounded relevant source excerpt
   and interface information upfront; the other discovers it with the tools.
   Provide no solution or mid-run guidance. Record the difference in initial
   information and token load; this is a retrieval comparison, not a pure
   model-size comparison. Freeze both before authoring twelve fresh sealed cases.
5. Success requires an applied edit by operation 8, a public test by operation
   12, all public cases and the frozen upstream selector passing, all twelve
   sealed cases passing, and no scope/hash violations. Record first-edit/test
   times, rejected edits/recovery, repeated reads, usage/cache fields, wall time
   and provider exit. A quarantine stops the comparison without retries. Preserve
   partial and failed outcomes. One pair is diagnostic, not a reliable success
   rate estimate; repetitions need their own approved budget.

If supplied-source succeeds and discovery fails, retrieval/allocation is the
leading bottleneck. If both apply valid edits and test but fail logic, capability
on the bounded task becomes the leading concern. If they fail copying anchors
or selecting modes, tool-contract adherence remains unresolved. If only the
discovery arm exhausts sixteen calls before its time limit, a later separately
approved 16-versus-32 comparison can vary that factor alone. Compare another
model/context only after controlling these conditions; do not infer its benefit
from model size. No such trials or budget increases are authorized here.

## Model-independent verification and preservation

[Three new tests](../tests/test_edit_contract.py) exercise six literal mode
examples, syntactically valid but behaviorally incorrect duplication, and
diagnostic-directed exact recovery followed by stale-hash rejection. They use
only synthetic source, never execute model proposals, and do not claim to test
model comprehension of English instructions.

Reproduce without inference:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_edit_contract tests.test_source_edit tests.test_focus tests.test_harness_context tests.test_trial_budget -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Targeted discovery: **37 tests, 36 passed, one Docker opt-in skipped**. Full
discovery: **135 tests, 128 passed, seven opt-in Docker/installed-harness tests
skipped**, no failures, 51.991 seconds. See the
[regression log](evidence/phase61/tool-contract-audit/regressions.log). This is
not a new all-hardware regression claim. Only tool descriptions changed, not
harness behavior; no live model fixture was run. No measured agent success is
claimed for the wording change.

All 25 entries in the latest original evidence-hash receipt were independently
rechecked successfully. Historical reports, source, quarantine states, frozen
Click and main were not modified. No execution bundle or authorization grant
was created; the experiment above is **DESIGN ONLY / NOT AUTHORIZED**.
