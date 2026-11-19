# Phase 5.2 ledger closeout

The bounded closeout did **not** produce a verified integrated ledger. Six local model requests, two per failing component, produced no accepted correction. Work stopped at that limit. Linking and final sealed evaluation remain blocked. An absent executable has no whole-program score.

## Implementation and preservation

The existing source adapter now optionally accepts one to three exact-match edits through `source_patch = true`. The controller fixes the destination to the component's owned deliverable, rejects ambiguous, unchanged, oversized or malformed edits before writing, and records model-authored edits and source hashes. Complete-file proposals remain the default. Previous public-attempt diagnostics have a separate bounded prompt field so the main diagnostic excerpt cannot truncate them away.

The closeout registration used the same interfaces, local `aiwork-qwen35-phase4:8k` model and pinned offline image `sha256:1b5e1619d2da515d953428d37729da1e25d2fa18946c1289780f3b7d65e3bd9b`. Analysis, behavior, tokenizer and output reused their exact verified jobs. Their sources were not regenerated. The three failing workers started from hash-checked public-selected model sources. The operator supplied contracts, public diagnostics, test tooling and orchestration, with no implementation corrections.

Balance's approved build recipe now requires its public corpus under `-fsanitize=undefined -fno-sanitize-recover=undefined`. Two additional public sequences check unused amount fields, invalid commands and state preservation. A failed gate makes a candidate ineligible. The existing selector records this combined build/test failure as `compiled: false`, even when GCC succeeded. The separate audit records compilation and per-case results independently. Its scores below must not be confused with the selector's zero eligible-case count after a failed gate.

## Measured public outcomes

Frozen selected sources were recompiled and replayed in separate offline containers after all workers finished. Every invocation completed.

| Component | Retained public result | Attempt 1 | Attempt 2 |
| --- | --- | --- | --- |
| Framing | 4/7 | Identical old/new edit rejected before writing | 3/7, public regression rejected |
| Validation | 14/18 | GCC rejected a duplicate `amount` declaration | 14/18, tie retained predecessor |
| Balance | 8/10 ordinary, 7/10 UBSan | 1/10 UBSan, gate rejected | 6/10 UBSan, gate rejected |

Framing still combines `a\nbc\n` into one chunk. The worker received the static `fgets` evidence and complete seven-case public corpus. Its second edit retained `fread` and consumed another byte to inspect for a newline, losing a previously passing boundary case. The selector restored the stronger checkpoint.

Validation still rejects numeric operands in the alphabetic check over all words. Both requests received the entire selected source, all 18 public cases and a diagnostic naming this cause. The first changed the numeric branch but introduced a duplicate declaration. The second changed only the later `atoi` branch, leaving the rejecting earlier loop and the incorrect TAKE negation intact. All four valid numeric cases still fail.

Balance's first edit rejected every operation except ADD/TAKE before reaching SHOW, RESET or SKIP. Its second replaced the 0..1000 amount check with checks only for the signed integer extremes, still after arithmetic. It retained the overflow and admitted oversized operands such as the already-public 1001. The selected predecessor still triggers UBSan on the already-public initial balance seven plus `INT_MAX` input. The raw-interface cases also expose rejection of unused negative amounts and state mutation for an invalid command. Neither repair passed the gate.

All six responses ended with `finish_reason=stop`. They used 19,847 input and 2,081 output tokens, zero worker tool calls, and 137.359 seconds summed across implementation attempts. These were bounded source-edit proposals followed by controller compilation and verification. They were not tool-using specialist sessions. The remaining limitation is the installed model's incorrect or unchanged corrections despite supplied public evidence. This experiment does not demonstrate successful autonomous ledger repair.

## Evidence and reproduction

The [audit report](../.aiwork/phase52/closeout-audit/report.json) contains source hashes, request/response paths, context receipts, case counts, per-attempt metrics and separate ordinary/sanitized replays. The [graph result](../.aiwork/phase52/closeout-result.json) records preserved job IDs and blocked integration. Original failures, proposed patches, rejected workspaces and selection receipts remain in their job directories. The three selected source hashes are:

| Component | SHA-256 |
| --- | --- |
| Framing | `3fd713a80bfbaf4b11f2a5337e6413b99638f4212a219692657d04417d7ffc67` |
| Validation | `20c7a48ca1792ae37929543ca111defbb5dc5a7b6da4059f0937e19c6afaaf1e` |
| Balance | `e798b55ff3eb390e1e2e8dfe137a4ae42b8c5f871b63113defa29feaae0e9e81` |

Reproduce existing public failures without inference:

```powershell
$env:PYTHONPATH = (Get-Location).Path
$py = '.venv/Scripts/python.exe'
$cfg = '.aiwork/phase4-followup.local.toml'
& $py examples/phase52/replay_public.py $cfg ledger-closeout trial framing retains-short-lines
& $py examples/phase52/replay_public.py $cfg ledger-closeout trial validation positive-sign
& $py examples/phase52/audit_closeout.py $cfg .aiwork/phase52/closeout-audit-repeat
```

`stage_closeout.py <config> <new-directory>` reproduces staging from the preserved predecessor. It makes no inference calls. A new execution requires a separately reviewed registration and two-attempt plan. The completed `ledger-closeout/trial` attempt limits are exhausted.

No final sealed suite was created or graded because the component acceptance gates never passed. Historical private inputs were not supplied to the workers or used for this selection. Fresh final evaluation requires a verified integration artifact to be frozen first. No partial component score is an integrated or sealed score.

All 73 regression tests passed, comprising the existing 71 plus two targeted-edit tests. The installed OpenCode boundary test and offline Docker checks were enabled. The original venv interpreter invocation worked. The direct fixture passed in job `deb952a5d0fc491484144cd1cf667c33`. Raw logs are in `.aiwork/phase52/closeout-regression-final.log` and `.aiwork/phase52/closeout-direct.json`.
