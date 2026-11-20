# Phase 6.1 execution recovery

**VERIFIED:** bounded navigation, objective separation, 120 regression tests and
one autonomous inspect/edit/public-test fixture. **UNTESTED:** completion of an
unfamiliar repository feature with these changes. Neither quarantined HTTPX
trial was resumed, modified or graded.

## What the HTTPX trace establishes

Seven focused reads included **three identical-window repeats** with unchanged
source hashes. The client reads did advance to lines 61 and 121; the prior
result's shorthand about repeated first pages should not be interpreted as all
seven reads starting at line one. `_utils.py` was opened at line one three times.
The responses returned the same imports/helpers and `next_line=61`, rather
than the later `URLPattern` implementation. No source edit or worker public-test
call occurred before the unfinished eleventh generation step was interrupted.

Three concrete interface problems contributed to unproductive exploration:

- Exact symbol selection existed, but the inspector provided no discovery list.
  The model needed to guess a qualified name or keep paging.
- Reproducing the historical 1,800-character index at `722414c` yields only
  `tests/models/test_url.py`, `tests/client/test_async_client.py` and
  `tests/client/test_headers.py`. Both authorized implementation files were
  absent. Files over 64 KiB were not parsed for Python metadata, and scope
  relevance could lose to keyword-heavy test names.
- The active implementation objective included the frozen specification's
  operator-only statement, "Preparation only. No model campaign is authorized
  by this file." That contradicts an instruction to implement a feature.

The system accepted duplicate reads and replayed their contents. The trace
supports these observed causes of wasted context; it cannot establish the
model's internal motives or prove that context compaction caused the repeats.

## Intentional limits and elapsed time

The HTTPX engineering reservation is 180 seconds for baseline selection,
planning, workers, public verification, integration and final selection. A
worker attempt separately has a 120-second ceiling. Baseline checks, admission
and staging consume that attempt, and the controller intentionally reserves up
to 20 seconds for verification. That left a 95.766-second harness window.
The historical launch-time split was not recorded precisely; it is incorrect
to describe the entire difference as wasted inference time.

The initial public selector spent 10.844 seconds in verification. The attempt's
baseline check took 1.406 seconds. These checks serve distinct selection and
diagnostic roles; neither is model exploration. The harness watchdog interrupted
inference, quarantine blocked further dispatch, and the outer phase closed at
117.360 seconds. Its unused 62.640 seconds could not be transferred or resumed.
The 40-second independent grading allocation was never used.

The actual waste demonstrated by the trace is repeated unchanged excerpts and
continued broad exploration without editing or testing. The limits themselves
were enforced as designed. Their values are unchanged. New `harness-budget.json`
receipts record the remaining attempt time, verification reserve, launch
allowance and outer phase deadline for future diagnosis.

## Changes and regression evidence

`focus` now returns bounded qualified Python definitions, including methods and
line ranges. A `query` selects matching definitions or a literal text occurrence;
`symbol=Class.method` and line paging remain available. Other text files support
literal queries without executing source. Files stay capped at 256 KiB,
excerpts at 60 lines/3,000 UTF-8 bytes, and the outline at 12 entries/1,200 bytes.

Unchanged identical excerpts are suppressed across MCP reconnects. Responses
retain symbol choices and navigation hints. Changed source hashes allow fresh
reads. Duplicate requests still consume the tool budget. All engineering MCP
sessions now persist their existing 16-call allowance across reconnects; this
does not claim to cap native harness tools at sixteen calls. The repository
index prioritizes approved writable source and parses Python metadata up to the
same 256 KiB limit. Historical replay places both implementation files first
and suppresses all three duplicate windows.

The active objective is persisted in harness instructions and returned with
inspection, diff and public-check responses. Future HTTPX manifests separately
record `implementation_objective` and `operator_preparation_notes`. The worker
receives the original requirement paragraphs verbatim, rather than review or
authorization instructions. The original `FEATURE.md` and its hash are unchanged;
the deterministic controller still owns authorization and permissions.

All **120 regressions pass**, zero skips, in **68.088 seconds**, including local
offline Docker and installed OpenCode with an inert provider. New cases cover
large-file symbol discovery, relevant-file ranking, bounded queries, duplicate
suppression, source changes, reconnect budgets, objective persistence, public
test execution after an edit and requirement/review separation. An initial
targeted test failed because its newly written fixture used Windows CRLF while
the assertion expected LF; the test now explicitly writes LF. Runtime source
bytes remain preserved.

## Single authorized fixture smoke

One existing-local-model worker used a fresh duration-conversion fixture with
a definition after eighty comment lines. The initial source passed 1/4 public
cases. The model authored one edit implementing the stated public interface;
neither an implementation nor a solution patch was provided to it.

| Observation | Result |
| --- | --- |
| Worker sessions / retries | 1 / 0 |
| Work deadline | 120 seconds, unchanged during execution |
| Actual work process | 31.625 seconds |
| Harness time | 28.578 seconds |
| Tool journey | denied native read → focused `Duration` symbol → edit → public check |
| Duplicate excerpt requests | 0 |
| Public outcome | 1/4 baseline → 4/4 after model correction |
| Controller verification | same four public cases rerun successfully in fresh verification workspace |
| Source scope | only `duration.py` changed; tests stayed identical |
| Reported token fields | 6,687 input / 298 output / 0 reasoning |
| Mid-run guidance / operator source correction | none / none |

The model initially was not resident; lazy loading was included in the harness
window. There was no neutral inference warm-up. The existing process/container
guard bounded the smoke, cleanup passed and no additional session was launched.
The produced patch SHA-256 is
`34de6eb40b8aef872bf765ed311c96c96e0fbc67a11cff271af0a1893e6cbc92`.

One denied native-read call remains a usability defect: the harness still
advertises a tool that policy denies, though this worker recovered immediately.
The smoke demonstrates the inspect–edit–verify path on a small self-authored
fixture. It does not establish HTTPX completion, unfamiliar-repository autonomy,
multi-round debugging or a matched speed improvement over the larger HTTPX task.
The duplicate guard was exercised by tests/replay, not by a repeated live read.

See the [audit](evidence/phase61/recovery/trace-audit.json),
[regression log](evidence/phase61/recovery/regressions.log),
[smoke receipt](evidence/phase61/recovery/receipt.json),
[model trace](evidence/phase61/recovery/smoke-agent.jsonl),
[public tool records](evidence/phase61/recovery/smoke-mcp.jsonl),
[controller rerun](evidence/phase61/recovery/smoke-controller-check.json) and
[model-authored patch](evidence/phase61/recovery/smoke-proposed.patch).
`examples/phase61/recovery_smoke.py` reproduces intake and the bounded run in a
new root; it refuses an existing root. Repeating inference needs a new operator
instruction. The completed smoke and retained stages remain under
`.aiwork/phase61-recovery/smoke`.

## Fresh HTTPX review, no execution

The [new manifest](evidence/phase61/recovery/manifest.json) remains
**PREPARED_NOT_AUTHORIZED** at `.aiwork/phase61-recovery/httpx-prepared`:

```text
2a12502209bd9ada3a5082e3ab489bb6423a41a6cdf5144fbec8de05874fe3b9
```

Both old grants are rejected for it. Frozen input inventories, specification,
public cases, four writable paths, model/profile, verification image and
20/180/40-second reservations are unchanged. The approved execution implementation
and worker objective have changed and therefore require explicit approval of
this new digest for exactly `["direct", "hierarchical"]`. No grant, trial state
or sealed inputs have been created for it. No HTTPX model request was made.

After such approval only, write a new grant with `approval_digest` equal to the
digest above, `authorize` equal to `["direct", "hierarchical"]`, and
`operator_approved: true`. Use the existing `aiwork.httpx_benchmark run` commands
with this fresh bundle and grant, direct first. Stop on quarantine. New sealed
inputs may be authored only after the approved candidates are frozen and both
engineering phases close as required. Do not reuse either previous trial.

Both original quarantine journals, raw artifact hashes and authorizations were
checked unchanged. Frozen Click and `main` remain unchanged. No remote service,
model weight, cloud resource, deployment or merge was changed.
