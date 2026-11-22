# Approved A100 duration-expiry trial: quarantined

Digest 0534cc79... ran once. First inference, compaction and resumed requests
worked; zero edits were accepted. The harness deadline interrupted request 51.
No frozen candidate or private cases exist, and grading was refused.

`outcome-0534.json` separates the syntax-only worker check, controller 3/12
public baseline, historical 297-pass upstream baseline, and unperformed sealed
evaluation. Reported usage covers 50 complete calls, not the interrupted final
call. `attempt/` contains all raw incoming/forwarded requests, responses, model
edit arguments, agent/MCP traces and timing/resource receipts.

`anchor-analysis-0534.json` only counts exact matches and newline-reencoded
representations; it applies no edit. Eleven multiline LF anchors match unique
CRLF source locations after conversion; 24 other anchors are ambiguous. Parsed
model tool arguments equal the actual MCP arguments for all 37 proposals.
The source read tool preserved CRLF, and expected source hashes were current.

`post-run-0534.json` and `retained-workspace-check.json` independently confirm
closed owned PIDs/listener, unchanged source, and absence of freeze/sealed state.
Read-only postflight confirms existing A100 health/idle state; it does not measure
backend cancellation latency. No service/model/configuration changes were made.

Runtime homes/private server logs and retained stages remain at recorded owned
local paths. Local evidence is indexed without publishing private runtime homes,
credentials or model weights. Historical data is checked in `preservation.json`.
