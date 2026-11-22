# Milestone E: deterministic source-editing recovery

This corrects the editor failures preserved at `bfa28c0`. It does not rerun the
ItsDangerous feature trial or establish autonomous feature correctness. No model
inference, remote operations, dependency downloads or new trial preparation ran.
The original A–E roadmap and OpenCode harness remain unchanged.

## Diagnosis and correction

The 37 saved MCP argument objects retain the actual model proposals. Their source
hash is `4fab550338d97c65ba6ea124f0ac021fb1e4b50299a725d7d66f9924957f7fcf`:
228 uniform CRLF endings. Eleven multiline LF anchors match uniquely after CRLF
adaptation. Twenty-four short anchors are ambiguous (23 match five sites, one
matches seven); one anchor is nonexistent and one is empty. The previous trial
accepted none. Transport escaping and stale hashes were not the cause.

`source_edit.py` still requires the exact current SHA-256. An exact match is tried
first; only an otherwise unsuccessful uniform LF/CRLF anchor is adapted, then
uniqueness is checked again. New text uses the source's uniform newline style.
Only the verified replacement/insertion span changes; the file is never globally
normalized. Mixed endings, bare CR and anchors splitting CRLF pairs are rejected.
Adapted anchors/new text remain subject to the 1200/3000-byte limits. Files without
newlines retain explicitly supplied uniform new-text endings. Python syntax,
write roots, atomic commit, race/stale checks and cancellation deadlines remain.

The optional edit `location` is `{evidence_key, line, end_line?}`. Lines are
one-based and inclusive; omitted `end_line` means the same line. `focus` issues
the key and retains the exact excerpt outside the worker workspace. The editor
verifies its key, file path, full current hash and exact inspected bytes. The
anchor must occur exactly once inside those explicitly selected inspected lines.
Absent, changed, stale, unrelated or out-of-window evidence is rejected; multiple
matches within the location still fail. Existing unique-anchor edits remain
supported. No first-match selection, fuzzy matching or full-file-write tool was
introduced. Before/after still keep `old` and insert only `new`.

MCP now records equivalent failures durably per source hash, expected hash, path,
anchor, locator and error classification. For missing/ambiguous anchors, changing
`new`, insertion mode or LF/CRLF spelling cannot reset the counter. The third
failure requires a different verifiable anchor/location; the fourth exhausts the
session. Fresh inspection can support recovery but cannot refund repetitions.
The failure ledger survives MCP reconnects and context compaction. Managed
execution latches clean resource exhaustion, blocking the next provider forward.
Every admitted failed edit still consumes an editing operation; original failure
codes, fingerprints, counts, diagnostics and timing remain in MCP receipts.

## Replay and conformance

[Replay receipts](evidence/editor-recovery/replay/replay.json) start every proposal
from a separate reset of the exact approved source. Calls 8, 9, 12, 14, 15, 17, 20,
22, 27, 29 and 32 apply: **11 newline-compatible applications**, representing
**six distinct argument objects and two resulting source hashes**. These are not
11 independent repairs or feature successes. All 24 ambiguous proposals remain
rejected; the nonexistent and empty anchors remain rejected. All 37 receipts
verify unchanged bytes outside the authorized span, or an unchanged whole file
on rejection. Applied proposals pass the editor's syntax gate; behavior is
**NOT EVALUATED**. Their retained sources are replay evidence, not approved
checkpoints or starting solutions for later workers.

Installed OpenCode 2.0.27 and real scoped MCP run against a scripted inert provider
in [two conformance fixtures](evidence/editor-recovery/harness/). The first makes
a unique LF-on-CRLF edit, receives three ambiguous rejections, reinspects, applies
an inspected-location edit to only the second duplicate and passes an approved
public Python check. Allocation: 3 inspections, 5 edits (2 applied, 3 rejected),
1 public test; 10 inert requests. The second makes four equivalent rejected edits:
1 inspection +4 edits, five inert requests, then forwarding stops before request
six. Its normalized status is `resource_exhausted`, raw harness exit 1, normalized
exit 0; no timeout, provider failure or quarantine. Both report successful cleanup
and provider gating. Actual model requests/tokens: **zero**. This is scripted
fixture conformance, not autonomous engineering or unfamiliar-repository delivery.

## Verification and preservation

Final regressions: **207/207 passed, zero skips, 144.596 seconds**. Exact receipts
are recorded in [verification.json](evidence/editor-recovery/verification.json),
with complete baseline/focused/full logs. Baseline: 190/190, no skips, direct
fixture VERIFIED. Focused recovery regressions: 15/15; both installed inert
conformance fixtures pass (4.062 and 3.110 seconds of harness execution).
The new deterministic tests cover EOL adaptation in both directions, all edit
modes, EOF, Unicode byte offsets, ambiguity, mixed endings, size limits, CRLF
boundaries, stale/unissued/tampered evidence, syntax rejection, durable recovery
and exact tool accounting. Existing suite covers permissions, atomic races,
checkpoint rollback, cancellation, compaction and installed harness boundaries.

[Preservation receipts](evidence/editor-recovery/preservation.json) verify 2,675
historical indexed entries (overlapping inventories), including both quarantined
trial bundles, their consumed authorizations, frozen Click, prior HTTPX evidence
and the unauthorized Pi comparison. Main remains `cf50e89`. No historical artifact
has changed in the final tree. Both consumed ItsDangerous grants remain unusable.

## Reproduce and continue

From the repository root in PowerShell, using existing installed dependencies:

```powershell
.\.venv\Scripts\python.exe scripts/replay_source_edits.py --output .aiwork/editor-replay-new
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_editor_recovery.py -v
$env:AIWORK_TEST_OPENCODE_BOUNDARY='1'
$env:AIWORK_TEST_PI_BOUNDARY='1'
$env:AIWORK_TEST_DOCKER_IMAGE='aiwork-engineering:phase3'
$env:AIWORK_TEST_QWEN_TEMPLATE_IMAGE='sha256:fc1854e6885153904be89d67c701cd012fd68e57523566405d184ce2a4fe05e1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Replay output must be a fresh directory. No model service is required. The
deterministic acceptance checks qualify the editor for review of a separately
authorized engineering trial. Model adoption of the locator/recovery contract,
feature correctness and live autonomous completion remain **UNTESTED**. No fresh
live bundle or approval digest was prepared; old implementation hashes are stale
and old grants are consumed. Stop here pending separate review.
