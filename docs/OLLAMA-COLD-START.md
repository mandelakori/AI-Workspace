# Calibrated Ollama cold-start correction

The consumed local arm at `1dda905` passed memory admission and opened the owned
Ollama HTTP listener. Its first OpenCode request then triggered the cold load.
The inner runner started at 05:42:29.571, reported model loading, entered
warm-up, and failed at 05:43:19.615. Ollama returned HTTP 500 with `timed out
waiting for llama-server to start - ` after 51.594 seconds at the relay. The
provider latch blocked the resend. The phase had time remaining, and neither
the model runner nor the provider reported an out-of-memory or capture failure.
[Historical execution report](ROUTING-CROSS-PLANE-EXECUTION.md)

The installed binary reports 0.40.17. Its versioned source uses
`OLLAMA_LOAD_TIMEOUT` to detect a stall and extends the stall deadline on
recognized load activity. The saved error text matches that branch. Client
cancellation has a different error path. The 45-second stall window therefore
explains the failure despite the longer wall time. The 49.39-second calibration
is a measured successful HTTP load duration, which does not directly measure
the longest inactivity interval. The logs do not establish what caused the
long warm-up interval on that particular run.
[Ollama timeout configuration](https://github.com/ollama/ollama/blob/v0.40.17/envconfig/config.go#L136-L152) · [Runner health and stall logic](https://github.com/ollama/ollama/blob/v0.40.17/llm/llama_server.go#L1291-L1368)

## Changed runtime behavior

- The calibrated runtime keeps the existing memory, context, model identity
  and verification reserves. It also checks any configured nonresident GPU
  minimum before loading. The per-context stall allowance is 1.5 times the
  measured successful load, rounded up and capped by the startup allocation.
- The absolute startup allocation is the smallest of 120 seconds, the measured
  stall allowance plus 25 seconds for listener startup, and the remaining
  work time after reserving the calibrated post-load portion and existing
  verification allowance. If too little time remains for the measured load,
  admission stops. With the recorded 16K measurements and a 220-second work
  allowance after verification reserve, the startup allocation is 97.467
  seconds and the Ollama stall allowance is 75 seconds. Newly initiated
  capacity calibration derives its stall limit from its existing 90-second
  load request and remaining context phase time.
- The listener receipt records HTTP readiness and the owned PID. Before the
  harness receives the endpoint, the controller performs one empty-prompt
  `/api/generate` call through the same process, then checks `/api/ps` for the
  exact model digest and admitted context. Ollama 0.40.17 returns a `load` result
  before generation for an empty prompt. The owned HTTP client is constrained
  by the same absolute initialization deadline, including the residency query.
  Timeout, invalid readiness or owner mismatch closes the owned Ollama job
  and prevents dispatch. Load and ownership receipts are separate. The
  provider failure latch is unchanged.
  [Ollama empty-prompt load behavior](https://github.com/ollama/ollama/blob/v0.40.17/server/routes.go#L512-L531)
- Cross-plane reporting checks the engineering and worker verdicts before
  opening the MCP transcript. It preserves provider or pre-harness failure as
  the primary reason. A purported success still requires the transcript,
  a scoped accepted edit, and a passing public test.

The full deterministic and inert-provider suite passed 254/254 with zero
skips. All 13 focused checks passed, including an owned client connecting to a
deliberately stalled loopback endpoint. The direct fixture passed before the
change. The unsigned manifest was validated and the installed local binary and
model blobs were verified read-only. No live load or generation was run.

## Load-only validation for review

**`PREPARED_NOT_AUTHORIZED`** for a separate `["local-initialization"]` approval.
The review digest is
`7fcb818fade7d18fcca517c800642dd61a975302dda2301af64f627201925a5b`.
The manifest pins the existing Qwen3.5 9B Q4_K_M model, Ollama executable and
model store, 16,384-token context, original calibration and controller hashes.
It reuses the local engineering admission envelope to assess headroom and
startup time. The actual validation authorizes **one load-only request, zero
generation requests, zero harness sessions and no grading**. It first allows
20 seconds for read-only preflight, then up to 240 seconds for the work lease.
Within that lease it waits at most five seconds for the existing local GPU
lane and applies the startup allocation capped at 120 seconds. The phase schema
retains an unused one-second grade slot. No Docker verifier is invoked.

Validate the manifest without starting Ollama.

```powershell
.\.venv\Scripts\python.exe examples/native/local_initialization.py validate docs/evidence/ollama-cold-start/initialization-review.json
```

After separate approval, the runner accepts `run <manifest> <approval.json>`.
The approval file must contain the exact `approval_digest`,
`"authorize": ["local-initialization"]` and `"operator_approved": true`.
It creates a fresh one-shot state under
`.aiwork/routing-validation/local-initialization-check`. Success requires the
expected listener owner, a `done_reason=load` response with no generated text
or tokens, matching residency digest and context, and clean owned cleanup.
Admission or startup failure consumes the run and preserves its receipts.
There is no retry, shared service change, or engineering follow-up in this
protocol. The actual local model load and reuse by a future engineering
request remain unverified.

The consumed local trial and unused A100 arm remain under their original
protocol. The new approval cannot launch either original arm.
[Validation evidence](evidence/ollama-cold-start/README.md)
