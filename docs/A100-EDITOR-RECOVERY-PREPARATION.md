# Milestone E: historical grades and fresh A100 preparation

**Historical preparation at `05271bd`.** This digest was subsequently approved
and consumed once. Read the [quarantined execution outcome](A100-EDITOR-TRIAL-RESULT.md).
The preparation details below do not authorize reuse or resume.

**PREPARED_NOT_AUTHORIZED. No model inference or worker dispatch.** Continue from
`321e426`; no controller, harness, feature asset or target implementation changed.
The two consumed/quarantined ItsDangerous trials remain immutable.

## Historical proposals: offline evaluation only

Each distinct replay source was copied into a separate original-input snapshot
and evaluated in the existing network-disabled, offline Docker image. The frozen
12 public cases and complete 297-test upstream suite were unchanged. Python AST
syntax validation is reported separately from behavior; binary compilation does
not apply. Every receipt and evaluated source is preserved
[outside worker inputs](evidence/a100-editor-preparation/historical-evaluation/).

| Source | Historical proposal calls | Syntax | Public | Upstream | Regressions / gains |
| --- | --- | --- | --- | --- | --- |
| `1b24237f474e144a2221358387d940dc0a0d2ce2553a17abd8aef776cab32871` | 8, 9, 12, 17, 22, 32 | PASS | **3/12** | **297/297** | 0 / 0 |
| `31fd0f1238a845df93105ee74f43f3ca037f57411173d8f2f5d15712a570f139` | 14, 15, 20, 27, 29 | PASS | **3/12** | **297/297** | 0 / 0 |

Both retain exactly the baseline's three public passes. All nine remaining public
cases fail with `TypeError`; API annotation checks also fail, and neither proposal
authors tests. Successful application and syntax parsing did not produce the
feature. These are **historical model proposals evaluated offline**, not autonomous
deliverables, independently sealed results, promoted checkpoints or future starting
solutions. The repeated proposals are only two distinct evaluated sources.

## Editor and infrastructure verification

- **207/207 regression tests pass**, zero skips, **155.271 seconds**. This includes
  deterministic replay, exact source/hash/location checks, permissions, syntax,
  checkpoint rollback, cancellation, two forced compactions and pinned-template
  verification using existing offline images.
- Installed OpenCode/MCP inert conformance again completes inspection, LF/CRLF
  editing, three ambiguous failures, fresh inspection, a grounded location edit
  and an approved public test. A separate fixture stops forwarding after the
  fourth equivalent failure, records clean resource exhaustion and passes cleanup.
- The fresh task's actual MCP catalog advertises unique anchors, insertion modes,
  current SHA-256, focus-issued `evidence_key`, inclusive inspected line bounds,
  stale-location rejection and different-strategy recovery. The optional location
  schema and recovery instructions were checked. Provider-facing catalog admission
  remains required before inference; the installed inert tests verify it.
- Both consumed digests and the unapproved example grant are rejected against the
  new bundle. There is no execution marker, worker state, real approval, frozen
  candidate or private evaluation material in it.

Receipts: [verification](evidence/a100-editor-preparation/verification.json),
[catalog](evidence/a100-editor-preparation/catalog/catalog.json),
[inert traces](evidence/a100-editor-preparation/inert-conformance/) and
[preparation checks](evidence/a100-editor-preparation/preparation-verification.json).
The editor is ready for a separately approved live trial. Model adoption of the
revised contract and autonomous feature completion remain **UNTESTED**.

## Fresh approval review

Bundle: `.aiwork/a100-editor-recovery/itsdangerous-trial`.

Approval digest:

`de9bdcda4c591eaf1b2a93927477b3159e4da9f1b480c844ed93abacf46a07e3`

Authorize exactly `["a100-existing"]` only through a separate explicit approval.
The [complete manifest](evidence/a100-editor-preparation/prepared/manifest.json)
binds all controller implementations, unchanged task assets, OpenCode binary,
source inventories, model profile, verifier image and resource protocol. Relative
to the last consumed manifest, only `mcp.py` and `source_edit.py` implementation
hashes changed; they are the verified correction from `321e426`.

The 42 pristine source files and 45 worker-input files match the original inventories
exactly. The new baseline independently reproduces **3/12 public**, passing syntax
and **297/297 upstream**. Neither historical candidate nor its evaluation records,
traces, attempted solutions or conclusions occur in the worker input. All results
in this report stay outside the isolated task workspace; no mid-run guidance is
authorized.

Unchanged reviewed configuration:

- Existing OpenCode and existing A100 Qwen3.6 35B-A3B Q6_K model; 65,536 context,
  4,096 output tokens, temperature 0, seed 1729, reasoning disabled.
- One autonomous worker, one attempt with a 720-second ceiling, no planner,
  retries, fallback or implementation guidance.
- 96 MCP operations, eight reserved edits/eight reserved public tests;
  64 model requests and four compactions. Phase reservations: **20/900/120 seconds**.
- Only `src/itsdangerous/timed.py`, `docs/timed.rst` and
  `tests/test_itsdangerous/test_timedelta_max_age.py` are writable.
- Existing immutable offline verifier:
  `sha256:00d3d7e3d1e32064b5bf313cc788fb91945c0c5fa000856513f490f2c8087645`.
- Frozen specification, 12 public cases, all upstream tests, authored tests,
  API annotations/docs, source-scope checks and failure/cleanup policy unchanged.
- Freeze only after permitted clean engineering closure. Independently author
  24 fresh sealed cases afterwards; no sealed feedback to workers or selection.

A fresh read-only inspection found the same server-reported model, template,
build identity and one idle **131,072-token slot**. No new weight hash is claimed.
It made zero generation requests; the test-owned SSH forward closed. Remote
services, models and storage were untouched. Readiness is a snapshot: identity,
slots, hashes and dependencies must pass again before authorized execution, with
drift causing a stop. No context or budget incompatibility was found.

## Operator commands and stop point

Validation only; no authorization, worker or model dispatch:

```powershell
.\.venv\Scripts\python.exe examples/milestone-e-a100/trial.py validate .aiwork/a100-editor-recovery/itsdangerous-trial
```

For a separately authorized operator, the existing `trial.py run` and `grade`
commands accept this bundle and an exact explicit approval JSON; the example grant
deliberately has `operator_approved:false`. Never use either consumed grant or
resume a quarantined bundle. The existing scripts require no Codex service.

All **2,766 historical indexed entries** (overlapping inventories) and main are
verified unchanged. No new models, downloads,
campaign, REA work, harness comparison, routing changes or next-phase work ran.
Stop at **PREPARED_NOT_AUTHORIZED** pending operator review of this digest.
