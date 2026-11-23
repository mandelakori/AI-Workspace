# Consumed A100 ledger trial evidence

- `preflight/` and `postflight/` record the frozen scope, scoped MCP catalog,
  pinned offline verifier, explicit resource limits, and read-only A100 identity
  and idle-slot checks. `reference-public.json` is reference behavior only.
- `trial/` records the exact approval, consumed manifest, phase ledger and failed
  closure. `job/` contains the controller intake, missing-source baseline and
  unchanged-proposal result.
- `attempt/` preserves all captured HTTP requests and response streams, tool
  and harness receipts, navigation excerpts and the empty diff. The seventh
  response ends at the configured output ceiling.
- `outcome.json` and `provider-audit.json` summarize checked artifacts, accounting
  and failure classifications. `local-evidence-inventory.json` covers the full
  local bundle including runtime material kept out of Git. `evidence-hashes.json`
  verifies each committed evidence file.

No candidate source or private case file exists. The grant is consumed and the
engineering phase failed. See [the result](../../NATIVE-LEDGER-A100-RESULT.md).
