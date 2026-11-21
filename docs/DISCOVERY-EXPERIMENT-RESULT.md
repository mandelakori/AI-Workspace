# Source-discovery experiment: quarantined, Phase 6.1 benchmarking closed

**QUARANTINED.** The one approved comparison for digest
`ee17b4c45b8b82dccc1790a91dec1dead8c2983625121b86d785e743a39443d0`
stopped during **B**, before A started. No retry, additional campaign, independent
grading or sealed-case authoring followed. Phase 6.1 benchmarking is now **closed**.
The next [development plan](NEXT-DEVELOPMENT-PLAN.md) requires separate review;
it has not been implemented or dispatched.

The original manifest, model, inputs, image, permissions and budgets were unchanged.
One worker session and one attempt ran, with zero planner requests and no mid-run
implementation guidance. The [outcome](evidence/phase61/discovery-result/outcome.json),
[authorization](evidence/phase61/discovery-result/operator-authorization-receipt.json),
[budget journal](evidence/phase61/discovery-result/trial-budget.json) and
[complete tool sequence](evidence/phase61/discovery-result/tool-sequence.json)
preserve the run. The frozen preparation review remains historical evidence,
not permission to run again.

## Requested results

| Measurement | B: autonomous discovery | A: source supplied upfront |
| --- | --- | --- |
| Status | Quarantined after harness timeout | Not started; withheld |
| Edit requests / applied edits | **0 / 0** | Not run |
| Executed worker public tests | **0**; one request refused after quota | Not run |
| First edit by MCP operation 8 | **Not achieved** | Not measured |
| First public test by operation 12 | **Not achieved** | Not measured |
| Public correctness | Pre-worker baseline **2/10**; source unchanged | Not run |
| Upstream correctness | Preparation baseline **287 passed, five skips**; no post-worker rerun | Not run |
| Authored regression tests | No test file created | Not run |
| Sealed correctness | **NOT RUN**; zero cases authored | Not run |
| Accepted corrections / regressions | No candidate or correction; baseline identity preserved | Not run |

All **47** source-inventory entries in both B's exported workspace and its retained
isolated stage match the approved baseline. This independent hash check preserves
the unchanged source; it is not post-quarantine behavioral grading. There is no
model-delivered candidate, selected checkpoint or successful autonomous completion.
Absent results are not zero scores. An archival source copy and ownership receipt
were preserved separately from candidate selection.

## Registration worked; context coordination did not

The required MCP server became ready in **2.109 seconds**, before implementation
inference. **All 32 provider-facing requests contained all four required tools**,
with no missing or unexpected names. Model identity and `reasoning_effort: none`
were preserved. OpenCode adjusted output allowances between 1,024 and 2,048 tokens,
within the frozen 2,048 ceiling. No tool schemas or request bodies were rewritten.

The gate's final `failed_closed` flag records a **ConnectionAbortedError** on
request 32 during the timeout/termination path. It does not establish a missing
catalog: every recorded catalog passed. Private-server cleanup and trial-owned
container cleanup both passed. No explicit provider invalid-stream error event
was recorded; the final response was interrupted and has no completed usage receipt.
Backend cancellation latency remains unmeasured; no shared service was interrupted.

The wire evidence establishes a more specific context defect:

1. By MCP operation **3**, the worker had received all **86 lines** of the primary
   module. The following request (4) was an automatic context-compaction call.
2. Request **5**, the next implementation generation, contained its prose summary
   but none of the source markers `def parse_variables`, `result = env.get` or
   `(?P<default>`. Operation **4** attempted to reopen the file and received an
   empty, duplicate-suppressed excerpt: the controller still considered that
   unchanged window already supplied.
3. A second compaction at request **12** again removed verbatim source from the
   following implementation request (**13**). The summaries preserved the broad
   feature objective, but not the complete original instructions or source.
4. The saved operator-task file was configured, yet the actual provider system
   message contained neither its active-objective header nor the full task text.
   After compaction, the initial detailed user request was replaced by summaries.
   File/config persistence therefore did not demonstrate provider-facing task
   persistence. The precise instruction-loader behavior needs review before a fix.

The summaries and wire archive allow these observations to be checked directly.
This interaction obstructed the worker's chosen reinspection strategy. Later
function windows did provide useful code, so it does not prove that a more effective
worker could not have edited within the remaining allowance.

The worker also repeatedly sought the entire file rather than using available
windows, issued two invalid literal queries (`resolve method`, `import re from abc`),
and continued making requests after explicit quota errors. These are observed
tool-use/progress-control failures. The editor itself was never invoked, so this
run cannot assess its replacement semantics or the model's implementation logic.

## Tool allocation and deadlines

The sixteen admitted MCP operations were **15 focus calls and one empty diff**.
Two literal queries failed; five unchanged duplicate excerpts were suppressed.
Returned source totaled **195 lines**, with **109 lines of unchanged-version
overlap**, covering the same 86-line file. One native grep ran outside MCP quota
but within the same deadline.

There were 29 recorded tool requests: 25 focus, two diff, one grep and one public
check. **Twelve post-quota MCP attempts were refused**, including the only public
check request. All fourteen tool errors are accounted for by those twelve refusals
and two query mismatches. No unprefixed or otherwise unavailable tool name was used.
The quota held; the worker nevertheless continued inference until its watchdog.

| Timing | Seconds |
| --- | ---: |
| Warm process | 18.015 |
| Engineering process | 133.640 |
| Engineering owned-container cleanup | 0.391; passed, none removed |
| Harness, including its readiness/termination bookkeeping | 118.391 |
| Wall time, warm start through engineering close | **152.096** |

The 150-second attempt had 139.046 seconds left at harness setup. Its twenty-second
verification reserve left a 119.046-second wrapper allowance; staging/preflight
also consumed that window. The inner harness reports exit **1**, `timed_out: true`,
`truncated: false`. The outer 180-second engineering watchdog did **not** expire;
the work process exited **1** after quarantine. Unused outer time was not a permitted
extension. The top-level runner exited **0** because its failure branch returns
after recording the failed phase; that shell status is not engineering success.

## Complete usage and cache accounting

There were **32 engineering API requests**, with **31 completed raw usage receipts**.
Two were automatic context-compaction requests, not new worker attempts. The harness
trace exposes 29 completed implementation steps and omits those two summaries from
its step-finish totals. Raw wire receipts reconcile the difference:

| Completed request category | Uncached prompt | Cached prompt | Output | Total including cached prompt |
| --- | ---: | ---: | ---: | ---: |
| Implementation steps | 20,473 | 138,862 | 1,735 | 161,070 |
| Two context summaries | 11,617 | 1,554 | 928 | 14,099 |
| Neutral READY warm-up | 17 | 0 | 2 | 19 |
| **Known total** | **32,107** | **140,416** | **2,665** | **175,188** |

Cached tokens are part of the prompt total, not an additional count to add again.
The final engineering request has no completed usage; complete experiment totals
are therefore **unknown**, with the table reporting only received usage receipts.
The raw API did not separately report reasoning-token details; the harness recorded
zero and all outgoing requests disabled reasoning. These timings include tools,
orchestration and compaction; they are not isolated GPU throughput measurements.

The first prompt used **5,086 tokens**. Peak reported full prompt, including cached
tokens, was **7,440** against the 8,192 context configuration. There was no explicit
context-overflow error. The older uncached-input/context ratio of 0.6208 does not
describe full context occupancy. A never ran, so its added token cost and A–B delta
remain **unmeasured**; its prepared extra prompt text remains 3,525 bytes.

## Conclusion and closure

The registration blocker was resolved in real execution. The remaining observed
failure combines context compaction, an unsynchronized source cache, and ineffective
worker allocation. It does **not** establish an intrinsic 9B reasoning ceiling or
an upfront-retrieval advantage. There was no matched pair, and no feature logic
was independently graded.

All source edits to AI Workspace in this closeout are documentation/evidence only;
the approved execution implementation still matches its manifest. The pre-run
regression evidence remains **141 passed, five optional integrations skipped**;
no additional model fixture, regression campaign or verification container was
launched after quarantine. All historical HTTPX evidence, frozen Click, models,
remote services and main remain unchanged. No sealed material was created or
returned to a worker. **Do not resume either arm or reuse this approval.**
