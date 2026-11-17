# Phase 4 engineering handoff

Run these commands from the AI-Workspace checkout using Windows PowerShell. The examples use the existing Python 3.12 install, local Linux Docker image, Ghidra installation and configured open-weight profiles. The controller can also be installed with [Bootstrap.ps1](../scripts/Bootstrap.ps1).

```powershell
$py = '.venv/Scripts/python.exe'
$cfg = '.aiwork/phase4.local.toml'
$env:AIWORK_TEST_DOCKER_IMAGE = 'aiwork-engineering:phase3'
$env:AIWORK_TEST_OPENCODE_BOUNDARY = '1'
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

The directories are under `.aiwork/phase4/native`. Each `run.json` links to the controller job, which holds harness traces, source and patches. The independently graded results support agreement only for the tested invocations. The parser diagnosis and revised candidate reports appear in the follow-up below. Lengthier sessions, other environments, execution through a PE-compatible runner, raw binary input protocols, side effects and untested error paths remain outside demonstrated coverage. No coverage-guided or symbolic engine was exercised.

`native run --rea-archive <archive> --evidence ghidra --trusted` adds static listings from a REA-Next archive after checking the exact target hash and the listing hashes. Its importer reads selected static entries. Campaign audit observations remain in the operator archive. With an authorized existing remote checkout, `campaign <fixture.toml>` accepts either a prebuilt ELF or flat sources and an offline build argv that produces `program`, development and audit JSONL, and `[input]` with stdin or file transport and fixed argv. The Phase 3 directory input still works. A prepared prebuilt classifier descriptor for this checkout lives at `.aiwork/phase4/rea-bucket/campaign.toml`. The new transport was exercised in staging tests. The authorized dispatch and classifier comparison appear in the follow-up below.

## Independent functions and scheduling

```powershell
$env:PYTHONPATH = (Get-Location).Path
& $py examples/phase4/component_benchmark.py --config $cfg --local-only
```

The two workers each receive an interface and a small approved compile recipe. Independent checks verify each implementation. The dependency journal carries both sources to a separate link and integration job that checks 501 inputs and both integer extremes. Both serial and two-worker trials passed in report `.aiwork/phase4/component-benchmarks/cbdb1f89c20e4e60/report.json`. This is one paired sample, with host overlap and one serialized Ollama lane. The same script can run the separate laptop and A100 profiles after explicit authorization. The A100 client submission experiment appears in the follow-up below.

Workflow handoffs now compare the bytes staged for a dependent job against the upstream verifier's recorded SHA-256 digest. A regression test changes an upstream artifact after verification and confirms the dependent job is rejected before dispatch. Legacy direct outputs without inventories remain readable.

## External repository and recovery

The benchmark uses PyPA packaging tag `25.0` at commit `f58537628042c7f29780b9d33f31597e7fc9d664`. The requested feature adds a dependency-policy library, a JSON CLI, tests and usage documentation. It checks duplicate requirements, canonical-name ordering with stable ties, markers, version constraints and invalid input. [PyPA packaging source at the pinned revision](https://github.com/pypa/packaging/tree/f58537628042c7f29780b9d33f31597e7fc9d664)

```powershell
git clone --depth 1 --branch 25.0 https://github.com/pypa/packaging.git .aiwork/phase4/upstream-packaging
git -C .aiwork/phase4/upstream-packaging rev-parse HEAD
& $py examples/phase4/packaging_inputs.py .aiwork/phase4/packaging-private/cases.json --seed 960431
& $py -m aiwork --config $cfg benchmark examples/phase4/packaging.toml --profile a100-qwen --profile a100-existing
& $py -m aiwork --config $cfg task verify-checkpoint ffde5b150ada4309b1f1ee6dbb2df40e --attempt 1
```

The original checkout stayed clean. Qwen Code's 12-turn trial wrote one of four deliverables before exhausting its budget. The run took 92.469 seconds and scored zero first-pass and final successes. The first OpenCode trial is contaminated. Its trace recorded a read of the operator-side oracle generator outside the staged workspace, and its generated unittest copied a sealed stimulus. Its saved checkpoint also failed compilation during independent replay `f6b5be775ec940a1babe600f91cbb72b`. A laptop repair of that candidate timed out without validated edits. The original benchmark reports are `b0fc46265f5f4379904f83ce11792729` and `d450ad15a53a49ec92bf1837175c201f` under `.aiwork/phase4/benchmarks`.

OpenCode now runs in a task copy outside any enclosing Git worktree with an explicit deny for external directory access. The installed-harness boundary test uses synthetic data and a local scripted endpoint to check that read and search tools reject outside files and a permitted edit survives. The test exercises the configured tool policy. An OS account or VM is still needed for kernel isolation of hostile harness binaries. [OpenCode directory permissions](https://opencode.ai/docs/permissions/#directories)

A fresh laptop trial with the hardened boundary generated no edits in two attempts. It took 93.984 seconds and is recorded at `.aiwork/phase4-boundary/benchmarks/2367737fc8304c778de29b841c0f1e52/report.json`. Ollama reported a 4,096-token server window throughout the run. The trial's 8,192-token harness declaration did not increase the server window. Admission now uses the reported resident-window limit and records both values.

The reviewed four-step plan `.aiwork/phase4-boundary/plans/packaging-decomposed-v2/result.json` verified the usage documentation. The library step produced no edits, so its CLI and test dependents waited for a verified library artifact. The acceptance suite and upstream checkout remained unchanged. The first planning manifest had an invalid Python snippet in its CLI smoke command. It was stopped and superseded by the syntax-checked v2 manifest before that command ran.

An additional local alias, `aiwork-qwen35-phase4:8k`, reuses the installed `qwen3.5:9b` weights. Ollama reported an 8,192-token resident window. The base weights and alias remain available. The saved Modelfile is at `.aiwork/phase4-boundary/Modelfile`, with the benchmark profile in `.aiwork/phase4-resident8k.local.toml`. [Ollama context configuration](https://docs.ollama.com/api/openai-compatibility#setting-the-local-context-size)

The 8K trial's first checkpoint contained the library, CLI and test file. Independently combining it with the verified documentation artifact generated a four-file patch that passed `git apply --check`. The original acceptance pipeline rejected this assembled candidate at compile time. The package's generated tests contained a Python syntax error. The assembly inputs and patch are in `.aiwork/phase4-boundary/package-assembly/02aec663f3244981a962c7bb5793a011`. Its verification job is `d9457c052ff64d80b94db17561a3302c`. The operator reviewed the task graph and selected the two artifacts. The generated source and fixed acceptance checks went into the assembly unchanged.

The automatic 8K retry carried forward the checkpoint and again ended with three of four deliverables. Its test file has the same digest as the one rejected during assembly. The two attempts took 651.469 seconds in report `.aiwork/phase4-boundary/benchmarks/8c6c94abb58b433db9556ff1f76dacb8/report.json`. That report's older classification groups incomplete deliverables with empty candidates. The per-attempt paths and patches record the three generated files.

The final wheel installed offline in a fresh Windows Python environment and verified the direct fixture from outside the source checkout. It is under `.aiwork/phase4-boundary/final-release/wheel`, with SHA-256 `73059a38f3097948e27c85f8bda9cfc8ac8ee3d1f553560d970546d5d1276319`.

The Phase 3 Node report's public test exercises different counts, so it cannot distinguish comparator choices for equal counts. A new public counterexample derived from the written contract gives `Zebra`, `apple`, U+E000 and U+10000 equal counts. A local Node probe confirmed that code-point order, default UTF-16 string order and English locale order produce three distinct sequences. This provides an independent tie-breaker test for a future fixture revision. The historical fixture and sealed inputs were preserved.

`task verify-checkpoint` verifies the recorded candidate hash, permitted changes and verifier inventory, then creates a model-free job. It currently accepts engineering fixtures without setup recipes. Candidate verification results leave the original attempt history intact. Policy-valid incomplete work is now checkpointed for retries. Qwen Code profiles can set a bounded `harness_turns` value. The default stays at 12.

The approved A100 probes use the following commands. A fresh run is a separate experiment with its own authorization and request budget.

```powershell
$env:PYTHONPATH = (Get-Location).Path
& $py examples/phase4/remote_probe.py throughput --config $cfg --profile a100-existing
& $py examples/phase4/remote_probe.py recovery --config $cfg --profile a100-existing
```

## Authorized follow-up

The two classifier campaigns used the same prebuilt reference ELF, existing REA-Next installation and cached sandbox image. Launches were limited to two. The paths remain available on `aisak` for inspection. Both were owned by `ubuntu` (UID 1000) with mode `0700`. Each local `dispatch.json` records the path, owner, device, inode and image.

| Campaign | Remote directory | Controller outcome |
| --- | --- | --- |
| `50c269b426ec44c6abc7301a1abb5869` | `/tmp/aiwork-p4.WXo4fh0s` | Non-root sandbox worker could not execute the uploaded ELF. Preflight failed. |
| `71a0ea71bf5247298523ab1a79b13c18` | `/tmp/aiwork-p4.AviOYr3M` | Changing the staged ELF to mode `0555` resolved preflight. The campaign finished in 31.094 seconds. Its best compiled output passed 1/9 development and probe inputs, then 1/4 audit inputs. Final decision `no_survivor`. |

The [throughput probe report](../.aiwork/phase4/remote-probes/74b31f81811c4133aca0dd3e666c26ee/report.json) records six two-request batches, three for each submission mode. The server advertised one slot and a 131,072-token default context. Median pair completion time was 2.656 seconds sequential and 2.578 seconds concurrent. The corresponding median individual latencies were 1.328 and 1.961 seconds. Across all 12 requests the server reported 390 prompt tokens and 1,920 completion tokens. All responses reached the 160-token completion cap without visible answers, so correctness was 0/12. Throughput for correct answers remains unmeasured. The probe now applies the profile's reasoning options and records finish reasons, with the 12-request limit covered by a mock regression. A live rerun requires a fresh request budget.

The [recovery report](../.aiwork/phase4/remote-probes/5ee877d1823a4ec99e9da962325ad0fe/report.json) records the test PID, owned SSH process handle, command, and failed loopback readiness after termination. The first attempt was blocked. The probe requeued the same job `e163566ebd2e4e588b854ce4a25e6405` and the next attempt passed independent verification. Total elapsed time was 26 seconds.

The classifier's original candidate accepted trailing non-whitespace after the integer and rejected an otherwise valid value ending at EOF. The ledger accepted trailing arguments to `show` and `reset`, treated blank lines as errors, and used a larger line buffer. The operator-assisted revisions passed 52/52 and 55/55 fresh inputs, respectively. The new suites exclude the exact historical final stimuli and, for the classifier, the campaign audit inputs. The fresh suites, revised sources, parent hashes and per-case reports are under `.aiwork/phase4-followup/native-parser`.

The [classifier comparison](../.aiwork/phase4-followup/comparison/results.json) used the same reference ELF and the same 52 new inputs. The historical Ghidra-assisted candidate matched 47/52. The hash-verified executable from the REA-Next audit matched 7/52. The local OpenCode run with both Ghidra and REA-Next static evidence compiled two candidates. They passed 2/5 and 0/5 development cases. The stronger development checkpoint matched 16/52 on the common final suite. The last checkpoint matched 0/52 and used the wrong upper clamp, score bands and error stream. These are artifact comparisons across different generation workflows and model configurations. They cannot isolate the effect of either specialist.

The [PyPA patch](../.aiwork/phase4-followup/pypa-assisted/proposed.patch) adds the library, CLI, tests and usage documentation in a separate copy of the pinned checkout. It passed `git apply --check`, compilation, the original public check, four focused unittests and 18/18 preserved sealed cases. This was an operator-assisted implementation. Prior autonomous attempts and the original upstream checkout were preserved. The verification job is `6ef1d9da4f1c46aaade89237a5d9306a`.

```powershell
& $py -m aiwork --config $cfg task run .aiwork/phase4-followup/pypa-assisted/verify.toml
```
