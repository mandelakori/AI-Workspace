# Frozen ledger repair benchmark

This benchmark preserves the Phase 5.2 closeout at `f78498b`. Preparation archives its exact public starting workspaces, contracts, approved evidence, verified tokenizer handoff and all six original proposal directories. It checks the starting checkpoint inventories and binds the archive, compiler image and Python implementation files by SHA-256. The closeout jobs and selected checkpoints are unchanged. No operator-written implementation corrections are included.

## Configurations and permissions

The recorded baseline is `aiwork-qwen35-phase4:8k`, the existing local Q4_K_M model. Its two attempts per component are exhausted. The benchmark supports historical replay, with zero new inference requests. It exposes no command to dispatch this local baseline again.

The second configuration uses the archived `a100-existing` profile for the Qwen3.6 35B-A3B Abliterated Heretic Q6_K model, through `ssh aisak` and remote port 18080. It is **prepared, unexecuted and awaiting separate authorization**. Its live availability is UNTESTED. Preparation and planning open no SSH connection and contact no inference endpoint. The optional future dispatch requires a separately approved manifest digest and refuses managed profiles or changed verification images. It uses the existing forwarding helper and local offline Docker verifier.

Both configurations use the same starting sources, public cases, contracts, source-edit protocol and bounded context construction. Each permits at most two source requests per component, six overall, 2,048 output tokens per request, 45 seconds per request and 160 seconds per attempt. Workers have zero tool calls. The controller compiles and tests independently. These are source-edit repair trials, not OpenCode tool sessions.

The recorded local context is 8,192 tokens. The archived A100 profile declares 131,072 tokens; this preparation makes no server configuration change. Context excerpts and public-case summaries use the same adapter limits, so a larger server window does not add evidence. The A100 configuration retains `reasoning_effort = none` and llama.cpp's `chat_template_kwargs.enable_thinking = false`. Future dispatch saves the complete outgoing JSON payload, raw response, applied edits, hashes and metrics. The remote transport and settings are covered by a mocked authorization test; no live A100 repair has been validated.

## Independent evaluation stages

Each candidate receives three distinct measurements in separate offline Docker invocations:

1. Ordinary GCC compilation, with its full output and success flag.
2. Public behavioral execution, including exact per-case stdout, stderr, exit status and latency.
3. A separate UBSan build and execution of the entire same corpus, using `-fsanitize=undefined -fno-sanitize-recover=undefined`.

`compiled` refers only to ordinary compilation. `sanitizer_compilation` records the instrumented build. `sanitizer_passed` records complete execution without sanitizer reports, unexpected exits, timeouts or truncated output. `behavior` and `sanitized_behavior` retain their own correctness counts. Incorrect stdout alone does not become a sanitizer failure. A compiler failure leaves behavior and sanitizer execution ungraded. Flat zero passing-case counts in such receipts are ranking bookkeeping, not a completed behavioral evaluation.

The selector rejects sanitizer failures even when compilation and ordinary behavior pass. It also rejects lost public passes and incomplete evaluations. Ties retain the predecessor. A verified result requires all ordinary and instrumented public behaviors to pass. No sealed cases enter selection, diagnostics or worker contexts.

The historical Phase 5.2 balance gate combined compilation with assertions and therefore recorded failed gates as `compiled: false`. Those original receipts are preserved. New benchmark receipts split these stages and do not rewrite historical results.

## Reproduction without inference

Run from the repository root with the existing environment. Each destination must be new.

```powershell
$py = '.venv/Scripts/python.exe'
$root = '.aiwork/phase52/repair-benchmark'
& $py -m aiwork.repair_benchmark prepare `
    .aiwork/phase4-followup.local.toml .aiwork/phase4.local.toml $root
& $py -m aiwork.repair_benchmark replay-baseline `
    $root .aiwork/phase52/repair-benchmark-baseline
& $py -m aiwork.repair_benchmark plan-a100 $root
```

Preparation discovers the A100 configuration from local records. The bundle contains `local-baseline.json`, `a100-prepared.json`, public workspaces and original attempts. `manifest.json` binds their inventories and implementation hashes. A changed input or implementation blocks replay or dispatch. The [prepared plan](../.aiwork/phase52/repair-benchmark-a100-plan.json) records zero remote inference requests.

Only after separate authorization, the operator may use `run-a100 <benchmark> <new-destination> --config .aiwork/phase4.local.toml --approve <separately-approved-digest>`. This command was not run during preparation. It creates a separate state directory, reserves no more than six proposals, preserves rejected workspaces and records the selected source. It does not resume any exhausted closeout job.

## Recorded results

The retained starting sources remain framing **4/7**, validation **14/18**, and balance **8/10** on ordinary public behavior. Framing and validation pass UBSan execution; balance fails it and matches **7/10** instrumented public cases. None qualifies as a complete component.

| Historical proposal | Ordinary compilation | Ordinary behavior | UBSan execution | Previously passing public cases lost |
| --- | --- | --- | --- | --- |
| Framing 1, unchanged workspace | Pass | 4/7 | Pass | 0 |
| Framing 2 | Pass | 3/7 | Pass | 1 |
| Validation 1 | Fail | Not run | Not run | Build rejected; 14 prior passes unavailable |
| Validation 2 | Pass | 14/18 | Pass | 0 |
| Balance 1 | Pass | 1/10 | Pass | 7 |
| Balance 2 | Pass | 7/10 | Fail | 1 |

Among the six proposals, one failed ordinary compilation and one failed sanitizer execution. Balance's first proposal had no detected undefined behavior but failed nine behavioral cases. The first framing response contained an unchanged edit and was rejected before writing during the original run; its archived workspace is replayed here and is not claimed as a valid source correction. New staged evaluation confirms no proposal can replace a retained checkpoint. Historical decisions remain unchanged.

The six historical requests consumed **19,847 input tokens and 2,081 output tokens**, with **137.359 seconds** summed across original attempts. Reasoning-token counts were unavailable. The new independent verification replay took **135.484 seconds**, with zero inference requests. These measurements describe the preserved local trial; there is no A100 correctness, token or timing result.

The [baseline report](../.aiwork/phase52/repair-benchmark-baseline/report.json) separates replay verification time from the historical generation/attempt time. Per-candidate receipts and raw public process results are beside it. The [original closeout report](LEDGER-CLOSEOUT.md) remains the record of historical execution and selection.

No new local inference or remote experiment is part of this benchmark preparation. No sealed suite was used or created.

All **78 regression tests passed**, including the existing 73 and five new tests for stage separation, authorization, archive integrity, bounded dispatch and rollback. Offline Docker and the installed OpenCode boundary test were enabled. The direct fixture passed in job `6abf32b214dd49c1980272f0b4c80621`. Logs are preserved in `.aiwork/phase52/repair-benchmark-tests-final.log` and `.aiwork/phase52/repair-benchmark-direct-final.json`.
