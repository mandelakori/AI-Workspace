# Direct-only HTTPX editing pilot result

**QUARANTINED — no applied source edits, no worker public-test execution and no
independently verified new feature functionality.** This is the single pilot
authorized for digest
`0281aec9e0da0fc5d20ae980cabcabda18236ad468881fa7d478311d478d6230`.
It used one local worker session and one attempt, with zero planner requests,
retries or hierarchical execution. The worker's watchdog triggered the existing
inference-client quarantine rule. Cleanup passed and all dispatch stopped.

## Requested outcome measurements

| Question | Recorded result |
| --- | --- |
| Were source edits applied? | **No.** One hash-grounded edit was requested and rejected as `anchor_mismatch`. |
| Did the agent execute public tests? | **No.** No public-check tool call occurred. |
| Public correctness versus 7/16 baseline | No improvement. The frozen artifact remains the **unchanged baseline, 7/16**, not model-delivered work. |
| Upstream regressions | Initial selector: **75 selected upstream tests passed**. All 121 source-inventory entries remain identical; no post-worker upstream rerun was permitted after quarantine. |
| Harness exit | **1**, `timed_out: true`, `truncated: false`; 125.156-second subprocess. |
| Provider-stream errors | No explicit provider error event was observed in the saved trace. The final generation was interrupted; this does not prove the earlier stream defect is resolved. |
| Independent feature verification | **Not run.** Quarantine blocks the 40-second grading phase; zero sealed cases were authored. |

The fallback was frozen before worker execution. Its inventory SHA-256 is
`5d4e3c9e66ae2da5c42bd1d7a58ed6dd0131835f72ddd95ff3fb54282a10e038`.
No model candidate was selected or promoted. The source and fallback hashes were
checked again during archival; these are integrity checks, not new behavioral
grading. Absent sealed results are not reported as 0/24. The scorer's legacy
`compiled` flag denotes the Python upstream regression gate, not C compilation.

## Complete operation accounting

The agent reached `URLPattern.matches` and `URLPattern.__init__` using qualified
symbols, also inspecting `_urls.py`. It nevertheless spent most of its tool
allowance on source exploration. The complete sequence is preserved in the
[structured tool sequence](evidence/phase61/httpx-editing-pilot/tool-sequence.json)
and [raw trace](evidence/phase61/httpx-editing-pilot/agent.jsonl).

- The first unprefixed `focus` call failed because that tool name was unavailable.
- Sixteen MCP operations were admitted: **15 focus calls and one edit**. These
  include two unmatched literal queries and two suppressed duplicate excerpts.
- The sole edit was operation **14**. Its expected SHA-256 matched the current
  file, but its literal old anchor occurred zero times. The editor returned an
  error with a source-region hint and did not change any bytes.
- The agent followed that hint with operation 15, inspecting line 178. It used
  the final operation to inspect `_urls.py`, without submitting another edit.
- Three subsequent MCP inspection requests were rejected by the call limit.
  They did not execute additional source operations. One native glob and four
  native grep calls were separate from MCP quota and remained under the harness
  deadline. Seven tool-error events are recorded in total.

The persistent counter is exactly **16**. Model requests beyond the limit were
blocked, not silently admitted. Native mutation tools remained unavailable;
the rejected edit did not bypass the hash or anchor checks. There were no other
attempt records or retry-worker dispatches.

The edit guard preserved source integrity, but the worker did not recover into
an applied correction or testing before exhausting resources. This is an
unsuccessful autonomous engineering attempt, with no operator implementation
guidance or source correction. It is not guided recovery or feature completion.
No conclusion about hierarchical performance is possible from a direct-only run.

## Timing and inference usage

| Timing receipt | Seconds |
| --- | --- |
| Warm execution including termination bookkeeping | 13.891 |
| Engineering execution including termination bookkeeping | 148.812 |
| Engineering owned-container cleanup | 0.219; passed, no containers remained |
| Harness subprocess | 125.156; watchdog timeout |
| Wall time from warm start through engineering close | 162.928 |

The 150-second attempt ceiling left 146.875 seconds at harness setup. The
controller retained its twenty-second verification reserve and recorded a
126.875-second wrapper allowance, which also charges isolated staging/catalog
setup. The subprocess expired within that allowance. The outer engineering
reservation of 180 seconds had not expired: its process reports `timed_out:
false` and code 1 because quarantine blocked subsequent selection. The inner
harness reports `timed_out: true`. These are distinct watchdog levels; no limit
was extended. Unused time cannot be refunded, transferred or resumed.

Warm-up returned `READY`, reporting **17 input / 2 output / 19 total tokens**.
Twenty-five completed worker usage events report **29,922 input / 1,721 output /
0 reasoning** tokens. Cache counters separately report **92,295 read / 0 write**.
There are twenty-six step-start events, so the final step has no completed
usage receipt. Complete provider totals, including any auxiliary requests and
unfinished generation, are unknown. These timings include orchestration and
tools and are not isolated GPU throughput measurements. Backend cancellation
latency remains unmeasured; the shared inference service was not interrupted.

## Preservation and closure

The [outcome](evidence/phase61/httpx-editing-pilot/outcome.json),
[failed edit](evidence/phase61/httpx-editing-pilot/failed-edit.json),
[MCP records](evidence/phase61/httpx-editing-pilot/mcp.jsonl),
[live trace](evidence/phase61/httpx-editing-pilot/agent-live.jsonl),
[usage](evidence/phase61/httpx-editing-pilot/agent-metrics.json),
[frozen baseline](evidence/phase61/httpx-editing-pilot/frozen-fallback.json),
[harness allowance](evidence/phase61/httpx-editing-pilot/harness-budget.json),
[source receipt](evidence/phase61/httpx-editing-pilot/source-receipt.json), and
[evidence inventory](evidence/phase61/httpx-editing-pilot/evidence-inventory.json)
preserve the authorization, tool failures, source hashes and timing receipts.
The retained isolated source was copied to
`.aiwork/phase61-editing/httpx-pilot/archival/direct-attempt-001-source`.
Archiving did not execute, repair or grade it.

The approved manifest, implementation, model settings, verification image, four
write paths and 20/180/40 reservations remain unchanged. No extra tests were run
after quarantine; the original approved controller had passed 132 regressions.
All previous trial evidence and quarantine journals, frozen Click and `main`
remain unchanged. No hierarchical execution, additional campaign, remote
inference, service restart, deployment or merge occurred.

This authorization is closed. Do not reuse the grant, retry/resume this arm or
create sealed inputs for this quarantined pilot.
