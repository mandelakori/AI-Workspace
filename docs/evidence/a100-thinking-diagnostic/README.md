# A100 paired diagnostic preparation evidence

- `template-probe/` contains the exact active template, the initial and tool
  continuation bodies for each switch, the server-rendered prompts and the
  no-inference receipt. `offline-template-receipt.json` records the offline
  replay. `service-flags.json` records selected visible command-line settings.
- `inert/` contains captured installed OpenCode request/response and tool
  receipts from scripted local providers. Their usage counters are synthetic.
  The two normalized summaries are in `inert-summary.json`.
- `prepared/` contains the two immutable manifests, exclusion hashes, common
  public worker files and Docker baseline receipts. The locally staged reference
  ELF is pinned by the manifest, with its original archive under `.aiwork`.
- `preparation-checks.json` records paired equality and negative approval,
  source-drift and grading guards. `preservation.json` confirms the consumed
  ledger evidence and `main` were retained.
- `regressions-final.log` records all 235 passing tests. The pre-change suite
  and its isolated Git recheck retain the original timing and results.

Both arms are PREPARED_NOT_AUTHORIZED. The exact execution and measurement
protocol is in the [review](../../A100-THINKING-DIAGNOSTIC.md). No real model
tokens or new private cases were created in preparation.
