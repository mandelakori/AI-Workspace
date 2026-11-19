# Ledger specialist repair

The executable revision follows the model-proposed tokenizer and validator split. The reviewed tokenizer owns whitespace boundaries and bounded, NUL-terminated word storage. The validator owns vocabulary, operand count and signed-decimal syntax. Numeric amount policy remains in the balance component. The operator supplied declarations, probes and orchestration glue. Workers supplied implementation source.

The original proposal described opaque token IDs without defining their representation. Review replaced that ambiguity with `TokenStream`, containing at most three 96-byte word buffers, a count and an invalid flag. The validator receives that value without modifying it. The process loop calls a small interface bridge. Workers own the framing, tokenization, validation and balance implementation files.

Each worker can edit one owned source file. Its approved command menu compiles and runs named public cases in an offline container. Independent ranking compares the full corpus in separate containers, preserves passing cases, and retains the strongest checkpoint. The graph links only verified components. The analysis and validated behavior jobs are reused from the prior approval. The output component requires verification with the revised header.

## Preserved failure diagnosis

The audit covers 15 source proposals from Phase 5 and Phase 5.1. Seven returned the existing source unchanged. Five failed compilation. Two syntax retries received a 2,400-byte excerpt of a 2,461-byte selected file. Every inspected model response ended with `finish_reason=stop`. None exhausted its model generation cap.

The framing seed read a fixed block and then discarded bytes around a newline. Its successor continued to use `fread` and removed the newline. The balance seed applied addition for both ADD and TAKE, and failed amount validation. The syntax proposals contained invalid C return expressions, undeclared identifiers or writes through a const pointer. The request files show that the source adapter received selected static facts, the interface header, current source and up to two public reproducers. The remaining public corpus was staged on disk but unavailable to that adapter's model request. [Request and response audit](../.aiwork/phase52/diagnosis.json)

The source adapter now sends the complete bounded selected component, records context sizes, uses the existing profile's output allowance up to 2,048 tokens, and can include bounded summaries of the approved public cases. The tool worker can inspect the staged corpus, invoke compilation and public diagnostics, edit its source, and repeat within its deadline. Both strategies retain the same independent ranked verification.

The initial public command helper failed to decode invalid UTF-8 emitted by a broken tokenizer. Independent selection still recorded all case verdicts. The revised helper renders invalid output with replacement characters so later public diagnostics can continue. The raw process output and independent verifier evidence remain available.

## Windows worker ownership

The ownership probe recorded launcher PID 57576 and actual Python worker PID 58548. Killing the launcher alone had left the worker's lock alive in the earlier test path. The local process runner now creates its child suspended, assigns it to a private Windows job, checks the thread's process ownership, and then resumes execution. Cleanup closes or terminates the owned job handle, covering the venv launcher and descendants. The recovery test now invokes this owned process path. The underlying-interpreter workaround remains available. [Ownership receipt](../.aiwork/phase52/ownership/report.json)

The regression probe also starts an unrelated test-owned process and confirms that terminating the worker job leaves that process alive. A separate timeout test verifies cleanup when a descendant inherits output pipes. The Windows implementation uses suspended creation and job assignment, plus the kill-on-close job limit. [Microsoft process assignment](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject) · [Microsoft job lifetime](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

## Reproduction

```powershell
$py = '.venv/Scripts/python.exe'
$cfg = '.aiwork/phase4-followup.local.toml'
$env:PYTHONPATH = (Get-Location).Path
& $py examples/phase52/diagnose.py .aiwork .aiwork/phase52/diagnosis-repeat.json
& $py examples/phase52/stage_split.py .aiwork/phase52/new-review
& $py -m aiwork --config $cfg hierarchy register my-ledger-tools .aiwork/phase52/new-review/tools-project.json
$plan = & $py -m aiwork --config $cfg hierarchy plan my-ledger-tools trial --reviewed .aiwork/phase52/new-review/reviewed-tree.json --reuse-from ledger-adaptive/trial --objective 'Implement and verify the reviewed split.' --profile laptop-ollama-8k | ConvertFrom-Json
Get-Content $plan.document
& $py -m aiwork --config $cfg hierarchy run my-ledger-tools trial --approve $plan.approval
& $py -m aiwork --config $cfg hierarchy status my-ledger-tools trial
```

The source variant uses `source-project.json` from the same staging action. Each variant uses the existing local model, pinned Docker image, three attempts per implementation and a 160-second attempt limit. Tool sessions may make multiple model turns. Source requests produce one complete file per attempt. These generation strategies have different token consumption, which is reported separately.

## Measured outcomes

The first source run verified tokenization at 9/9 public cases and left framing at 2/7, balance at 4/8 and validation uncompiled. The tool run improved framing to 4/7 and balance to 8/8. Its tokenizer reached 5/9, so the dependency gate blocked validation. The context-summary follow-up reached 8/9 tokenization cases and retained the failing framing and balance seeds.

The final composition used the verified model-authored tokenizer and balance sources. It revalidated their public cases and retained compatible evidence and output jobs. The remaining workers also received the original Ghidra listing, whose bytes matched the archived intake. Framing's traces show reads of that listing. It reached 4/7, then submitted a 3/7 regression and a build failure. The controller retained 4/7. Validation reached 12/18.

Earlier tool sessions tried to write additional test files outside their approved scope. Those requests were denied and preserved in the traces. An additional reviewed repair added named public reproduction commands and decoded framing's hex output into readable chunk lists. It retained the strongest selected source and allowed two attempts for each remaining worker. Framing emitted unchanged source twice. Validation rejected an 11/18 regression, then improved to 14/18 without losing a previous pass. All linking attempts remained gated by the unsuccessful components.

| Trajectory | Model sessions | Input tokens | Output tokens | Tool calls | Sum of attempt time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Source adapter | 11 | 19,561 | 4,222 | 0 | 174.52 s |
| Tool worker | 8 | 81,701 | 10,509 | 84 | 599.11 s |
| Full public context follow-up | 10 | 24,867 | 2,481 | 0 | 109.45 s |
| Composition with original static evidence | 6 | 84,217 | 11,797 | 89 | 645.11 s |
| Targeted final repairs | 4 | 44,347 | 5,432 | 28 | 361.47 s |

Each trajectory used the existing `aiwork-qwen35-phase4:8k` model, public case files and independent ranked verifier. Tool sessions can make several generations, and blocked dependencies change which workers run. These totals describe the measured paths and do not establish an efficiency advantage. The development agent specified and reviewed the representation, interfaces, glue, command scopes and public tests under the user's authorization. It supplied no source correction to a worker. [Per-attempt metrics and file reads](../.aiwork/phase52/metrics.json) · [Final graph](../.aiwork/phase52/focused-result.json) · [Verified source provenance](../.aiwork/phase52/hybrid/seed-provenance.json)

## Remaining blockers

The selected framing code calls `fread` for a fixed block. For the public input `a\nbc\n`, its probe returns one combined chunk. The required result has two chunks, `a\n` and `bc\n`. The worker read the static `fgets` evidence and the public reproducers, but retained the block-reading behavior.

The final validator applies an alphabetic command-word test to every word, including numeric operands. It therefore rejects all four remaining valid public number cases, including a leading plus and both signed integer limits. The public corpus also catches the malformed-input behavior. Both source and tool traces retain the proposed code and exact expected-versus-observed evidence.

These commands reproduce two remaining failures on the selected source through the existing offline verifier, with zero inference calls.

```powershell
& $py examples/phase52/replay_public.py $cfg ledger-targeted-tools trial framing retains-short-lines
& $py examples/phase52/replay_public.py $cfg ledger-targeted-tools trial validation positive-sign
```

Balance's ordinary public suite passes, but its generated implementation computes the next balance before checking the operand range. UBSan reports signed integer overflow for the published public probe with initial balance seven and an ADD amount of `INT_MAX`. Its raw interface also mishandles negative values in the unused amount field of nonnumeric commands. These defects remain in the frozen source. [Public overflow verification](../.aiwork/phase52/independent-latest/balance-ubsan-public.json)

## Independent grading

All worker requests ended before final candidate freezing and private grading. The final component replay uses separate five-second invocation and 180-second suite limits and requires all cases to complete. Every listed 24-case result completed all 24 invocations.

| Frozen component | Public | New private cases |
| --- | ---: | ---: |
| Framing | 4/7 | 0/24 boundary cases |
| Tokenizer | 9/9 | 24/24 |
| Validator | 14/18 | 16/24 balanced grammar cases |
| Balance | 8/8 | 24/24 reachable-command sequences |

The first random validator suite matched 23/24, with most stimuli malformed. The supplementary suite explicitly balances 12 valid and 12 invalid forms, yielding 16/24. Balance also matched 9/24 broader raw-interface cases with arbitrary values in unused fields. The sanitizer failure uses an already public, reachable arithmetic input. All results and failed suites remain in the evidence directories. [Complete component replays](../.aiwork/phase52/independent-latest/component-complete-results.json) · [Balanced and reachable supplementary replays](../.aiwork/phase52/independent-latest/supplementary-results.json)

The revised graphs produced no verified integrated executable. The historical ranked monolithic baseline passed 10/48 on a new whole-program suite using the same reference ELF and image. The previous Phase 5 and Phase 5.1 hierarchies also had no integrated candidate. [Whole-program baseline replay](../.aiwork/phase52/independent-latest/whole-results.json)

Three evaluator corrections are preserved. The first replay used an image tag when checkpoint receipts required the pinned image ID and fell back to baselines. A subsequent suite stopped on the overlap guard after repeating blank private inputs. A third component pass incorrectly used the invocation timeout as the entire suite deadline. The final evaluator revalidated candidate hashes and executed every case with separate budgets. A regression test covers that timing distinction. A request to print a failed private case was rejected by automatic approval review. Validation continued through a separately constructed public sanity input and aggregate-only private replay.

All **71 regression tests passed** through the original `.venv/Scripts/python.exe` invocation, including the existing 67 and the installed OpenCode boundary check. The direct fixture passed in job `3dae93c6aee742c9b1e50cce5922fd7c`. The underlying-interpreter workaround remains available. All new experiments used the existing laptop model and offline Docker image.
