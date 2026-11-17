# Phase 4 engineering handoff

Run these commands from the AI-Workspace checkout using Windows PowerShell. The examples use the existing Python 3.12 install, local Linux Docker image, Ghidra installation and configured open-weight profiles. The controller can also be installed with [Bootstrap.ps1](../scripts/Bootstrap.ps1).

```powershell
$py = '.venv/Scripts/python.exe'
$cfg = '.aiwork/phase4.local.toml'
$env:AIWORK_TEST_DOCKER_IMAGE = 'aiwork-engineering:phase3'
& $py -m unittest discover -s tests -v
& $py -m aiwork --config $cfg models
& $py -m aiwork --config $cfg doctor
```

If the Phase 4 config needs to be recreated, copy `config/phase3.example.toml` to `.aiwork/phase4.local.toml`, set `state = "phase4"` and `execution_state = "."`, and configure the installed Ghidra and Java paths as shown in the [Phase 3 runbook](ENGINEERING.md#phase-3-operator-workflow). Verify model aliases and local Docker availability using the commands above. Keep the existing shared execution state for GPU lane locks.

## Native development and final grading

Each `native.toml` declares the reference inputs or previously built executable, its format, a build and invocation recipe, development inputs, evidence selectors and the candidate's build, invocation and file contract. The reference source stays in a separate build copy. The worker gets named development observations and selected analysis JSON. The controller freezes and hashes the first candidate that passes development. The candidate and reference execute in separate, network-disabled containers with read-only mounts during final grading. The verifier uses a pinned local image and checks exit code, stdout and stderr. It saves per-case comparison provenance outside the worker workspace. [Docker run options](https://docs.docker.com/reference/cli/docker/container/run/)

```powershell
& $py -m aiwork --config $cfg native run examples/phase4/stride/native.toml --profile a100-qwen --evidence ghidra --trusted
New-Item -ItemType Directory -Force .aiwork/phase4/private | Out-Null
& $py examples/phase4/final_inputs.py stride .aiwork/phase4/private/stride-new.json --seed 730127
& $py -m aiwork --config $cfg native grade '<native_run from the first command>' --cases .aiwork/phase4/private/stride-new.json --workers 4
```

Use `bucket` or `ledger` in place of `stride` to reproduce those fixtures. Freeze every comparison candidate before running a shared final suite. Supply `--audit path/to/named-audit-inputs.json` for each upstream campaign audit used by the experiment. The evaluator rejects overlapping stimuli from development and supplied audits. Use a fresh private suite for further iterations after opening a final report. The published fixture generator makes its boundary recipes reproducible. For an evaluation requiring secret case design, supply an independently held generator and seed.

The historical runs below used 48 distinct inputs per target. The ledger includes 40 randomized sessions of 25 commands each and the classifier includes signed-integer boundaries and malformed inputs. The argv utility includes argument count, empty input, literal arguments, parsing and length boundaries.

| Target | Profile | Development | Final | Native run and final report directory |
| --- | --- | --- | --- | --- |
| Byte-stride utility | A100 Qwen Code | 5/5 | 48/48, verified | `316b157df27c459e93b5b171bc1df38d/final/6f6dc8aa669d40509875002fd5e41ff1` |
| Integer classifier | A100 OpenCode | 5/5 | 44/48, failed | `828a808088d342418c7bc1f12cf50d4e/final/dddce151787c4026b06a66a6d846a114` |
| Stateful ledger | A100 Qwen Code | 3/3 | 47/48, failed | `f540f4381804475f9bdfc76093968bd9/final/eb4968b2fe32425aa7a8f41e7e830d44` |
| Stateful ledger | Laptop OpenCode | No candidate in two attempts | Ungraded | `064e5bcde6694876b6f03ad6d3e72c99` |

The directories are under `.aiwork/phase4/native`. Each `run.json` links to the controller job, which holds harness traces, source and patches. The independently graded results support agreement only for the tested invocations. Classifier and ledger discrepancies remain unresolved. Lengthier sessions, other environments, execution through a PE-compatible runner, raw binary input protocols, side effects and untested error paths remain outside demonstrated coverage. No coverage-guided or symbolic engine was exercised.

`native run --rea-archive <archive> --evidence ghidra --trusted` adds static listings from a REA-Next archive after checking the exact target hash and the listing hashes. Its importer reads selected static entries. Campaign audit observations remain in the operator archive. With an authorized existing remote checkout, `campaign <fixture.toml>` accepts either a prebuilt ELF or flat sources and an offline build argv that produces `program`, development and audit JSONL, and `[input]` with stdin or file transport and fixed argv. The Phase 3 directory input still works. A prepared prebuilt classifier descriptor for this checkout lives at `.aiwork/phase4/rea-bucket/campaign.toml`. The new transport was exercised in staging tests. The remote dispatch and the matched REA-only versus Ghidra versus combined benchmark require authorization.

## Independent functions and scheduling

```powershell
$env:PYTHONPATH = (Get-Location).Path
& $py examples/phase4/component_benchmark.py --config $cfg --local-only
```

The two workers each receive an interface and a small approved compile recipe. Independent checks verify each implementation. The dependency journal carries both sources to a separate link and integration job that checks 501 inputs and both integer extremes. Both serial and two-worker trials passed in report `.aiwork/phase4/component-benchmarks/cbdb1f89c20e4e60/report.json`. This is one paired sample, with host overlap and one serialized Ollama lane. The same script can run the separate laptop and A100 profiles after explicit authorization. A100 multi-request capacity remains unmeasured.

## External repository and recovery

The benchmark uses PyPA packaging tag `25.0` at commit `f58537628042c7f29780b9d33f31597e7fc9d664`. The requested feature adds a dependency-policy library, a JSON CLI, tests and usage documentation. It checks duplicate requirements, canonical-name ordering with stable ties, markers, version constraints and invalid input. [PyPA packaging source at the pinned revision](https://github.com/pypa/packaging/tree/f58537628042c7f29780b9d33f31597e7fc9d664)

```powershell
git clone --depth 1 --branch 25.0 https://github.com/pypa/packaging.git .aiwork/phase4/upstream-packaging
git -C .aiwork/phase4/upstream-packaging rev-parse HEAD
& $py examples/phase4/packaging_inputs.py .aiwork/phase4/packaging-private/cases.json --seed 960431
& $py -m aiwork --config $cfg benchmark examples/phase4/packaging.toml --profile a100-qwen --profile a100-existing
& $py -m aiwork --config $cfg task verify-checkpoint ffde5b150ada4309b1f1ee6dbb2df40e --attempt 1
```

The original checkout stayed clean. Qwen Code's 12-turn trial wrote one of four deliverables before exhausting its budget. The run took 92.469 seconds and scored zero first-pass and final successes. OpenCode produced four files in its first attempt, with verification and retry interrupted by deadlines. Its recorded durations exceed the attempt budget by a wide margin. Treat them as unusable for a speed comparison. The saved checkpoint's separate replay `f6b5be775ec940a1babe600f91cbb72b` failed compilation of the generated unittest. The reviewable patch is in `.aiwork/phase4/runs/ffde5b150ada4309b1f1ee6dbb2df40e/attempt-001/proposed.patch`. The original benchmark reports are `b0fc46265f5f4379904f83ce11792729` and `d450ad15a53a49ec92bf1837175c201f` under `.aiwork/phase4/benchmarks`.

The Phase 3 Node report's public test exercises different counts, so it cannot distinguish comparator choices for equal counts. A new public counterexample derived from the written contract gives `Zebra`, `apple`, U+E000 and U+10000 equal counts. A local Node probe confirmed that code-point order, default UTF-16 string order and English locale order produce three distinct sequences. This provides an independent tie-breaker test for a future fixture revision. The historical fixture and sealed inputs were preserved.

`task verify-checkpoint` verifies the recorded candidate hash, permitted changes and verifier inventory, then creates a model-free job. It currently accepts engineering fixtures without setup recipes. Candidate verification results leave the original attempt history intact. Policy-valid incomplete work is now checkpointed for retries. Qwen Code profiles can set a bounded `harness_turns` value. The default stays at 12.

After approval for the specific remote experiments, use the following commands to measure one versus two requests on the existing lane and test failure and recovery of a disposable local SSH forward. The examples preserve the existing A100 service, profile locks and inference configuration. The live probes remain pending.

```powershell
$env:PYTHONPATH = (Get-Location).Path
& $py examples/phase4/remote_probe.py throughput --config $cfg --profile a100-existing
& $py examples/phase4/remote_probe.py recovery --config $cfg --profile a100-existing
```
