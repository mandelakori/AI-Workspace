# Source discovery comparison: operator review

**PREPARED_NOT_AUTHORIZED.** No real model inference, measured arm, or sealed
acceptance case has run. The existing HTTPX grants and quarantines remain closed.

Approval digest (SHA-256 of canonical sorted compact manifest JSON):

```text
ee17b4c45b8b82dccc1790a91dec1dead8c2983625121b86d785e743a39443d0
```

Review the exact [manifest](evidence/phase61/discovery-preparation/manifest.json),
[preparation receipt](evidence/phase61/discovery-preparation/receipt.json),
[task](../examples/phase61-discovery/FEATURE.md) and
[ten public cases](../examples/phase61-discovery/public_cases.json).
The local execution bundle is `.aiwork/phase61-discovery/benchmark`.
There is no real approval file or execution-state lease; the example grant
deliberately contains `operator_approved: false` and cannot dispatch anything.

## Target and frozen baseline

The target is [python-dotenv](https://github.com/theskumar/python-dotenv), pinned
at [`4fbc6ff07215367ece731006855e732d1405992c`](https://github.com/theskumar/python-dotenv/commit/4fbc6ff07215367ece731006855e732d1405992c).
Nested interpolation defaults reproduce a behavior described in
[upstream issue 326](https://github.com/theskumar/python-dotenv/issues/326).
That historical issue is closed; this is a bounded feature extension against
the measured pinned checkout, not a claim that an open issue awaits this patch.
No previous AI Workspace benchmark registered this repository; model pretraining
familiarity cannot be established.

The production module is `src/dotenv/variables.py`, **86 lines**. Its original
SHA-256 is `083d2a5cebefa41deae51a4140c0fda97eaf1d7ed2c96f92ba2c063054a5b74f`.
Only that file and the new `tests/test_nested_defaults.py` may change.
No implementation correction or solution patch has been supplied.

The unmodified baseline passes **2/10 public cases**; eight reproduce the
missing behavior. The complete upstream test collection passes **287 tests**,
with **five documented skips**: four root/permission cases and one Windows-only
case in the Linux verifier. Syntax/import validation passes. Public cases cover
nested defaults, balanced consumption of unused defaults, concatenation,
empty/None preservation, literal mapping values and `dotenv_values` integration.
All existing upstream cases remain regression checks.

Both arms contain the same 47-file inventory. The
[frozen input archive](../deliverables/phase61-discovery/frozen-input.zip) includes
the public BSD-licensed source, specification and checker; no sealed material.
The original upstream checkout remains clean. The verification image is frozen
as `sha256:5c19bf11295cb95f58cdc0250c8f699292e453a05b9fdf3960346b3517fe1abf`.
Its offline wheel lock, base-image identity and reproduction steps are retained.

## Resolved provider-catalog blocker

OpenCode 2.0.27 starts MCP connections asynchronously. The old direct server
preflight could succeed while the actual agent initially received only native
search tools. A private server's MCP list can likewise initially be empty or
pending. Official [CLI](https://opencode.ai/docs/cli/commands/) and
[MCP API](https://opencode.ai/docs/api/#mcp) interfaces support explicitly
connecting to a server and checking its location-specific status.

Engineering execution now starts an owned private server, waits for `checks`
to connect at the exact workspace location, then submits the task. A loopback
relay checks the actual provider-facing catalog **before forwarding each
request**. All four scoped tools must be present; unexpected tools, missing
catalogs or a different model latch the gate closed. Requests, schemas and model
arguments are forwarded without rewriting. No bootstrap substitute tool calls
are used. Permissions, exact anchors, source hashes and sixteen-call accounting
remain unchanged. A fixed session title avoids auxiliary title generation.
Schemaless auxiliary/compaction requests also fail closed; the gate does not
silently waive this rule if an 8K session needs compaction.

The [installed-harness inert proof](evidence/phase61/discovery-preparation/catalog-ready.json)
shows all four tools in the **first provider request**, zero auxiliary requests,
successful scoped edit/check execution and cleanup. Backend request hashes equal
the relay's captured request hashes. The API uses `max_completion_tokens: 2048`
and `reasoning_effort: none`. The
[negative proof](evidence/phase61/discovery-preparation/catalog-negative.json)
withholds one required tool: the backend receives **zero** requests and the
owned server is cleaned up. These are synthetic harness tests, not autonomous
feature completion. Measured private-server ownership currently requires Windows
jobs; unsupported measured POSIX ownership fails before launching the server.

## Matched arms and measurements

- **A:** the unchanged primary module and existing `resolve_variables` caller
  excerpt supplied once in the initial prompt, with original file hashes.
- **B:** discover the same code through the same tools. Both share the same
  active objective, workspace inventory, public diagnostics and write scopes.

Randomization was performed once during preparation. The frozen execution order
is **B, then A**. Approval still names exactly **`["A", "B"]`**; the manifest
determines execution order. Both are direct workers; no planner or hierarchy.

The model remains `aiwork-qwen35-phase4:8k`, Qwen3.5 9B, 8,192-token context,
2,048 output ceiling and reasoning disabled. Model identity matches the existing
recorded digest `5852b52876b93f88a1d3b8f6a9888e3f6f904a38dff024a18f28831f6cbc1048`.
No model weights, service settings or inference endpoint were changed.

Each arm retains **20 seconds warm-up, 180 engineering, 40 grading**, one session,
one attempt, a **150-second attempt ceiling** and **16 MCP operations**. Readiness,
baseline checks, inference and public tests consume the same budgets. The
controller reserves twenty seconds within the attempt for its public/authored
checks; the harness gets at most the remaining 130 seconds, including setup.
The complete upstream promotion gate runs during post-worker selection inside
the same 180-second engineering phase. There are no extensions or retries.

The neutral READY warm-up is identical for both arms. Preserve residency, TTL
and cache counters; no server restart or KV-cache purge is requested. An exclusive
operator window is required. Other clients and cache reuse remain measurement
limitations. Native searches do not consume MCP slots, but do consume time and
inference; their counts remain visible.

The upfront evidence is **3,471 UTF-8 bytes / 118 lines**, or **3,525 additional
prompt-text bytes** including its wrapper. Tests prove it appears once and does
not change the persistent objective. Exact model-token cost is **not measured
during preparation**: no generation or guessed tokenizer count is used. Authorized
execution records raw provider usage and the observed first-prompt token delta
A–B, alongside cache details. That delta includes wrapper/path token differences
and is not isolated tokenization of the excerpt alone.

Record first applied edit by MCP operation **8**, first public test by **12**,
their elapsed times, rejected edits/recovery, overlapping unchanged reads,
reads repeating upfront evidence, provider catalogs/usage, harness exit and wall
time. Completion requires **10/10 public**, the complete frozen upstream gate,
authored tests and **12/12 fresh sealed acceptance cases**, plus both milestones.
Partial correctness, missing delivery and harness failures remain distinct.
Final-candidate selection rejects scope violations, failed syntax/import gates,
upstream regressions and lost public passes; ties retain the original baseline.
Intermediate edit/check traces are retained, without claiming every intermediate
snapshot was independently ranked.

Freeze both selected candidates after engineering. Only then independently
author twelve distinct inputs outside worker contexts, disjoint from public
inputs, and grade both against that same sealed file. Expected values stay on
the controller; only case inputs enter read-only offline grading containers.
No sealed feedback returns to a worker. Interruption, nonzero harness exit,
catalog failure or cleanup failure stops the pair; quarantined arms cannot resume.

If A succeeds and B fails discovery, retrieval/allocation is the leading
explanation. Valid edits with failing logic in both arms point toward capability
under this configuration; malformed edits point toward contract adherence.
Catalog/provider failures make the capability comparison inconclusive. One
paired observation cannot establish a reliable success rate or causal superiority.

## Verification and approval

Execution code is frozen at **`0128db5`**, with every `aiwork/*.py` hash in the
manifest. Full regression discovery: **146 tests, 141 passed, five optional Docker
integrations skipped**, no failures. Installed OpenCode tests used inert providers
only. The real repository baseline ran in offline Docker. Initial environment
failures and their corrections are retained in the preparation receipt; no
unsuccessful agent campaign was hidden or repeated.

```powershell
.\.venv\Scripts\python.exe -m aiwork.discovery_benchmark validate .aiwork/phase61-discovery/benchmark
```

To authorize later, explicitly approve the digest above and exactly `["A", "B"]`,
including frozen B→A order and the stated limits. The future execution command
requires a separate `operator-approval.json` with `operator_approved: true`.
**No approval was created and no execution command was run in this preparation.**
See the [operator commands](../examples/phase61-discovery/README.md).
