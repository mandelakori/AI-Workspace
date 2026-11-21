# OpenCode versus Pi: exact review protocol

**PREPARED_NOT_AUTHORIZED**. No worker, engineering model call or sealed case has
been dispatched/created. This preparation does not reuse any consumed approval.

Approval digest:
`26c715e373551595dd655c09ecdf72bb96a3057fee9d12eeeafe69d721b2e8e2`

Local bundle: `.aiwork/adaptive-local/comparison`. The exact
[manifest](evidence/adaptive-local/comparison/manifest.json) freezes implementation,
both harness installations, inference executable, calibration, original inventory,
initial context and image. Its randomized order is **Pi → OpenCode**. Authorization
must name exactly `["opencode", "pi"]` and that digest; the order is already frozen.

| Dimension | Both arms |
| --- | --- |
| Task | Same pinned python-dotenv nested-default problem from closed Phase 6.1, commit `4fbc6ff`; reused to isolate harness effects, not a new unfamiliar-task claim |
| Start | Identical clean 47-file snapshots, same task contract and 3471-byte upfront source evidence without a solution; inventories bound in manifest |
| Model | Existing `qwen3.5:9b`, 16K fixed for both, 2048 output, temperature 0, seed 1729, reasoning disabled |
| Inference | Fresh private Ollama process and fresh harness home per arm; same independent copied model store, f16 KV, flash attention, parallel 1, calibrated 512 MiB engine GPU overhead |
| Admission | Current RAM/VRAM +512 MiB GPU /2048 MiB RAM headroom; full observed task demand 7440+2048+512=10000 tokens; refuse if measured 16K is not admissible, never substitute another context or model |
| Worker | One attempt, no planner, no retries, no mid-run implementation guidance |
| Tools | Same four scoped tools; only `src/dotenv/variables.py` and `tests/test_nested_defaults.py` writable; exact current hash/anchor editor |
| Operations | 48 total, four editing slots and four public-test slots reserved; at most 64 model requests including four compactions |
| Per-arm time | 5-second **no-inference** startup lease, 330-second engineering phase, 40-second independent grading reservation; total reservations 375 seconds |
| Attempt | 300-second ceiling including private-server startup, cold loading, first prefill, inference, tools and cleanup; existing controller reserves 20 seconds within the attempt for final public verification |
| Verifier | Identical existing offline Docker image, manifest-pinned image ID; same ten public feature cases, syntax and upstream checks |
| Selection | Compare final export to original; protect existing public passes and reject upstream regression. Preserve all edits and intermediate snapshots; no claim that every intermediate is ranked |
| Final evaluation | Only after both engineering phases cleanly close and both candidates freeze: independently author twelve genuinely new sealed inputs, same suite for both, no expected outputs mounted and no feedback to workers |

The old 20/180/40 protocol is unchanged. These longer **new** limits require this
separate approval: measured cold loading plus first prefill alone consumed roughly
78–97 seconds, and the conservative 16K single-request estimate is about 195.5
seconds for the recorded input/output ceiling. A 300-second attempt is a bounded
engineering allowance, not a claim that 64 full-size requests fit. Actual requests
and elapsed time remain limited by the original absolute watchdogs.

No generation warm-up is performed. OS/driver/disk caches are not purged or
pretended equal; record execution order, native cached-token counters, server logs,
actual offload, provider usage and cold-start times. Any unreported cache accounting
stays unknown. One randomized pair cannot establish causal superiority or a success
rate. Hierarchy is not a variable in this comparison.

Stop the pair on interruption, failed catalog, provider/harness failure, phase
timeout or failed cleanup. Quarantined/consumed arms cannot resume or retry. Clean
tool/resource exhaustion is reported separately and may freeze a partial candidate
if all controller cleanup and public-selection checks close within the phase.
Do not grade a candidate after an interrupted/quarantined engineering phase.

The unchanged baseline reproduces **2/10 public**, syntax passing, and **287 upstream
passes / five platform-or-root skips** (286+1 in two controlled invocations).
Baseline checks are preparation, not agent engineering. Exact receipts are preserved.

After separate operator approval only:

```powershell
# First verify that every frozen input still matches; this does not infer.
.\.venv\Scripts\python.exe -m aiwork.harness_comparison validate .aiwork/adaptive-local/comparison
# Copy operator-approval.example.json to a new approval file and set
# operator_approved=true only to record the operator's explicit digest approval.
.\.venv\Scripts\python.exe -m aiwork.harness_comparison run .aiwork/adaptive-local/comparison --approval .aiwork/adaptive-local/comparison/operator-approval.json
# Stop here unless engineering-closed.json exists and both frozen hashes verify.
# An independent evaluator then authors private/cases.json with 12 new cases.
.\.venv\Scripts\python.exe -m aiwork.harness_comparison grade .aiwork/adaptive-local/comparison --approval .aiwork/adaptive-local/comparison/operator-approval.json
```

Report applied/rejected edits, first-edit/test operations, repeated/evicted reads,
authored tests, complete public and upstream scores, sealed correctness, rollback,
provider usage/cache counters, category time, total time, raw harness exit status,
ownership and cleanup. Keep autonomous completion, partial completion and harness
failure separate. The prepared runner was deterministically tested for approval,
drift, matching and consumed-budget guards; its **live paired path is UNTESTED**.
