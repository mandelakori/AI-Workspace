# Phase 5 final handoff

The bounded finalization completed six local function-replacement requests and accepted **0/6** corrections. No component reached full public correctness. Ledger integration remains blocked. No integration attempt or new sealed evaluation followed the failed component gates.

## Preserved checkpoints and evidence

The A100-authored balance checkpoint was imported into a new campaign, hash checked, and independently reproduced at **9/10** ordinary and instrumented public cases with UBSan passing before local inference started. Original frozen inputs, exhausted jobs and A100 evidence remain unchanged. Verified analysis, behavior, tokenizer and output artifacts were copied with their hashes into the handoff.

| Best component | Public | UBSan execution | SHA-256 |
| --- | --- | --- | --- |
| Framing | 4/7 | Pass | `3fd713a80bfbaf4b11f2a5337e6413b99638f4212a219692657d04417d7ffc67` |
| Validation | 14/18 | Pass | `20c7a48ca1792ae37929543ca111defbb5dc5a7b6da4059f0937e19c6afaaf1e` |
| Balance, imported A100 source | 9/10 | Pass | `4426488d8ff2e09224725f82571e12e9eeed7b2b683e9570c1be0b300324881e` |

These are partial component checkpoints. Passing sanitizer execution does not imply correct behavior. [Selected checkpoint archive and trial summary](../.aiwork/phase5-finalization/handoff/summary.json) · [Verified dependency copies](../.aiwork/phase5-finalization/handoff/verified-dependencies.json) · [Complete execution report](../.aiwork/phase5-finalization/execution/report.json)

## Different repair strategy

`aiwork.function_repair` locates one exact approved C signature using token positions and balanced braces while masking comments and literals. The model receives the complete function, surrounding declarations, contract, authorized static evidence, entire public corpus and precise discrepancies. Retries retain public compiler and sanitizer diagnostics.

The model returns one `function` string. The controller rejects changed signatures, extra top-level code, includes, directives, unchanged functions and oversized responses. It replaces only the identified span and records prefix, suffix and source hashes. Independent ordinary compilation, behavioral checks, instrumented compilation and UBSan execution use the existing offline verifier. The ranked selector rejects lost passes and sanitizer failures. This locator supports the reviewed C signatures; it is not a general C/C++ transformation engine.

All implementation text came from model responses. The development agent supplied orchestration, contracts, diagnostics and tests. It inserted no C correction into autonomous results.

## Measured results

| Local function trial | Outcome |
| --- | --- |
| Framing, both requests | Returned the original function unchanged; rejected before compilation |
| Validation, first request | Added an extra `signature` field; protocol rejected, not compiled |
| Validation, second request | Compiled, passed UBSan, retained numeric-operand rejection; 14/18 tie rejected |
| Balance, first request | Compiled, passed UBSan; 9/10 tie rejected |
| Balance, second request | Compiled, passed UBSan; gained invalid-command handling but lost two prior cases; 8/10 regression rejected |

Three of six responses produced valid changed functions. All three compiled and passed UBSan; none qualified or was promoted. Two unchanged responses and one protocol failure were preserved separately. Compilation and sanitizer failure counts were both zero among evaluated candidates. The selector kept the stronger 9/10 balance source rather than the latest 8/10 proposal.

The trial consumed **18,517 input and 3,179 output tokens** (21,696 total), **106.906 seconds** of proposal processing, **165.266 seconds** summed across attempts, and **209.797 seconds** campaign wall time. The preceding import replay is separate. All six responses ended normally, below the 2,048-output-token cap; reasoning-token counts were unavailable. Each request had a 45-second timeout and used the existing local `aiwork-qwen35-phase4:8k` profile. No remote inference or paid cloud lifecycle action occurred in this finalization.

For context, the recorded local exact-edit trial accepted 0/6 proposals. The authorized A100 exact-edit trial accepted 1/6, the partial balance correction imported here. This function trial started balance from that stronger source and changed the prompt representation and diagnostics. These small, different trials do not establish a causal model or strategy ranking. [Earlier local/A100 comparison](../.aiwork/phase52/repair-benchmark-a100-20261120-comparison.json)

## Verified capabilities and limits

Phase 5 has demonstrated approved nested task graphs, scoped component handoffs, compatible verified-artifact reuse, review-only model interface refinement, independent verification and ranked rollback. Earlier stateful-target integration is documented in [Phase 5](PHASE5.md) and [Phase 5.1](PHASE51.md). This finalization additionally verified function-scope enforcement, public diagnostic retention, request reservation before dispatch, exhausted-run rejection and preservation of imported work.

Native ledger repair remains unreliable. Framing ignores newline boundaries. Validation still rejects valid numeric operands. Balance still fails the invalid-command state-preservation sequence. Function replacement did not resolve those limitations within the approved budget. The qualified ledger integration path was not exercised; its failure gate is regression tested. No whole-program or sealed score exists for this finalization.

All **83 regression tests passed**, including the existing 78 and five relevant function-repair tests, with offline Docker and the installed OpenCode boundary test enabled. The direct fixture passed in job `85cf3fbe11b04349a648be433ed72783`. [Regression log](../.aiwork/phase52/phase5-final-tests.log)

## Continuing development

Inspect preserved evidence without inference:

```powershell
Get-Content .aiwork/phase5-finalization/handoff/summary.json
.venv/Scripts/python.exe -m aiwork.function_repair --help
.venv/Scripts/python.exe examples/phase52/replay_public.py `
    .aiwork/phase4-followup.local.toml ledger-closeout trial framing retains-short-lines
.venv/Scripts/python.exe examples/phase52/replay_public.py `
    .aiwork/phase4-followup.local.toml ledger-closeout trial validation positive-sign
```

The frozen benchmark remains pinned to its recorded implementation at `57ba9fb`. Its strict legacy loader intentionally rejects a changed package inventory. The new function campaign separately verifies every originally recorded implementation file and all frozen inputs while allowing this additive module. Use the original commit for historical benchmark dispatch/replay.

The completed function execution cannot resume. After a **new explicit repair authorization**, a fresh reviewed campaign can be staged and executed:

```powershell
$py = '.venv/Scripts/python.exe'
$cfg = '.aiwork/phase4-followup.local.toml'
$stage = & $py -m aiwork.function_repair --config $cfg stage `
    .aiwork/phase52/repair-benchmark .aiwork/phase52/repair-benchmark-a100-20261120 `
    .aiwork/phase5-next-authorized | ConvertFrom-Json
& $py -m aiwork.function_repair --config $cfg run `
    .aiwork/phase5-next-authorized --approve $stage.approval
```

Only a campaign with all component gates passing may use `integrate <campaign>`. A successful public integration is frozen before any new independent sealed inputs are authored. Preserve the current handoff and failures as reference evidence. Further work should target the demonstrated repair limitations before expanding architecture.
