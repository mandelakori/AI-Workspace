# Cross-plane execution result

This is the first, pre-dispatch observation. The later
[execution record](ROUTING-CROSS-PLANE-EXECUTION.md) supersedes its grant state.

On 2026-11-24, the approved comparison from `442cb06` stopped at local
admission. Both frozen manifests, the scoped permissions, the implementation
and input hashes, the pinned OpenCode and offline Docker verifier, and the
model identities matched. The local calibration and model manifest and blobs
also matched. Neither authorization was consumed. Neither arm created a worker
session, requested inference, changed source, or froze a candidate.

## Local admission

The Docker Desktop Linux engine was initially stopped. Starting the installed
local engine made the existing pinned image available. The next dependency
check passed and reached the calibrated memory gate. The 16,384-token window
failed both memory requirements.

| Resource | Available | Required at 16,384 | Shortfall |
| --- | ---: | ---: | ---: |
| Laptop GPU VRAM | 1,459,617,792 bytes (1.36 GiB) | 7,118,782,464 bytes (6.63 GiB) | 5,659,164,672 bytes |
| Laptop available RAM | 1,519,689,728 bytes (1.42 GiB) | 7,583,031,296 bytes (7.06 GiB) | 6,063,341,568 bytes |

The requirements include 512 MiB GPU and 2,048 MiB RAM headroom. A separate
read-only sample also showed both shortages. NVIDIA listed a pre-existing
LocalAI `llama-server.exe` among GPU clients. Windows did not report its
per-process VRAM, so attribution of the shortfall to that process is unverified.
No existing process was stopped to free memory. The calibrated 171.923-second
cold request estimate remained within the admission deadline. Actual model
load, inference and engineering latency were unmeasured.

## A100 readiness and execution status

The read-only preflight reached the existing llama.cpp endpoint through an
owned SSH forward, verified the reviewed Qwen3.6 Q6_K model identity, build and
template, and found one idle 131,072-token slot. The forward closed cleanly.
Raw A100 host RAM and free VRAM were unmeasured. The separate A100 arm was held
because its required predecessor had not run and closed successfully.

| Measurement | Local | A100 |
| --- | --- | --- |
| Result | Blocked before dispatch, insufficient VRAM and RAM | Ready at preflight, held by local-first gate |
| Recorded preflight total | 7.577 s, including pinned local model verification | 9.409 s |
| Readiness portion of that total | 0.162 s, memory sample and admission calculation | 7.543 s, read-only SSH and endpoint probe including owned forward closure |
| Worker admission, queue, model loading and inference | Unmeasured | Unmeasured |
| First response, accepted edit and public check | No events | No events |
| Generation requests and token consumption | 0 requests, 0 generated tokens | 0 requests, 0 generated tokens |
| Public and independent correctness | Ungraded | Ungraded |
| Engineering verification and cleanup times | No phase started | No phase started |

The calibrated preflight prevented a run under insufficient local headroom.
The approved execution order held A100 even though its endpoint was reachable.
These results validate the admission and sequencing boundaries. Automatic
profile ranking was never invoked. They provide no measured cross-plane
speed or correctness comparison. The frozen limits, remote services, historical
results and `main` were preserved. Both original authorizations remain unused.

[Preflight evidence](evidence/routing-cross-plane-result/README.md)
