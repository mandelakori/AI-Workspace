# Source-grounded editing recovery

**VERIFIED:** exact, scoped source editing and a model-authored correction after
an intentionally rejected request. **BLOCKED:** a clean provider/harness exit;
the fixture exposed a separate invalid-stream response. **UNTESTED:** HTTPX
feature completion using this editor. No quarantined trial was resumed.

## Exact cause of the rejected HTTPX edits

Both historical `oldString` values first differ from the saved source at file
line **169**. Each places the closing `)` of a multiline `raise ValueError(...)`
immediately after its final f-string. The source instead has a newline followed
by twelve spaces before that parenthesis. Both literal anchors occur zero times.
In diagnostic copies only, restoring precisely that missing newline/indent makes
each complete anchor occur once. No source file was changed during this analysis.

This was a source transcription mismatch, not a demonstrated logic or compiler
failure. The [audit](evidence/phase61/source-editing/audit.json) records hashes,
the mismatch and the diagnostic proof. Neither rejected feature proposal nor a
corrected version is provided to future workers. Their original evidence and
all quarantine journals remain unchanged.

## Editing contract and integrity

Engineering OpenCode workers now mutate source through the scoped MCP `edit`
operation. Native mutation permissions are removed. The installed-harness probe
also confirms native `edit`/`write`/`patch` schemas are absent from its first
provider request. Restricted-mode harness permissions are unchanged.

An edit supplies `path`, `expected_sha256`, `old`, `new` and `mode`:

- `replace`, `before` and `after` require the current raw-byte SHA-256 and one
  unique literal anchor. Overlapping occurrences count as ambiguity. The old
  anchor is capped at 1,200 UTF-8 bytes; new text at 3,000 bytes. Whitespace and
  line endings are exact. No fuzzy matching or automatic indentation repair occurs.
- `create` requires `expected_sha256: "absent"` and empty `old`. Creation never
  overwrites a competing file. Parent directories must already exist.
- Source/result size remains bounded to 256 KiB. Python results must parse;
  parsing does not execute source or establish behavioral correctness.
- Existing file mode is retained. A session edit lock, bounded reads, hash/content
  recheck immediately before commit and atomic file publication protect ordinary
  cooperating writers. Windows creation uses no-overwrite rename; POSIX creation
  uses no-overwrite link. Replacement uses an atomic rename of verified bytes.
  These checks are not an OS sandbox against a hostile process running as the
  same host account; native worker mutations are denied to keep framework writes
  under the shared edit lock.
- Existing path, link, excluded-file and write-root checks apply before reads or
  writes. Editing never runs shell commands or changes permissions outside the
  task workspace. Stop/deadline checks occur before preparation and commit.

Failures return a reason such as stale hash, missing/ambiguous anchor, invalid
syntax or no change. Diagnostics include the current hash and a bounded source
inspection hint where applicable. A rejection with a known current hash permits
one reinspection of that same file/version despite duplicate suppression.
Rejected requests still consume the sixteen-call engineering MCP budget.
Before/after hashes and the complete edit arguments are recorded. Public-test
success remains separate from edit or inspection success.

## Tool-availability investigation

The saved harness log shows MCP connecting after initial agent/model setup.
An installed OpenCode 2.0.27 probe against an inert provider reproduces the gap:
the first tool-bearing request offers only `glob` and `grep`; scoped MCP tools
first appear on the sixth such request in the final probe. Thus a hard-coded
instruction to call `checks_focus` could request a tool not yet advertised.

Initial worker instructions now say to use only the actual tool catalog, rather
than guessing names. A bounded initialization/list preflight checks the scoped
server and its exact expected catalog before inference and charges its time to
the existing attempt allowance. It does **not** synchronize the harness's separate
asynchronous MCP registration. The inert probe calls tools only when advertised
and completes scope rejection, source inspection, stale-hash rejection, recovery,
editing and public testing. The upstream registration gap remains a limitation;
no upstream harness change or service restart was made.

## Regression and autonomous fixture results

All **132 regression tests pass**, zero skips, in **81.678 seconds**, including
offline Docker and installed OpenCode with an inert provider. Cases cover
multiline anchors, indentation, CRLF preservation, stale hashes, overlapping
ambiguity, no-op rejection, syntax errors, deadlines, protected paths, concurrent
changes, competing creators, exact single-arm approval scope and persistent quotas.

Failed development checks are retained. Windows sandbox hard-link creation failed
initially; creation now uses Windows no-overwrite rename. The initial full suite
observed Docker auto-removal between enumeration and inspection. Production
correctly failed closed. The live test now requires retained quarantine and an
empty owned-container set for that specific inspection failure; other failures
remain test failures. No production cleanup error is suppressed or retried.

One explicitly authorized **self-authored** fixture used the existing local model,
one worker, no retry and a 150-second outer work deadline. Its initial contract
requested a deliberately stale first edit; no implementation solution was supplied.

| Recorded tool sequence | Outcome |
| --- | --- |
| Edit with the requested all-zero fingerprint but empty old/new text | Rejected as `invalid_anchor`; no source change |
| Inspect `distance.py` | Returned exact source and current SHA-256 |
| Short replacement with that SHA-256 and exact multiline old text | Applied; only `distance.py` changed |
| Approved public test command | 4/4 passed |
| Controller rerun in fresh verification workspace | Same four public cases passed |

The fixture started at 1/4 public cases. Model-authored code reached 4/4 in
**55.641 seconds** of work, including **51.281 harness seconds** and cold model
loading. Recorded token fields are **4,902 input / 597 output / 0 reasoning**,
with **11,126 cache-read / 0 cache-write** tokens recorded separately. No
mid-run guidance, operator source correction, extra worker or timeout occurred.
Cleanup passed. Patch SHA-256:
`1dfc45c161aa01e668023aa3ad5359ac5c820a0f26438ef9625f5f6499625d2e`.

Two qualifications are preserved explicitly:

1. The malformed empty anchor was rejected before the stale-hash branch. The
   live run establishes recovery from validation rejection, not live stale-hash
   recovery. Stale-hash recovery passed deterministic and inert-harness tests.
2. The trace contains `provider.invalid-output: OpenAI Chat stream ended without
   finish_reason` (HTTP 200), and the harness exited **1**, without timeout or
   truncation. The existing controller independently verified the resulting source
   despite that transport error; its receipt retains `agent_exit_detail`.
   Complete provider usage, including the invalid stream and auxiliary requests,
   is unknown. The provider issue was not repaired or probed with another model run.

This prompted fault-injection fixture demonstrates actual inspection, guarded
editing, testing and recovery. It does not establish unfamiliar-repository
completion, an unexpected-fault recovery rate or flawless inference/harness
operation. The [receipt](evidence/phase61/source-editing/receipt.json),
[raw trace](evidence/phase61/source-editing/smoke-agent.jsonl),
[tool sequence](evidence/phase61/source-editing/smoke-mcp.jsonl),
[controller check](evidence/phase61/source-editing/smoke-controller-check.json),
[patch](evidence/phase61/source-editing/smoke-proposed.patch),
[catalog probe](evidence/phase61/source-editing/catalog-probe.json) and both
[final](evidence/phase61/source-editing/regressions.log) and
[initial](evidence/phase61/source-editing/regressions-initial.log) regression logs
are preserved. Reproduction script: `examples/phase61/editing_smoke.py`, using a
new root and the existing local configuration. Do not repeat inference automatically.

## Single-arm HTTPX pilot awaiting approval

The [fresh manifest](evidence/phase61/source-editing/manifest.json) is
**PREPARED_NOT_AUTHORIZED** at `.aiwork/phase61-editing/httpx-pilot`:

```text
0281aec9e0da0fc5d20ae980cabcabda18236ad468881fa7d478311d478d6230
```

The model/profile, source specification, public cases, frozen starting inventory,
verification image and four writable paths are unchanged. No HTTPX inference,
worker dispatch, sealed-case authoring or pilot grant occurred. All prior grants
are rejected. The known provider error above is part of this review's limitations.

The exact budget proposed for separate operator approval is:

| Limit | Pilot value |
| --- | --- |
| Authorized arm | `direct` only; no hierarchy or comparison claim |
| Warm/preflight | 20 seconds; one neutral request, maximum four output tokens |
| All engineering/public verification/selection | 180 seconds |
| Independent grading | 40 seconds; exactly 24 new sealed cases after freeze |
| Total reserved execution | 240 seconds, no transfers or extensions |
| Worker sessions / attempts / planner requests | 1 / 1 / 0, persisted limits |
| Attempt ceiling | **150 seconds**, up from the previous 120, within the unchanged 180-second outer reservation |
| Verification reserve inside attempt | Up to 20 seconds; harness receives at most 130 seconds minus setup/catalog/staging |
| MCP calls | 16 total, including edits, checks and rejections |
| Model context / output response ceiling | Existing 8,192 / 2,048 tokens; reasoning setting unchanged |
| Cancellation | Existing at-most-ten-second owned cleanup allowance; failures quarantine; no retry/resume |

Only after explicit approval of this digest and exactly `["direct"]`, create a
new grant at `.aiwork/phase61-editing/operator-approval.json` with that digest,
`authorize: ["direct"]` and `operator_approved: true`. Then the reviewed command is:

```powershell
.venv/Scripts/python.exe -m aiwork.httpx_benchmark run .aiwork/phase61-editing/httpx-pilot --arm direct --authorization .aiwork/phase61-editing/operator-approval.json
```

Stop on quarantine. Any independent grading must follow the frozen-candidate
and fresh-private-input rules; no sealed feedback may reach a worker. This report
does not authorize execution. Previous HTTPX trials, authorizations, source hashes,
quarantine states, frozen Click and `main` remain unchanged. No remote inference,
model-weight change, deployment or merge occurred.
