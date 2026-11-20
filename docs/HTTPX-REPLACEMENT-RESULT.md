# Replacement HTTPX comparison result

**QUARANTINED — autonomous attempt failed to deliver an implementation.**
The comparison authorized for digest
`cac8f70e899ef694fde19c0100109a92636b316e5bc5020086d7c7809c9a4639`
ran direct warm-up and one engineering session. The worker's harness watchdog
interrupted inference, triggering the frozen pair-wide quarantine rule.
Hierarchical execution and independent grading were not dispatched.

## Completion and correctness

| Measurement | Direct | Hierarchical |
| --- | --- | --- |
| Engineering worker sessions | 1 | 0 |
| Planner requests | 0 | 0 |
| Model-authored source changes | None; all 121 hashes match the start | Not started |
| Completion | Failed; repository exploration only | Blocked by quarantine |
| Frozen public fallback | 7/16 feature cases; upstream gate passes | No candidate |
| Authored tests/documentation gate | Fails: deliverables absent | Not evaluated |
| Sealed correctness | Not evaluated | Not evaluated |
| Regressions | Unchanged source; baseline retained | Not evaluated |
| Hierarchy effect | Not measured | Not measured |

The public selector froze the unmodified baseline before model execution. Its
75 selected upstream tests pass, but nine of sixteen feature cases fail.
That fallback is **not model-delivered work**. Its inventory SHA-256 is
`5d4e3c9e66ae2da5c42bd1d7a58ed6dd0131835f72ddd95ff3fb54282a10e038`.
No challenger was promoted and no rollback comparison completed after the
worker interruption. The scorer's legacy `compiled` ranking flag denotes the
Python upstream-test gate; it does not indicate native compilation.

The retained isolated worker stage and archived source match the initial
inventory exactly. Thus no source regression or partial implementation was
introduced. This is an unsuccessful autonomous attempt, not guided recovery
or partial feature completion. No operator-written feature code or mid-run
implementation guidance was supplied.

Both engineering phases did not close successfully, so the condition for
authoring the 24 independent acceptance cases was not met. **Zero sealed cases
were created**, and no sealed feedback reached a worker. Absent candidates
receive no fabricated zero score.

## Timing, tools and model usage

| Recorded measurement | Value |
| --- | --- |
| Warm execution including termination bookkeeping | 14.860 s |
| Engineering execution including termination bookkeeping | 117.360 s |
| Engineering container cleanup | 0.203 s, passed; no containers remained |
| Worker harness window | 95.766 s, watchdog timeout |
| Wall time from first phase start through engineering close | 132.441 s |
| Worker tool calls | 6 glob, 2 grep, 7 focused inspections; zero reported tool errors |
| Worker public-test calls | 0 |
| Warm usage | 17 input, 2 output; 19 provider-reported total tokens |
| Completed worker usage events | 10 |
| Recorded worker token fields | 19,821 input; 714 output; 0 reasoning |
| Separately recorded worker cache fields | 30,183 read; 0 write |

There are eleven step-start events and ten completed usage events. Usage for
the final interrupted step is unknown, so complete server request/token totals
cannot be claimed. Cache counters are reported separately as recorded by
OpenCode. Timings include orchestration/tool work and are not isolated inference
latency or GPU throughput measurements.

The approved task has a 120-second attempt ceiling; the existing controller
reserves up to twenty seconds for verification and charges readiness/setup to
that attempt. The resulting harness window expired before the outer 180-second
engineering deadline. `agent-process.json` records `timed_out: true`; the outer
work process records `timed_out: false` and exits with code 1 after quarantine
blocks further work. These are different watchdog levels, not conflicting
receipts. No timeout or reservation was extended.

The trace shows repeated first-page focused reads of `_client.py` and
`_utils.py`; the worker remained in inspection until interrupted. This is an
observed exploration bottleneck under the approved limits, not evidence that
the feature is impossible or that another architecture would perform better.

The controller wrote an `attempt-002` bookkeeping record after the first
session failed. Its lease guard rejected execution immediately: elapsed zero,
no second worker claim and no further inference dispatch. The journal records
one session, zero planner requests and pair-wide quarantine. No automatic
replacement campaign or retry worker was launched.

## Preservation and boundaries

Warm-up's container-free policy passed. Work cleanup passed, so the earlier
Docker-query blocker did not recur. The new stopping condition is interrupted
inference; backend cancellation latency remains unmeasured. The shared model
service was not restarted or terminated.

The [outcome receipt](evidence/phase61/httpx-replacement-run/outcome.json),
[agent metrics](evidence/phase61/httpx-replacement-run/direct-agent-metrics.json),
[raw trace](evidence/phase61/httpx-replacement-run/direct-agent.jsonl),
[live trace](evidence/phase61/httpx-replacement-run/direct-agent-live.jsonl),
[MCP records](evidence/phase61/httpx-replacement-run/direct-mcp.jsonl),
[source receipt](evidence/phase61/httpx-replacement-run/direct-source-receipt.json)
and [complete local evidence inventory](evidence/phase61/httpx-replacement-run/evidence-inventory.json)
preserve the attempt, blocked retry bookkeeping, baseline outcomes, authorization,
hashes, timing and usage. The 1,142-file inventory covers the local bundle at
capture time. The original external stage remains retained, with a second copy
at `.aiwork/phase61-cleanup-repair/benchmark/archival/direct-attempt-001-source`.
Archiving did not execute or grade candidate code.

Approved implementation, inputs, permissions, settings, image and resource
limits remain unchanged. Frozen Click, the original quarantined comparison and
`main` are preserved. No remote inference, deployment or merge occurred. There
were no implementation changes requiring another regression run; the same
controller code passed 115 tests before this comparison.

This authorization is closed to further dispatch. Do not resume the unused
reservations, run the hierarchical arm, generate sealed cases or reuse the grant
to start another comparison.
