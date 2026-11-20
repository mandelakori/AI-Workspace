# HTTPX recovery comparison outcome

**QUARANTINED — relevant code reached and edits attempted, but no source change
was applied or independently verified.** The comparison authorized for digest
`2a12502209bd9ada3a5082e3ab489bb6423a41a6cdf5144fbec8de05874fe3b9`
ran direct warm-up and one worker session. The harness watchdog interrupted the
session, triggering the approved inference-client quarantine rule. Dispatch
stopped; hierarchical execution and sealed grading were not started.

## Progress and remaining failure

The worker used the new navigation interface to reach the `URLPattern` class
around line 120 and its priority section at line 203. Two unchanged duplicate
excerpts were suppressed. It then issued two native `edit` calls proposing a
path attribute in `httpx/_utils.py`. Both failed exact-match validation:
neither supplied `oldString` occurs in the unchanged source. The proposals are
preserved as model-authored, **unapplied** data; no operator corrected them.

This is progress from exploration into editing attempts. It is not an applied
implementation or a verified partial feature. The worker never called an
approved public test command. All 121 inventoried source files still match the
starting snapshot. No correct source edit, newly passing feature case or new
feature functionality was independently verified.

Four tool errors were recorded: one `checks_focus` unavailable-tool error before
the same call subsequently worked, one rejected absolute-path inspection, and
the two exact-match edit failures. These are observed interface/use failures;
the transient availability error's underlying cause was not investigated during
the frozen comparison. No permission or tool-policy exception was introduced.

| Measurement | Direct | Hierarchical |
| --- | --- | --- |
| Worker sessions / planner requests | 1 / 0 | 0 / 0 |
| Native edit attempts / accepted edits | 2 / 0 | Not started |
| Focus invocations | 7, including one unavailable-tool error | Not started |
| Other native tool calls | 1 glob, 1 grep | Not started |
| Duplicate excerpts suppressed | 2 | Not started |
| Worker public-test calls | 0 | Not started |
| Frozen fallback public correctness | 7/16 feature cases; 75 selected upstream tests pass | No candidate |
| Authored tests/documentation | Absent | Not evaluated |
| New feature functionality independently verified | None | None |
| Sealed correctness | Not evaluated | Not evaluated |
| Completion | Unsuccessful autonomous attempt with rejected edits | Blocked by pair quarantine |

The public score belongs to the **unmodified baseline**, frozen before the
worker ran. It is not a model-delivered score. Its inventory SHA-256 remains
`5d4e3c9e66ae2da5c42bd1d7a58ed6dd0131835f72ddd95ff3fb54282a10e038`.
No challenger was promoted, no source regression was introduced, and no
post-attempt challenger grading was performed. The scorer's legacy `compiled`
field denotes its Python upstream-test gate, not native compilation.

Both engineering phases did not close as required because the hierarchical arm
was blocked by quarantine. Consequently **zero sealed cases were authored**;
there is no 0/24 score or independently verified feature-completion claim.
There was no mid-run guidance or guided recovery. The earlier fixture success
does not establish transfer to this unfamiliar-repository task. This incomplete
comparison provides no evidence of hierarchical superiority. Differences from
historical traces are descriptive observations, not a controlled causal estimate.

## Time and usage

| Recorded timing | Seconds |
| --- | --- |
| Warm execution including termination bookkeeping | 10.719 |
| Engineering execution including termination bookkeeping | 118.234 |
| Engineering cleanup | 0.203, passed; nothing remained to remove |
| Harness subprocess | 95.375, watchdog timeout |
| Full wall time from warm start through engineering close | 129.181 |

Reservations remained 20/180/40 seconds. The 120-second attempt ceiling still
reserved twenty seconds for verification. The new timing receipt records
116.547 seconds remaining in the attempt and a 96.547-second wrapper allowance
before isolated staging/session setup. The harness subprocess then timed out
after 95.375 seconds. The outer engineering process exited with code 1 before
its own 180-second deadline; its `timed_out: false` does not negate the inner
harness's `timed_out: true`. Quarantine caused termination of further work.
No unused time was transferred or used to resume the worker.

Recorded warm usage is **17 input / 2 output / 19 provider-reported total**.
Eleven completed worker usage events record **18,579 input / 2,030 output /
0 reasoning** tokens. Cache counters separately record **35,214 read / 0 write**.
The trace also contains eleven step-start events. Any provider work not
represented in completed records is unknown; complete provider request/token
totals are not independently available. A harness timeout does not establish
what the unowned backend was doing at that instant. Backend cancellation
latency remains unmeasured.

The controller created an `attempt-002` bookkeeping record, whose lease guard
rejected execution with zero elapsed time. There was no second worker claim,
retry inference dispatch or planner request. Container cleanup passed, and the
shared inference service was not restarted or terminated.

## Preserved evidence and closure

The [outcome](evidence/phase61/httpx-recovery-run/outcome.json),
[raw trace](evidence/phase61/httpx-recovery-run/direct-agent.jsonl),
[live trace](evidence/phase61/httpx-recovery-run/direct-agent-live.jsonl),
[navigation log](evidence/phase61/httpx-recovery-run/direct-mcp.jsonl),
[unapplied model proposals](evidence/phase61/httpx-recovery-run/unapplied-model-proposals.json),
[timing receipt](evidence/phase61/httpx-recovery-run/direct-harness-budget.json),
[usage](evidence/phase61/httpx-recovery-run/direct-agent-metrics.json),
[source receipt](evidence/phase61/httpx-recovery-run/direct-source-receipt.json)
and [local evidence inventory](evidence/phase61/httpx-recovery-run/evidence-inventory.json)
preserve the run, authorization, blocked retry record, hashes and public baseline.
The inventory covers 1,146 local files at capture time. The retained external
stage was also copied to
`.aiwork/phase61-recovery/httpx-prepared/archival/direct-attempt-001-source`.
Preservation did not execute, repair, test or promote that source.

The approved implementation, inputs, model settings, image, scopes and budgets
were unchanged. Previous evidence, frozen Click and `main` remain preserved.
No new regression campaign was run because there were no implementation
changes; the approved controller previously passed 120 regressions. No remote
inference, deployment, additional campaign or merge occurred.

This single authorization is closed to further dispatch. Do not run the
hierarchical arm, create acceptance cases, resume unused reservations or reuse
this grant for another comparison.
