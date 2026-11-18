# Phase 5 hierarchical engineering

Each registered project supplies one reviewed policy with named components, public inputs, interface contracts, owned outputs, dependencies, and approved checks. The coordinator proposes a nested grouping of those components. A planning specialist can revise a subgroup within the same registered policy. Introducing a new interface or tool requires a new registration. The plan review exposes the exact authority and the digest required for submission.

The controller queues components only when their dependencies verify. The graph passes only selected, hash-checked outputs and the files listed for that worker. Analysis, testing and integration can run deterministic recipes. Tool-using implementation workers use the existing harness. For narrow jobs, the registered policy can request one local model proposal for a single file with explicit context. That worker cannot choose paths or tools. A resume starts the failed component from its own checkpoint with a debugging role. The controller leaves unrelated verified artifacts available to consumers.

## Local operator workflow

The ledger example stages an archived reference's public observations and bounded static metadata. Worker inputs include declarations and tests. The provided `main.c` wires the interfaces together. The model supplies the framing, parser, state machine, and output implementations.

```powershell
$py = '.venv/Scripts/python.exe'
$cfg = '.aiwork/phase4-followup.local.toml'
$env:PYTHONPATH = (Get-Location).Path
$ledgerNative = '.aiwork/phase4-followup/controller/native/64685c5d53b9405298e778adce13e13f'
& $py examples/phase5/stage_ledger.py .aiwork/phase5/my-ledger $ledgerNative --source
& $py -m aiwork --config $cfg hierarchy register my-ledger .aiwork/phase5/my-ledger/project.json
$plan = & $py -m aiwork --config $cfg hierarchy plan my-ledger trial --profile laptop-ollama-8k --objective 'Reconstruct and independently test the ledger interfaces.' | ConvertFrom-Json
Get-Content $plan.document
# Review interface scopes, check commands, dependencies, profile, image and budgets before submitting.
& $py -m aiwork --config $cfg hierarchy run my-ledger trial --approve $plan.approval
& $py -m aiwork --config $cfg hierarchy status my-ledger trial
```

`hierarchy run --retry <component>` resumes one unsuccessful implementation within its registered attempt budget. `hierarchy plan <project> <new-run> --from-run <prior-run> --group <group> --objective <text> --profile <local-profile>` proposes a subgroup revision and produces a new approval. `hierarchy status` returns each verified output's path and SHA-256. Operators can also pass a reviewed tree with `hierarchy plan --reviewed <file>`.

The new window-counter fixture can be staged with `examples/phase5/stage_window.py <config> <staging> --source`. It supplies a second stateful program with a different command protocol. Its integration fixture owns the process loop and formatting. The workers implement syntax and state transitions.

Add `--meter` to stage the smaller band meter. Its generated components implement the saturating state update and the band function.

`examples/phase5/freeze_candidate.py <config> <project> <run> <reference-native-run> <destination>` freezes a verified integration artifact. The operator authors a new sealed suite after freezing and then runs `native grade <destination> --cases <private-inputs>`. Keep the evaluation suite outside all registered input scopes. The final grader sends one stimulus at a time to isolated executables and stores the results outside the repair and hierarchy jobs.

## Local comparisons

The comparisons used the installed laptop model `aiwork-qwen35-phase4:8k`, separate staged jobs, and the same reference hash, public corpus and pinned Docker image within each target. The ledger's ranked single-agent run started from its archived 13/18 source. Its hierarchy generated the four component sources from their interface contracts. Both ledger configurations allowed up to 840 seconds of implementation attempt time. The meter had a 400-second component ceiling and a 214-second single-agent ceiling. Its executed component work finished on the first attempts. Hierarchy source workers made one bounded source request per attempt, while the ranked single-agent jobs used OpenCode. These harness differences and small samples limit the comparison.

| Target and approach | Public | Fresh sealed | Implementation attempts | Model input / output tokens | Execution wall time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ledger hierarchy, source proposals | Output verified, three components blocked | No candidate | 7 | 11,074 / 2,638 | 93.92 s |
| Ledger ranked single agent | 13/18 retained | 6/40 | 2 | 38,279 / 12,404 | 439.40 s |
| Window hierarchy, source proposals | Both implementation components blocked | No candidate | 4 | 5,236 / 1,290 | 48.57 s |
| Window ranked single agent | No compilable candidate | No candidate | 2 | 15,830 / 1,904 | 101.55 s |
| Meter hierarchy, source proposals | 9/9 | 38/40 | 2 | 2,029 / 348 | 11.42 s, plus 4.89 s planning |
| Meter ranked single agent | 9/9 | 37/40 | 1 | 5,665 / 835 | 36.01 s |

Execution time runs from the first attempt dispatch through the last attempt record. Meter token counts include the accepted planner request. The ledger and window source trials reused earlier proposed trees after review. Those planner calls used 680/269 and 447/142 input/output tokens respectively. Earlier rejected plans and OpenCode ledger attempts are preserved separately. No source corrections were supplied to either approach. The operator defined test contracts and glue, submitted approvals, and triggered the ledger's three targeted retries and window's two retries under the registered budgets. The meter needed one approval and zero retries.

In the ledger, the verified output component kept the same job throughout all three targeted retries. The controller blocked linking while framing, syntax and balance remained unverified. The rejected proposals lost unread input at a newline, failed to compile the parser, or applied the wrong transition. The ranked single-agent alternatives dropped to 2/18 and 1/18, so its controller restored the 13/18 baseline. In the window trial, both component checks failed and the monolithic file failed compilation. Neither blocked graph reached integration. [Ledger hierarchy](../.aiwork/phase5/ledger-evidence-status.json) · [Ledger sealed report](../.aiwork/phase5/ledger-independent/reports.json) · [Window hierarchy](../.aiwork/phase5/window-evidence-status.json)

The meter analysis, both generated components, testing and integration independently verified on their respective checks. Both frozen executables missed two signed-integer-extreme cases. The single-agent executable also differed on one additional format case. The specialist produced a separate review receipt that refined only the meter's analysis-and-state group. Its approved components, tools and dependencies stayed the same. [Meter integration](../.aiwork/phase5/meter-status.json) · [Meter sealed report](../.aiwork/phase5/meter-independent/reports.json) · [Specialist review](../.aiwork/phase4-followup/controller/hierarchy-projects/meter-phase5/plans/refined/approval.json)

The independent suites were generated after freezing and held outside the registered input scopes. The comparison audit confirmed that the model jobs had no private verification directory. The 60 Phase 4 tests and four new hierarchy tests passed with offline Docker and the installed OpenCode boundary test enabled. The direct fixture passed. [Per-attempt comparison metrics](../.aiwork/phase5/comparison-metrics.json)
