# Status as of 2026-11-16

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
| D · REA-Next campaign dispatch | UNTESTED | External argv boundary exists. Campaign creation, execution and export are pending. |
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
