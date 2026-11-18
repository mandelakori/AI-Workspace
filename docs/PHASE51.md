# Phase 5.1 adaptive engineering

## Ranked specialists

A component policy can now declare `public_cases`, two verification recipes for compilation and invocation, and a bounded retry count. The controller reproduces the starting candidate's behavior in Docker, compiles every proposal, and compares every approved case on the same frozen corpus. Public results record the case name, individual stream differences, expected and observed output, source hashes, ancestry and selection decision. Retries stage the strongest compatible checkpoint. A proposal that loses a passing case is rolled back, and a tie retains the incumbent. The absolute attempt limit also applies after resume.

Workers can use the installed tool-using harness with explicitly approved `commands`, or the existing single-file source adapter. The latter receives approved context, public reproducers, the selected source, and bounded compiler diagnostics on each turn. Independent compilation and testing happen between model turns. The controller selects the resulting checkpoint. Private verification directories are prohibited for these jobs.

## Interfaces and revisions

`hierarchy investigate` sends one failed ranked component's public evidence to a local diagnostic planner. Its review-only result can propose fresh interfaces, owned outputs, component splits, missing requirements and dependency rewiring. The validator rejects missing dependents, cycles, path collisions, protected output paths and removal of unrelated dependencies. The proposal has no executable check recipes. The operator supplies or reviews those recipes and interface assets in a new project registration before execution.

`hierarchy plan --reuse-from PROJECT/RUN` binds a predecessor approval into the new approval receipt. The executor can retain a verified node only when its complete policy, input hashes, pinned runner, inference profile and dependency lineage match. Its dependents are regenerated when any required predecessor changes. Reused artifacts are hashed again before handoff. This path was demonstrated by keeping the ledger analysis, behavior verdict and output job in a reviewed diagnostic graph.

```powershell
$py = '.venv/Scripts/python.exe'
$cfg = '.aiwork/phase4-followup.local.toml'
$env:PYTHONPATH = (Get-Location).Path
& $py examples/phase51/stage_ledger.py .aiwork/phase51/my-ledger .aiwork/phase4-followup/controller/native/64685c5d53b9405298e778adce13e13f .aiwork/phase4-followup/controller
& $py -m aiwork --config $cfg hierarchy register my-ledger .aiwork/phase51/my-ledger/project.json
$plan = & $py -m aiwork --config $cfg hierarchy plan my-ledger trial --reviewed .aiwork/phase51/my-ledger/tree.json --objective 'Repair ledger components using their public case evidence.' --profile laptop-ollama-8k | ConvertFrom-Json
Get-Content $plan.document
& $py -m aiwork --config $cfg hierarchy run my-ledger trial --approve $plan.approval --investigate-on-failure syntax
& $py -m aiwork --config $cfg hierarchy status my-ledger trial
```

The optional failure investigation creates at most one diagnostic proposal. It submits no revised component jobs. `hierarchy investigate <project> <run> <component> <proposal-name>` also invokes that bounded review path directly.

## Behavioral modeling and ledger results

The ledger fixture declares input framing and operand grammar, state bounds and amount bounds, transition rules, silent/error/denied/value replies, output streams and error-state preservation in `behavior.json`. A deterministic checker matches the target identity, the decompiled 96-byte `fgets` call and observable command/error tokens. It then replays the behavioral model against all 18 archived public observations. The checker passed with zero inference requests. Its scope is the fixture's ASCII, decimal-token contract. This is an operator-authored behavioral description validated against public evidence.

The ledger specialists started from historical model-authored failed framing and balance files. Syntax started without an implementation. Framing's selected baseline passed 2/7 public probes and balance passed 4/8. Each worker had three proposal attempts. Framing and balance repeatedly emitted unchanged source. Syntax produced three compile failures and retained the earliest policy-valid proposal on ties. The output component passed. Integration stayed blocked. Ten source proposals used 20,121 input and 4,042 output tokens in total. All failed source trees and raw model responses remain in their original attempt directories. [Ledger run](../.aiwork/phase51/ledger-result.json)

The diagnostic planner proposed a new tokenizer interface and a dependent validation interface, rewired the whole-program test dependency and identified token-buffer termination as a missing requirement. The split remains a review artifact. Its executable implementation has not been approved or tested. [Model-proposed revision](../.aiwork/phase4-followup/controller/hierarchy-projects/ledger-adaptive/plans/trial/investigations/split-syntax/revision.json) · [Compatible artifact reuse](../.aiwork/phase51/reuse-result.json)

## Successful specialist repair

The archived model-authored meter state function added two signed integers before clamping. Seven new public state probes included signed extremes and state preservation. The baseline passed 5/7. The specialist repaired the function in one proposal, compiled it and passed 7/7 without losing a prior pass. The verified analysis and band artifacts were reused. Independent testing and integration passed. The repaired meter matched **32/32 new sealed cases**, while the archived executable matched **27/32** on the identical suite. The worker used 922 input and 87 output tokens, taking 10.672 seconds including public verification. No operator source correction was supplied. [Repair and selection](../.aiwork/phase51/meter-result.json) · [Independent comparison](../.aiwork/phase51/independent/meter/reports.json)

## Matched repeated comparisons

Two newly authored stateful utilities were tested twice per approach. Debt saturates signed adjustments to a bounded positive/negative state. Water retains a capped high-water mark and resets on negative input. Each comparison used the same existing laptop model, source-proposal adapter, temperature settings, 1,300-token generation cap per request, exact reference hash, pinned Docker image, complete public executable corpus and final grading procedure. The hierarchy had two components with up to two requests each. The monolithic source had up to four requests. Both arms had a 328-second maximum aggregate worker time. Every observed implementation passed on its first attempt.

| Target and approach | Repetitions | Sealed per trial | Mean input tokens | Mean output tokens | Mean execution time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Debt hierarchy | 2 | 32/32 | 634 | 123 | 11.25 s |
| Debt monolithic | 2 | 32/32 | 381 | 140 | 11.87 s |
| Water hierarchy | 2 | 32/32 | 636 | 169 | 12.62 s |
| Water monolithic | 2 | 32/32 | 383 | 184 | 13.04 s |

The operator authored fixture contracts, unit drivers, orchestration glue and reference utilities, then approved each reviewed graph. Models authored every implementation file. Each trial used one plan approval and no in-run source intervention. The graph topology was fixed for these comparisons, so planner inference is excluded. There were zero lost public passes and zero failed testing or integration jobs. These small local trials show agreement under the tested contracts and do not establish a general advantage for either approach. [Per-attempt tokens, timing and outcomes](../.aiwork/phase51/metrics.json) · [Debt sealed results](../.aiwork/phase51/independent/debt/reports.json) · [Water sealed results](../.aiwork/phase51/independent/water/reports.json)

All candidates were frozen and rehashed before each new private suite was authored. The suites were stored outside the registered input scopes. No model work continued against those candidates after final grading.

## Regression environment

The initial venv-based baseline twice failed the worker-kill recovery test with an occupied `worker.lock`. Invoking the interpreter behind the Windows venv launcher passed all original 64 tests. The final suite uses that interpreter so the test terminates its actual Python worker process.

All **67 tests** passed, including the installed OpenCode boundary check and the original 64 regressions. The direct fixture passed in job `5e42376663e34b6f8b31890c2b243078`. All experiments used the existing laptop model and offline Docker image. The laptop model configuration and existing remote services were preserved.

```powershell
$py = & .venv/Scripts/python.exe -c "import sys; print(sys._base_executable)"
$env:AIWORK_TEST_DOCKER_IMAGE = 'aiwork-engineering:phase3'
$env:AIWORK_TEST_OPENCODE_BOUNDARY = '1'
& $py -m unittest discover -s tests -q
```
