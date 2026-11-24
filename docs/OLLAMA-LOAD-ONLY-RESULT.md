# Local Ollama load-only validation

The authorized validation at `fe82c72` passed on 2026-11-24. Its one-shot grant
was consumed. The server recorded one empty-prompt load request and returned
`done_reason: load` with an empty response. The phase ledger recorded zero
harness sessions and zero planner requests. No generation request ran.

The owned instance served the pinned Qwen3.5 9B Q4_K_M model at exactly 16,384
context tokens. `/api/ps` confirmed the reviewed digest
`85879493124988ce76ff36a6ac583504cc8d893727db6a0c4f9992a079e6ca49`.

| Measurement | Result |
| --- | ---: |
| llama.cpp runner startup | 48.28 s |
| Load-only HTTP request | 49.12 s |
| Bounded client load and residency check | 49.485 s |
| Whole command, including read-only preflight and cleanup | 69.125 s |
| Startup allocation and Ollama stall limit | 96.999 s / 75 s |
| Ollama-reported total resident model size | 6.22 GiB |
| Ollama-reported model VRAM | 5.02 GiB |
| Sampled peak GPU usage | 5.77 GiB |
| Sampled drop in available system RAM during work | 2.07 GiB |

The GPU and RAM observations are system-wide readings from 30 work-phase
samples. The RAM drop uses the admission baseline and does not attribute the
entire change to Ollama. The process ownership receipt and both phase cleanup
receipts passed. A post-exit TCP probe confirmed the owned listener was closed.
The phase ledger recorded no quarantine. The load-only result does not measure
reuse or engineering behavior on a subsequent request.

[Hashed execution evidence](evidence/ollama-load-only-result/evidence-hashes.json)
