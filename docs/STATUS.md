# Status as of 2026-11-19

## Ledger specialist follow-up

| Capability | Status | Evidence |
| --- | --- | --- |
| Reviewed executable tokenizer/validator split | VERIFIED | The revised graph compiled and evaluated each owned interface, reused compatible evidence/output jobs, and revalidated model-authored tokenizer and balance sources. Linking stayed gated by incomplete public correctness. |
| Specialist repair progress | VERIFIED | Tool workers improved framing from 2/7 to 4/7, balance from 4/8 to 8/8, and validation from 12/18 to 14/18. Ranked selection rejected regressions and retained passing behavior. |
| Native ledger completion | BLOCKED | The selected framing function combines lines, the validator rejects valid numeric operands, and UBSan detects overflow in balance before its operand-range check. Public reproductions and frozen sources are preserved. |
| Complete private component grading | VERIFIED | All 24 cases completed in each replay. Tokenizer matched 24/24, framing 0/24, balanced grammar validation 16/24, and reachable balance sequences 24/24. The public sanitizer probe failed. No integrated candidate was produced. |
| Original venv process recovery | VERIFIED | Managed Windows children are assigned to an owned job before execution. Cleanup releases descendant locks and preserves a separate test job. All 71 tests passed on the original venv invocation, including the existing 67. The direct fixture passed in job `3dae93c6aee742c9b1e50cce5922fd7c`. |

See the [ledger repair report](LEDGER-REPAIR.md) for exact failures, comparison budgets, evaluator corrections and commands.

## Phase 5.1

| Capability | Status | Evidence |
| --- | --- | --- |
| Ranked iterative component repair | VERIFIED | The meter state specialist improved 5/7 to 7/7 public cases without a lost pass. The rebuilt executable passed 32/32 new sealed cases, compared with 27/32 for the archived executable on the same inputs. |
| Adaptive interface proposals and artifact reuse | VERIFIED | The local diagnostic planner proposed tokenizer and validator interfaces with changed dependencies. The review-only proposal introduced no executable authority. An approved diagnostic revision reused the verified ledger analysis, behavioral verdict and output jobs. |
| Deterministic behavioral validation | VERIFIED | Structured ledger grammar, bounds, transitions and error/output contracts matched 18 public observations and selected static evidence using zero inference requests. |
| Matched repeated local evaluation | VERIFIED | Two trials per approach on each of two unfamiliar stateful targets passed all 32 fresh sealed cases. Both approaches used the same model, source adapter, maximum request count and evaluation process. |
| Ledger reconstruction | BLOCKED | Framing and balance repeated their failed source, while syntax failed compilation in all three turns. No integrated candidate was produced. |
| Regression and offline direct fixture | VERIFIED | All 67 tests passed, including the original 64 and installed OpenCode boundary check. The direct fixture passed in job `5e42376663e34b6f8b31890c2b243078`. |

See the [Phase 5.1 handoff](PHASE51.md) for exact artifacts, controlled budgets, operator involvement and limitations.

## Phase 5

| Capability | Status | Evidence |
| --- | --- | --- |
| Nested reviewed component graphs | VERIFIED | A local model proposed the meter tree. The specialist refined one subgroup under the same registered authority. Independent checks verified both implementation components and the merged executable on the public corpus. |
| Failed-component recovery | VERIFIED | Targeted ledger retries kept the verified output component. A Docker regression test recovered a failed component and verified integration using the original unrelated artifact. |
| Held-out comparison | VERIFIED | The meter hierarchy passed 38/40 fresh sealed inputs, compared with 37/40 for ranked single-agent execution on the same reference. The retained single-agent ledger baseline passed 6/40. |
| Complete ledger reconstruction | BLOCKED | Framing, syntax and balance failed public checks. No independently verified integrated candidate was produced. |
| Windows regression and direct fixture | VERIFIED | All 64 tests passed, including the installed OpenCode workspace boundary check. The direct fixture verified in job `3e0ffe44a5f14f8a8f7f91b21155a440`. |

See the [Phase 5 handoff](PHASE5.md) for commands, metrics and artifact paths.

## Phase 4

| Capability | Status | Evidence |
| --- | --- | --- |
| Windows regression and direct smoke | VERIFIED | All 60 tests passed with offline Docker and the installed OpenCode boundary probe enabled. The direct fixture passed in job `50408bd37d904847913bf7c86aa82365`. The initial Phase 4 wheel also passed an offline installed smoke test in job `8fcb59393c8d45d8980a97ebf7084c7e`. |
| Configurable native reconstruction and separate differential grading | VERIFIED | Three self-authored ELF targets exercised stdin, argv, multi-function source and stateful input sequences. The stride candidate passed 48/48 final cases. The classifier and ledger were rejected at 44/48 and 47/48. The laptop ledger attempt produced no candidate. |
| Component isolation and integration | VERIFIED | Two Ollama workers implemented separate C functions. Both the serial and two-worker schedules independently verified and linked the components. They took 63.234 and 50.922 seconds with one laptop inference lane. |
| Independent checkpoint verification | VERIFIED | A new deterministic job replayed the original PyPA acceptance pipeline against an unchanged checkpoint. It caught a syntax error in the generated test file. |
| Autonomous external feature | BLOCKED | The first OpenCode sample read the test generator outside its workspace and is contaminated. A fresh 8K-context trial saved three of four files. Combining those files with independently verified documentation produced a reviewable patch, and the unchanged verifier rejected its generated tests during compilation. |
| OpenCode workspace boundary | VERIFIED | The installed OpenCode process read and edited staged probe files. It denied read and search operations against synthetic files in the enclosing checkout. The probe used a fake local model endpoint. A separate Ollama job `e4dd3a4086e54e3fbcff1fdb9bf797d2` edited source and passed offline verification through the isolated workspace. |
| Measured Ollama context admission | VERIFIED | The laptop reported a 4,096-token serving window during an 8,192-token harness declaration. Admission now caps the declared window when residency reports a smaller one. Regression coverage confirms an insufficient window blocks dispatch before the harness starts. |
| REA-Next static evidence import | VERIFIED | Imported the pinned Phase 3 ELF archive's matching `file`, `readelf` and `objdump` artifacts. The Phase 4 classifier campaign and matched artifact replay are recorded below. |
| Cross-plane component and increased-turn Qwen trials | UNTESTED | The follow-up authorization covered two REA-Next campaigns, a 12-request probe and test-owned SSH interruption. The separate cross-plane component and increased-turn Qwen experiments remain pending. |
| Coverage-guided or symbolic generation, PE runtime validation | UNTESTED | The new evaluator was exercised on Linux ELF command-line targets with seeded inputs. |

### Authorized A100 follow-up

| Capability | Status | Evidence |
| --- | --- | --- |
| Bounded REA-Next dispatch and receipt | VERIFIED | Two directories were allocated with the Phase 4 prefix and recorded as UID 1000, mode 0700. The first dispatch failed preflight. The second completed with no survivor. Its best compiled output passed 1/9 development and probe inputs and 1/4 campaign audit inputs. Both evidence archives were preserved. |
| A100 client throughput measurement | VERIFIED | Exactly 12 requests completed. The server reported one slot and a 131,072-token default context. All responses reached the 160-token output cap with empty visible content. Correctness was 0/12, leaving throughput for correct responses unmeasured. |
| A100 throughput with configured reasoning controls | VERIFIED | All 12 serialized requests contained both controls and returned exact correct answers. The median pair times were 1.938 seconds sequential and 1.641 seconds concurrent. The server reported one slot, 1,512 total tokens and no separate reasoning-token counts. Raw request and response bodies were preserved. |
| SSH interruption and recovery | VERIFIED | The probe stopped its owned forward. Readiness failed and the controller recorded a blocked attempt. The probe requeued the same job, which passed independent verification on the next attempt in a fresh session. |
| Native parser repairs | VERIFIED | Operator-assisted revisions passed fresh differential suites of 52/52 classifier and 55/55 ledger cases. The failed autonomous baselines remain in the evidence trail. |
| Public diagnostics and early native repair trials | VERIFIED | The controller runs the baseline diagnostic on restored checkpoints. On a matched set of 48 cases each, the autonomous classifier improved from 43 to 47 and the ledger remained at 6. A guided classifier edit matched 48/48 and then 1/4 on supplemental whitespace cases. The earlier operator-assisted revisions passed all the same inputs. Both autonomous repairs were incomplete in those trials. [Phase 4 handoff](PHASE4.md#functional-closeout) |
| Ranked native checkpoint rollback and classifier repair | VERIFIED | The autonomous classifier improved from 13/22 to 22/22 public and from 36/48 to 48/48 sealed on matched inputs. Ranked retries reject sealed inputs. A fresh ledger proposal dropped from 13/18 to 2/18 and was rolled back. [Repair reliability](PHASE4.md#autonomous-repair-reliability) |
| Autonomous ledger repair | BLOCKED | Five proposals across two local trials were rolled back. Three failed compilation and two lost previously passing public cases. The selected baseline remained at 13/18 public and passed 10/48 fresh sealed cases. |
| Local REA-Next round selection | VERIFIED | On 22 public inputs, selected round one at 17/22 over round two at 7/22. Round two lost 13 previously passing cases. The frozen round-one export independently passed 40/48 new cases. |
| Matched classifier artifact comparison | VERIFIED | On the same 52 fresh inputs, the historical Ghidra-assisted candidate matched 47, the REA-Next audit candidate matched 7, and the stronger local combined-evidence checkpoint matched 16. All three failed the final gate. |
| PyPA feature delivery | VERIFIED | The operator-assisted patch passed `git apply --check`, four focused tests and a new 32/32 sealed suite authored after the candidate freeze. The generator-derived suite is excluded from independent evidence. Autonomous completion remains unverified. [Incident review](PHASE4-INCIDENT.md) |
| REA-Next retry diagnosis | VERIFIED | The original round-one ELF and Ghidra-assisted candidate matched 47/52 cases on the identical target, Docker image and corpus. The round-two ELF matched 7/52 after adding an incorrect requirement for a second integer. |

See the [Phase 4 handoff](PHASE4.md) for commands, job IDs, limitations and report paths.

## Phase 3

| Capability | Status | Evidence |
| --- | --- | --- |
| Previously unseen engineering | VERIFIED | Eight OpenCode samples across two fixtures and two profiles passed all public and sealed checks. The matched A100 follow-up had one success and one sealed ordering mismatch per harness. [Benchmarks](BENCHMARKS.md) |
| Pause, continue and revise a plan | VERIFIED | `p3-dependencies` paused after the laptop completed the first step. Resuming exposed the missing dependency in job `118b1e4252615acd904e27d4e2d00231`. The reviewed successor `p3-dependencies-fixed` reused `6b77efc075af5657a638431679c43814`, verified a new Qwen Code step and passed independent integration in `4be94ac613175b2995eb668f1cee5d06`. The patch passed `git apply --check`. |
| Generalized self-development and retry | VERIFIED | A100 job `313c9d81880e4f099f92ea9c82ebd2a8` worked from commit `0212fa7`. The first implementation failed a new regression. The second passed the targeted test and full committed suite. The patch for trace parsing passed `git apply --check` and awaits operator review. |
| Project memory and focused staging | VERIFIED | Tests indexed 5,001 files, retrieved a scoped subset, detected a same-size and same-timestamp content change, and linked attempt evidence to its original project key. |
| Sealed verifier and worker recovery | VERIFIED | Docker test code observed a read-only workspace, absent private files and Docker socket, and loopback-only networking. A disposable Windows worker was forcibly killed while holding a claim. The controller preserved its partial artifacts and verified the next attempt. |
| Model-generated policy draft | VERIFIED | A100 artifact `482e610d22a64e6082e42ad09ed315e0.json` proposed two valid file scopes, portable unittest recipes and the dependency between the steps. Earlier laptop proposals had unsuitable recipes and scopes. Drafts remain inert until the operator creates an executable manifest and graph. |
| A100 REA-Next campaign | VERIFIED | Real campaigns ran on the existing SSH host and llama.cpp server. The longer trial `0b3b616c93524fac95c989359282b486` compiled a candidate, passed 6/10 development/probe inputs and 2/8 audit inputs, and ended `no_survivor`. Another trial exhausted synthesis turns without a candidate. |
| Ghidra on ELF | VERIFIED | Ghidra emitted a function, direct calls and decompilation from the same toy ELF in job `a6907808dc8b4b218f9e6a8662c23c78`. |
| Ghidra-assisted reconstruction | VERIFIED | A100 job `d441afb8c523479f9c2ba4f52fb4cd2e` received decompilation text and wrote fresh C. Separate Docker checks compiled it. The first candidate matched 5/8 original observations and the retry matched 8/8. This is agreement on the archived audit inputs. |
| Existing Node package repair and refactor | VERIFIED | A100 job `5bd457e9236943af9efbf4101db20c34` passed the public regression and sealed CLI checks. The laptop exhausted its retries on the release entrypoint. |
| Official REA ELF provider on Windows | BLOCKED | The pinned provider reported Linux x64 only for `inspect-binary-layout` in job `a230a9d7796f4b47ab8265fd83e0c599`. The existing PE adapter remains available. |
| Interrupted SSH, real endpoint loss and A100 parallel throughput | UNTESTED | Clean SSH forwarding and a live single lane were exercised. Forced disconnect and endpoint loss were left for a disposable environment. |
| Independent Windows installation | VERIFIED | The v0.3.0 wheel installed in a fresh Python 3.12.14 environment. Its CLI reported the version and verified the direct fixture from outside the source checkout. The Docker-enabled regression suite passed 42 tests. |

Phase 3 state and artifacts are under `.aiwork/phase3`. See the [Windows runbook](ENGINEERING.md#phase-3-operator-workflow) for setup and operation.

## Phase 2

| Demonstration | Status | Evidence |
| --- | --- | --- |
| A · Multi-file feature | VERIFIED | A100 job `0274e10d0dbe4a1bbf696b7d1be6d048` changed the parcel request model, pricing policy, service, CLI and usage page. Compilation, public pricing tests and the five-case independent insurance holdout passed. The saved patch passed `git apply --check`. |
| B · Autonomous debugging | VERIFIED | A100 job `6a8020c67d414dc39106fc78b880b786` recorded the failing baseline, repaired timestamp ties and final-page cursors, and passed the public reproducers and two private checks. Earlier laptop and A100 attempts exposed compaction failures and an unhandled full final page. |
| C · Automatic planning | VERIFIED | The controller generated and validated `parcel-release-holdouts` from a high-level objective, ran two jobs, and integrated six changed files. Integration job `6b89a1a520195d3ebf752d8509b3d56e` passed compilation, the documentation check, nine public tests and seven private tests. Pagination escalated from the laptop to the A100. The final patch passed `git apply --check`. |
| D · Multi-worker collaboration | VERIFIED | In `sensor-release`, the laptop verified `fix-units` in job `3c8ed06070855287be0bf88f85a601ed`. The A100 verified `fix-labels` in job `4a187325384054c6a2ae9157665438b0`. Job `4e99f2afc95a5a8b85182c822dbe4614` independently verified the composed report. The combined patch passed `git apply --check`. |
| E · Self-development | VERIFIED | From committed checkout `c731241`, A100 job `afa49c08c7f34087b84e0a7f7bf7897d` proposed plain-import indexing and a new test file. The Git-equipped Linux runner executed 33 tests with one nested-Docker test skipped. The patch passed `git apply --check` on the source checkout and is available for review. |
| Docker runner and offline dependencies | VERIFIED | Docker Desktop Linux engine 29.9.3 ran Phase 2 command and verification copies. A test installed a self-authored wheel into a disposable copy and checked that the only network interface was loopback. |
| Windows regression suite and package | VERIFIED | `python -m unittest discover -s tests -q` passed all 32 tests with `AIWORK_TEST_DOCKER_IMAGE` set to the configured Python image. AI Workspace 0.2.0 installed into a separate environment and verified a direct task using its packaged CLI. |

The earlier parcel plan passed public integration in `parcel-release-covered`. A subsequent full holdout run, `ee672c0f71dd4398a8852cf490141171`, rejected missing insurance validation and output fields. The controller now includes the parent objective in each subtask and the release manifest requires both holdouts. The new `parcel-release-holdouts` run passed that stronger gate.

See [Engineering mode](ENGINEERING.md) for the start commands, protected test setup and patch review.

## Phase 1

| Gate or integration | Status | Evidence |
| --- | --- | --- |
| A · Controller and local install | VERIFIED | Windows Bootstrap installed a wheel into a fresh Python 3.12.14 environment. CLI help, doctor, direct task, SQLite evidence and unit tests executed. |
| A · Retry and provider error tests | MOCKED | Simulated model failure and escalation, Lambda accept/reuse, no capacity, ambiguous transport, rate limit and scope-checked termination. |
| B · Laptop OpenCode | VERIFIED | RTX 5070 Laptop measured 8,151 MiB total. Ollama exposed `qwen3.5:9b` Q4_K_M. The tuned profile edited source, ran MCP tests and passed independent tests. Benchmark job `316f5a3ad8d547e29f3007d449d96b88`. |
| C · Existing A100 | VERIFIED | `ssh aisak` authenticated noninteractively as `ubuntu` and reported A100-SXM4-40GB. The configured tunnel reached the llama.cpp model and OpenCode passed the same task. Benchmark job `ab9976d6ad6c46aab9c7590818d95dc9`. |
| C · Lambda launch and bootstrap | BLOCKED | Public OpenAPI 1.10.0 checked. Launch and termination tested with doubles. Live operations require separately configured Lambda credentials, existing storage, trusted SSH enrollment and opt-in policy. No billable lifecycle action exercised. |
| D · Native reconstruction | VERIFIED | MSVC compiled the self-authored PE fixture. Ghidra 12.1.4 emitted function evidence. The A100-generated function passed source preflight, compiled and matched 182 differential inputs. Job `afd1e637ac384e7ba971c32387db4367`. |
| D · Official REA | VERIFIED | Pinned REA 6.7.0 ran `inspect-pe-resources` through the specialist adapter and returned structured evidence on the toy PE. Job `5ce304e139534091815ec771fc233a7f`. |
| D · REA-Next MCP bridge | VERIFIED | Inner REA-Next CLI’s read-only `probe-mcp` reported 207 installed tools and all 20 tools selected by the native profile. |
| D · REA-Next campaign dispatch | VERIFIED | Phase 3 created and executed a bounded campaign and exported structured evidence. See the Phase 3 campaign row for its verdict. |
| E · Real benchmarks | VERIFIED | One matched fixture per profile. Laptop 26.469 s and A100 18.688 s. On the same A100 model at matched settings, OpenCode took 13.640 s and Qwen Code 14.234 s. All four samples passed independent tests. [Benchmarks](BENCHMARKS.md) |
| Cross-plane task graph | VERIFIED | `workflow examples/multi-agent.toml --id live-cross-plane --workers 2 --trusted` ran both model jobs and verified their artifact handoff. Journal at `.aiwork/workflows/live-cross-plane/workflow.json`. |
| Windows background controller | VERIFIED | PowerShell start and status reported a live worker. It consumed a separately submitted direct job `31335729286e45659bacf7eafabfe4fe` and exited after the stop marker. |
| Qwen Code 0.27.4 | VERIFIED | With the measured 131,072-token serving context and scoped edit and MCP approvals, the A100 fixture edited source and passed the public and independent tests. Job `f246f2b721b34c65a62ff4e82135825e`, 17.250 s. Earlier runs exposed one-token requests and tool permission denials. |
| Docker verification during Phase 1 | BLOCKED | The Linux engine pipe was unavailable during initial validation. Phase 2 subsequently verified the runner. |
| Ubuntu CI, vLLM and DeepSeek-specific harness | UNTESTED | CI workflow and OpenAI-compatible engine profile are supplied. A DeepSeek-specific harness adapter is pending. |

## Commands and outputs

- **VERIFIED** · `scripts/Bootstrap.ps1 -Python <installed-python3.12.exe>` installed AI Workspace, then doctor reported Python, the laptop GPU, OpenCode and SSH. Run `aiwork models` to discover each profile’s current server inventory.
- **VERIFIED** · `aiwork task run examples/direct.toml --trusted` selected the deterministic worker and verified exact output. Run `aiwork runs 66678159bc6541e28698ace70aabe235` to inspect that first smoke run.
- **VERIFIED** · `python -m unittest discover -s tests -v` passed 22 automated tests on Windows, including real local subprocess fixtures and mocked provider responses.
- **VERIFIED** · `aiwork --config aiwork.example.toml benchmark examples/coding.toml --profile laptop-ollama --profile a100-existing --trusted` produced the two successful samples and a JSON report.
- **VERIFIED** · `scripts/NativeDemo.ps1 -GhidraHeadless <analyzeHeadless.bat>` ran Ghidra, source preflight, compilation and 182 finite input comparisons.
- **VERIFIED** · `scripts/ReaDemo.ps1 -ReaEntry <rea.mjs>` ran the pinned official REA adapter. `python -B -m reanext.cli probe-mcp --profile native --timeout 30` exercised the existing REA-Next MCP integration.
- **VERIFIED** · `aiwork --config config/qwen.example.toml task run examples/coding.toml --profile a100-qwen --trusted` ran the alternate harness against the existing private A100 endpoint.
- **BLOCKED** · Run `aiwork --config config/lambda.local.toml a100 plan` after completing the prerequisites in [Next steps](NEXT_STEPS.md#lambda-managed-profile). Confirm Docker Desktop’s server responds to `docker version` before configuring `verification_image`.
