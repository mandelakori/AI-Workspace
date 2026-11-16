# Benchmarks

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
