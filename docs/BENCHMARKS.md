# Benchmarks

## Phase 3 repeated engineering trials

Each trial started from the same staged source and ran public tests followed by sealed stdin/stdout cases. The suite tested an unseen multi-file Python API and CLI, and a CommonJS report API with case-sensitive ordering. The laptop ran OpenCode 2.0.27 with Ollama Qwen3.5 9B Q4_K_M and a 4,096-token context. The A100 ran OpenCode with the existing llama.cpp Qwen3.6 35B-A3B Q6_K profile, a 131,072-token context and a 3,072-token output budget. Thinking was disabled.

| Fixture | Profile | First pass and final | Wall time per trial |
| --- | --- | --- | --- |
| Python readings | Laptop OpenCode | 2/2 | 44.141 s, 34.406 s |
| Python readings | A100 OpenCode | 2/2 | 24.516 s, 22.266 s |
| Node report | Laptop OpenCode | 2/2 | 64.594 s, 35.203 s |
| Node report | A100 OpenCode | 2/2 | 77.719 s, 49.032 s |

The first suite overlapped planning and includes queue time. In OpenCode's reported events, the highest individual input was 3,201 tokens on the laptop and 3,819 on the A100. The GPU reported 8,151 MiB total on the laptop and 40,960 MiB on the A100. Post-harness free memory was 318 MiB and 10,144 MiB, respectively. These are device snapshots. The reports preserve each sample's token counts, duration and verdict. Each suite sample had one attempt.

Suite report `.aiwork/phase3/suites/02ef758d5d214eaa80944095422a70d2/report.json`. Fixture reports `.aiwork/phase3/benchmarks/f1c439dd1d704e33bd8e8c59b9486396/report.json` and `.aiwork/phase3/benchmarks/30130d40827546d29135466197aec46e/report.json`.

### Same model and hardware, two harnesses

The follow-up held the Node fixture, Windows host, Docker runner, A100, loaded model and generation settings constant. Each harness had two first-pass trials.

| Harness | First pass and final | Wall time per trial | Reported input / output totals by trial |
| --- | --- | --- | --- |
| OpenCode 2.0.27 | 1/2 | 16.08 s pass, 19.14 s fail | 5,344 / 426 and 5,545 / 489 |
| Qwen Code 0.27.4 | 1/2 | 23.83 s fail, 20.50 s pass | 60,460 / 1,126 and 51,219 / 1,025 |

Both failures passed public tests and used locale-aware ordering, which disagreed with the sealed case. Both harnesses also produced correct implementations. Input counters follow the harness's conventions for cached tokens. The earlier contested comparison had one verified sample per harness and two deadline-related attempts. Report IDs are `06c52085d61b4f4590061d0027a44585` and `254dbe6e60524e19b98f6a48a4114105` in `.aiwork/phase3/benchmarks`. These trials are too small to select a universal default or estimate sustained parallel throughput.

```powershell
$ai = '.\.venv\Scripts\aiwork.exe'
$cfg = 'config/phase3.example.toml'
& $ai --config $cfg benchmark examples/phase3/suite.toml --suite --profile laptop-ollama --profile a100-existing --repeats 2
& $ai --config $cfg benchmark examples/phase3/node-report.toml --profile a100-existing --profile a100-qwen --repeats 2
& $ai --config $cfg benchmark examples/phase3/suite-extended.toml --suite --profile laptop-ollama --profile a100-existing --repeats 2
```

The extended suite adds an ESM/CommonJS package repair and parser refactor with public regression checks and independent cases. Use a separate private case directory if tools or agents can read repository-wide files. Keep concurrent work off the inference lane when estimating profile timing.

## 2026-11-16 OpenCode coding comparison

Both profiles ran the same Fahrenheit-to-Celsius bugfix from a fresh copy of the same fixture. The agent read and edited source, ran the public MCP check, and the controller independently reran all four unit tests. Each profile ran once. Wall time includes routing, harness execution, SSH forwarding where applicable, and verification. Token totals are the values reported by OpenCode events.

| Profile | Model and runtime | Verified | Wall time | Input / output tokens | Public MCP checks |
| --- | --- | --- | ---: | ---: | ---: |
| laptop-ollama | RTX 5070 Laptop, Ollama, Qwen3.5 9B Q4_K_M, 4096 context, thinking off | 1/1 first pass | 26.469 s | 3,200 / 299 | 1 |
| a100-existing | A100-SXM4-40GB, llama.cpp, existing Qwen3.6 35B-A3B Q6_K derivative | 1/1 first pass | 18.688 s | 3,389 / 579 | 1 |

Report: `.aiwork/benchmarks/09d1257aeb3241d38617154402f8598e/report.json`. Jobs: `316f5a3ad8d547e29f3007d449d96b88` and `ab9976d6ad6c46aab9c7590818d95dc9`.

The earlier comparison recorded an A100 success at 28.516 s and a laptop timeout at 240.469 s under the earlier laptop configuration. See `.aiwork/benchmarks/41a5580ed3e2438cb7c85ff37cbe8e83/report.json`. A one-fixture comparison with two different models and runtimes cannot isolate a hardware effect or estimate sustained throughput.

## 2026-11-16 A100 harness comparison

Both harnesses used the same llama.cpp server, loaded Q6_K model, 131,072-token context, 3,072-token output budget, fixture and independent checks. Thinking was disabled. Each profile ran once and completed its MCP check.

| Harness | Independently verified | Wall time | Reported input / output tokens |
| --- | --- | ---: | ---: |
| OpenCode 2.0.27 | 1/1 first pass | 13.640 s | 3,650 / 474 |
| Qwen Code 0.27.4 | 1/1 first pass | 14.234 s | 47,926 / 600 |

The harnesses report token usage differently, including cached inputs. The table preserves each harness’s reported values. Report: `.aiwork/benchmarks/bfefa1dba7a844fca1f0c768f4f6e38e/report.json`.

## Reproduce and extend

```powershell
.\.venv\Scripts\aiwork.exe benchmark examples/coding.toml --profile laptop-ollama --profile a100-existing --repeats 3 --trusted
.\.venv\Scripts\aiwork.exe --config config/qwen.example.toml benchmark examples/coding.toml --profile a100-opencode-matched --profile a100-qwen --repeats 3 --trusted
```

Add uniquely named profile entries for alternative contexts, quantizations, harnesses or engines after inventory reports their exact model IDs. The report records profile settings, fixture hashes, runs, first-pass and verified counts, blocked jobs, p50/p95 and a wall-time-derived completions/hour rate. Keep `repeats` greater than one for a latency distribution. Configure `seed` only where the engine supports it. Use an independent protected evaluator for adversarial holdouts. Per-token inference throughput and peak GPU measurements are pending.
