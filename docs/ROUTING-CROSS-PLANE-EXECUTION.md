# Cross-plane comparison stopped on local cold start

The repeated preflight on 2026-11-24 passed for both original manifests from
`442cb06`. The pinned Docker image, frozen inputs and implementation, OpenCode,
local calibration and model blobs, and A100 model identity matched. At preflight,
the laptop had 7.71 GiB of free VRAM and 10.58 GiB of available RAM against the
frozen requirements of 6.63 and 7.06 GiB. A100 reported one idle 131,072-token
slot and closed its read-only forwarding session. No settings changed.

## Local arm

The local controller admitted the 16,384-token run and started its owned
Ollama server. The required scoped tools were present on the first provider
request. The forwarded payload used a 1,536-token ceiling, reasoning OFF,
temperature 0 and seed 1729. Ollama failed during model initialization and
returned HTTP 500 with `timed out waiting for llama-server to start`. Its
server log ended the model load during runner warm-up. This happened inside
the approved work deadline. No usable model response or token receipt was
returned. OpenCode attempted to resend the same request, and the provider
latch rejected it before forwarding.

| Measurement | Local result |
| --- | --- |
| Lane wait | 0.016 s |
| Warm preflight phase | 1.829 s |
| Owned Ollama startup to ready listener | About 18.232 s, observed by a 100 ms passive poll |
| Admission receipt after work start | About 19.733 s |
| First provider response | HTTP 500 after 51.594 s at the relay, about 74.187 s from work start |
| OpenCode harness | 56.984 s, exit 1 |
| Work phase and container cleanup | 77.703 s of work and 8.640 s of cleanup, both separately accounted |
| Complete local command | About 95.555 s, including pre-dispatch checks and phase cleanup |
| Resource use | 1 forwarded request, 1 blocked resend, 0 of 20 MCP operations, 0 compactions |
| Prompt, completion and reasoning tokens | Unreported |
| First accepted edit and public check | None |
| Public and independent correctness | Ungraded, no candidate freeze |

The runtime logged 29 of 33 layers offloaded to GPU and a 4,272.54 MiB
CUDA model buffer. Before and after the harness, it reported 7,891 MiB free
VRAM and no resident Ollama model. The peak RAM and VRAM during startup were
unmeasured. Relay, Ollama and container cleanup passed. The trial was not
quarantined. The work phase failed and its one-shot local grant was consumed.
After the provider failure, the frozen wrapper also raised `FileNotFoundError`
while reading the absent MCP transcript. The earlier provider receipt and
server log preserve the primary failure independently of that reporting error.

## A100 arm and scope

The A100 arm was held because local work did not meet the original completion
gate. Its grant remains unused. There were no A100 inference requests and no
live engineering or grading times to compare. The result exposes a local
cold-start failure after successful memory admission. It neither establishes
model engineering capability nor supports a GPU performance comparison. The
paired run stopped with no retry, fallback, or modification of the frozen
protocol or remote services.

[Execution evidence](evidence/routing-cross-plane-execution/README.md)
