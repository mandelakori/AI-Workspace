# Consumed thinking-mode comparison evidence

- `preflight/` and `postflight.json` record frozen hashes, scope, live
  non-inference template validation, and endpoint and slot identity.
- Each arm has `trial/`, `job/`, `attempt/`, `frozen/` and `grade/` receipts.
  These contain the consumed grant, state and cleanup, raw provider files,
  scoped tool traces, the model-authored source and redacted verdicts.
- `live-metrics.json` joins provider tool-call IDs to OpenCode and MCP evidence
  and distinguishes reasoning emission from an unreported token counter.
  `audit_live.py` reconstructs it from the retained local traces without inference.
- `comparison.json` records the shared sealed-suite hash and verified outcomes.
  The private suite and raw per-case streams are kept under the local pair,
  covered by `local-pair-inventory.json`. Runtime homes and private logs remain
  local. `evidence-hashes.json` binds the committed archive.

Both grants have been consumed. The comparison report records the limits of
this single pair. [Full result](../../A100-THINKING-DIAGNOSTIC-RESULT.md)
