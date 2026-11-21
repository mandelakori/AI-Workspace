# Adaptive local execution and experimental Pi integration

Implemented on `phase61/autonomous-completion`, starting at `c37a210`. OpenCode
remains the reference. Pi is experimentally admitted after installed inert-provider
conformance; its real-model engineering performance remains **UNTESTED**. No live
engineering comparison was dispatched. Calibration is a separate synthetic
capacity measurement, not an autonomous engineering result.

## Measured capacity — VERIFIED

Existing Ollama 0.40.16, Qwen3.5-9B Q4_K_M, RTX 5070 Laptop (8151 MiB),
31.12 GiB visible RAM. Each context used a fresh private server, copied existing
model bytes, one load-only request and two streamed 128-token generations.
Temperature 0, seed 1729, `think:false`, one inference lane, flash attention,
f16 KV and 512 MiB engine GPU overhead. The six generation calls completed in
369.234 seconds including model copying/loading and all three context probes.

| Window | Long prompt tokens | Long prefill tokens/s | Short / long generation tokens/s | Long first-token seconds | GPU / total layers | KV total MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 8192 | 6183 | 2013.24 | 25.99 / 37.53 | 3.156 | 31 / 33 | 256 |
| 16384 | 12327 | 1612.07 | 21.72 / 28.56 | 7.781 | 29 / 33 | 512 |
| 32768 | 24615 | 1293.44 | 17.79 / 17.85 | 19.188 | 26 / 33 | 1024 |

8K KV was entirely GPU-resident. 16K split 448 MiB GPU / 64 MiB CPU; 32K split
896 / 128 MiB. Total KV growth was 32 KiB/token. Server layer-offload evidence
shows 2, 4 and 7 layers remaining on the CPU respectively.

| Window | Peak global GPU increment GiB | Observed available-RAM decrease GiB | API resident total / VRAM GiB | Load seconds | First short-prefill TTFT seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8192 | 6.084 | 0.899 | 5.947 / 5.077 | 51.25 | 41.859 |
| 16384 | 6.130 | 5.062 | 6.223 / 5.022 | 49.39 | 47.859 |
| 32768 | 6.306 | 0.000* | 6.832 / 5.183 | 45.16 | 32.438 |

Global GPU/RAM deltas include unrelated desktop activity. *32K's zero RAM decrease
was masked by unrelated reclamation; it is not zero model RAM. Admission retains
the maximum smaller-window RAM measurement and a resident CPU footprint floor.
Load times come from server HTTP logs because the load-only API omitted
`load_duration`. The first short prefill incurred substantial extra latency;
its internal cause was not independently profiled. The dataset records this
observed overhead rather than assuming all requests achieve warm throughput.

All six native responses reported zero cached prompt tokens, visible output and
128 generated tokens: **46224 prompt + 768 output = 46992 total tokens**.
No visible thinking was returned. A separate reasoning-token
counter was unavailable. Repetitive filler exercises allocation and throughput;
these measurements establish neither useful long-context comprehension nor code
correctness. One short/long pair per window is not a robust throughput estimate.

64K was **NOT RUN**: projected GPU use plus the 512 MiB margin exceeded observed
free VRAM by about 108 MB. The conservative gate withheld the probe; it does not
prove 64K impossible. No model download, original-store write, shared-server
restart, application closure or RAM clearing was performed. Each private listener
was PID-checked and its Windows job cleaned up. Shared PID 23348 and its empty
resident-model inventory were preserved.

## Admission and operation — VERIFIED with stated limits

`local_runtime.py` adds opt-in SHA-pinned calibration to local Ollama profiles.
The controller picks the smallest **measured** window satisfying full observed
input, output/reserve tokens, current RAM/VRAM headroom and estimated cold-request
latency. Profile `context` is an operator maximum; no universal 8K production cap
is imposed. Unmeasured, stale or unavailable telemetry fails admission. A
calibrated profile uses an owned private server with the calibrated engine
settings, not the shared endpoint. Served context is checked again after work.

For the recorded 7440-token task demand plus 2048 output and 512 reserve tokens,
8K is too small. 16K is the smallest qualifying window with a 280-second inference
allowance; 130 seconds admits none. Memory availability is sampled again at run
time. Latency estimates are conservative single-request estimates, not a guarantee
that an arbitrary engineering loop completes. Absolute deadlines and durable
tool/model quotas still enforce total execution bounds. No automatic CPU/GPU
retuning occurs; offload is measured from the existing engine.

`Task.context_input_tokens` must represent observed **full** input, including
cached source, contracts and tool definitions, not only uncached billing tokens.
The runtime refuses a missing observation. Dynamic token prediction and automatic
mid-session server resizing are **UNTESTED / not implemented**. The existing
context planner also accepts explicit resource/latency measurements without
starting inference.

```powershell
# From the repository; no Codex or proprietary API is required.
.\scripts\Install-Pi.ps1
.\.venv\Scripts\python.exe -m aiwork --config examples/adaptive-local.toml harnesses
.\.venv\Scripts\python.exe -m aiwork --config examples/adaptive-local.toml models
# Review a future calibration plan; this command does not load a model.
.\.venv\Scripts\python.exe -m aiwork local-calibrate .aiwork/new-calibration --source "$env:USERPROFILE/.ollama/models"
```

Only adding `--apply` executes a new calibration. Existing measurements need not
be repeated. The preserved `.aiwork/adaptive-local/calibration/model-store` is
local, independently copied model data; it is not committed. The example profiles
require that local bundle. Moving/recreating calibration requires reviewed paths
and updated hashes, not editing the frozen dataset in place.

## Pi SDK boundary — VERIFIED with inert provider

Pinned `@earendil-works/pi-coding-agent@1.6.0`; Node 24.21.0 was used (minimum
22.19). `scripts/Install-Pi.ps1` installs the frozen npm lock with lifecycle scripts
disabled beneath `.aiwork`; it refuses an unknown existing dependency tree.
The installer existing-version path and installed SDK were exercised. A fresh
`npm ci` through that script is **UNTESTED**; the original pinned npm installation
and package-lock are preserved.

The SDK receives an empty resource loader, in-memory settings/session, disabled
builtin tools, no project/user extensions or prompts, no provider discovery,
telemetry or cache warming, and zero automatic retries. Exactly four controller
MCP tools are registered: source focus, exact hash edit, approved public check,
and diff. Native shell, mutation and file-read tools are absent. Trusted SDK
requests may reach only the controller's owned loopback provider gate.

Pi 1.6 carries tool declarations in `TranscriptContext` system deltas. The bridge
replays those declarations before attesting request purpose. Every engineering
request must advertise exactly the scoped catalog; tool-free compaction is allowed
only as a trusted maintenance request after a valid primary request. Persistent
contracts, epochs, exact hashes, category quotas and cancellation use the same
controller implementation as OpenCode. Raw requests/responses, Pi events, MCP
processes and normalized execution receipts are preserved.

Six installed conformance tests cover rejected-anchor and stale-hash recovery,
outside-scope read/write rejection, public testing, **two actual SDK compactions**,
source retention versus eviction/reinspection, clean exhaustion, missing catalog
before provider dispatch, streaming cancellation, and cancellation of a nested
test process while releasing its file lock. These are scripted inert-provider
tests, **not model-authored repairs**. Both adapters produce the same controller
receipt schema; independent verification remains a separate field and authority.

Cancellation testing found a real Windows relay defect: socket shutdown left a
buffered provider read blocked. The relay now polls cancellable direct reads
within the original deadline; a slow-prefill regression verifies that polling
does not shorten it. No ownership/cleanup errors are suppressed. HTTPS transport
with this reader is **UNTESTED**; the local HTTP validation path passed.

Early failed Pi attempts (integer timeout, transcript/catalog assumptions,
retained-source compaction expectation and blocked relay cleanup) remain in the
evidence. The exact editor implementation was not weakened or rewritten.

## Verification and next comparison

The baseline 162 regression tests passed before changes. The final **178/178**
passed in 141.868 seconds with installed inert OpenCode/Pi, offline Docker and no
skips. An offline wheel build succeeded and includes the Pi bridge. The first
non-isolated wheel attempt failed because the development venv lacked setuptools;
the successful build used existing cached build wheels without network access.
Capability/context/resource receipts are in [preserved evidence](evidence/adaptive-local/).
The [new comparison review](LOCAL-HARNESS-COMPARISON-REVIEW.md) fixes model, context,
source, verifier and resource limits. It remains **PREPARED_NOT_AUTHORIZED**.
There is no live Pi/OpenCode comparison result, autonomous feature-completion
claim, hierarchy claim or new sealed suite in this implementation phase.

Primary interface references: [Pi 1.6 SDK](https://github.com/earendil-works/pi/blob/v1.6.0/packages/coding-agent/docs/sdk.md),
[full-control example](https://github.com/earendil-works/pi/blob/v1.6.0/packages/coding-agent/examples/sdk/12-full-control.ts),
[Ollama context configuration](https://docs.ollama.com/context-length),
[memory/cache options](https://docs.ollama.com/faq),
[generation API](https://docs.ollama.com/api/generate),
[resident-model API](https://docs.ollama.com/api/ps),
[OpenAI-compatible thinking controls](https://docs.ollama.com/api/openai-compatibility).
The engineering arms send `reasoning_effort:none`; Ollama documents that as false
for Boolean thinking models. That field is checked in inert provider requests;
the new arms' actual server output remains untested until authorization.
