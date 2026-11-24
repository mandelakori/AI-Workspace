# Final integration and stabilization

## Memory admission and cleanup

Each owned Ollama server remains scoped to its attempt and GPU lane. On Windows,
its Job Object closes the owned process tree on release, failure or owner exit.
The controller retains the cleanup receipt and can block promotion and fallback
after a cleanup failure. A saved PID is evidence only. Reclamation does not scan
for candidate processes to terminate.

External model reclamation is disabled by default. To enable it, review and
configure one `[idle_ollama]` entry in the operator's TOML. The example shows
the required fields. Use an explicit IPv4 loopback port, a local model tag and
its `/api/tags` digest, and the absolute `ollama.exe` path and SHA-256. Inspect
the digest and path before enabling the policy and keep the enrolled tag stable.
Use the same `execution_state` across controllers sharing the GPU.

The controller attempts reclamation once, under the exclusive local lane, when
known RAM or VRAM is too low and the workload otherwise qualifies. Uncalibrated
profiles use their configured VRAM minimum. Calibrated profiles use their
measured RAM, VRAM and deadline policy. Unknown telemetry or another admission
blocker cannot trigger an unload. The helper verifies listener PID, process
creation time, executable and model identities and Ollama version 0.40.17. Its
only mutation is an empty-prompt, `keep_alive: 0` request for the enrolled tag.
In that release, the server defers eviction until an active runner reaches zero
request references. A pending eviction can remain resident beyond the bounded
poll. External processes are never stopped by the helper.
[Ollama unload endpoint](https://github.com/ollama/ollama/blob/v0.40.17/server/routes.go#L444-L454) · [Scheduler reference checks](https://github.com/ollama/ollama/blob/v0.40.17/server/sched.go#L401-L447) · [Unload scheduling](https://github.com/ollama/ollama/blob/v0.40.17/server/sched.go#L1650-L1676)

The helper is capped at eight seconds, with a separate reserve for the memory
recheck. The controller writes `memory-reclamation.json` and records the fresh
readings in the admission receipt. An unload acknowledgment alone never
qualifies a job. If rechecked resources are still insufficient, the ordinary
attempt policy may use an eligible configured profile. Explicit profile and
location overrides and one-shot trial limits continue to apply.

## Operator workflow and installation audit

- A fresh checkout can run `python -m aiwork --help` from the repository. Use
  `Bootstrap.ps1` to create the Windows environment and CLI launcher. For an
  offline build, provide the pinned `setuptools==80.9.0` wheel and run
  `python -m pip wheel --no-index --find-links <wheelhouse> --no-deps .`.
  Install the resulting wheel with `--no-index --no-deps`.
- Use `aiwork doctor`, `aiwork harnesses`, and `aiwork task inspect <manifest>`
  before dispatch. `aiwork models` contacts configured endpoints. A missing
  explicit configuration exits with code 2 and a concise stderr message.
  A task that ran and failed to verify exits with code 1 and retains receipts.
- `task submit`, `worker --once`, and `runs <job-id>` form the queue and review
  path. `task run` combines submit and execution. Use the returned `artifacts`
  path to inspect routing, admission, edits, provider logs and the final verifier
  receipt. `Controller.ps1 Stop` sets the existing cooperative stop marker.
- Verified locally for this pass are CLI help and version, manifest inspection,
  doctor, the direct queue/result path and the pinned offline package build.
  The shipped default example keeps thinking OFF for both model profiles.

All 260 controller regressions passed with zero skips, including installed
inert harness and Docker checks. The focused run passed 33 tests with one
installed boundary test deferred to the full run. The wheel was installed
into an isolated directory using the existing offline build dependency.

## Reviewed local end-to-end smoke

The subsequent [authorized run](LOCAL-ENGINEERING-SMOKE-RESULT.md) passed. The
preparation protocol below records the reviewed inputs and limits. Its grant is
consumed.

The local-only bundle at `.aiwork/release-validation/engineering-smoke/local`
was prepared as `PREPARED_NOT_AUTHORIZED`. It reuses the existing frozen runner and
the pristine two-file temperature conversion fixture. Only `units.py` is
writable. Reclamation is disabled in this smoke's configuration. The pinned
Qwen3.5 9B Q4_K_M model and OpenCode use 16,384 context, thinking OFF and a
1,536-token output ceiling. One 240-second attempt allows at most 12 requests,
20 MCP operations and one compaction, within the existing 20/265/45-second
phase reservations. The private oracle stays outside the worker scope and Git.

The offline pristine baseline is 1/4 public and 0/6 independent. Live success
requires confirmed load-only residency before dispatch, a valid model-authored
edit, a passing tool-invoked public test, 4/4 independent public reruns, clean
closure and cleanup, and 6/6 independent acceptance after candidate freeze.
No retries or fallback are part of this smoke.

Validate the unsigned manifest without contacting the inference service.

```powershell
$smoke = '.aiwork/release-validation/engineering-smoke/local'
.\.venv\Scripts\python.exe examples/native/cross_plane_trial.py validate $smoke
```

The approval digest is
`ce3bf3c489e129f05325084be56363f80411384ca9010d895df9a166a6eb6d45`.
Only after separate approval, use `run <bundle/arm> <approval.json>` with that
digest, `"authorize": ["local"]` and `"operator_approved": true`. The old
cross-plane and load-only grants retain their own
protocols. [Evidence and exact smoke manifest](evidence/release-stabilization/README.md)

## Release limits

The load-only initialization and its transition into scoped OpenCode engineering
passed on the bounded conversion fixture. External unload behavior is
covered by deterministic tests and the reviewed Ollama version source. No live
external service was unloaded during this work. Other providers and Ollama
versions are outside the reviewed unload scope.

The controller has verified scoped editing, public tests, provider accounting,
rollback and independent grading. Complex unattended engineering still fails
some acceptance gates, including the ItsDangerous final trial. The native
workbench supports static analysis and has verified bounded reconstruction
fixtures. Whole-program stateful reconstruction remains incomplete for the
ledger. The original roadmap and these historical failures remain in force.
[Engineering outcome](MILESTONE-E-FINAL-RESULT.md) · [Native workbench](NATIVE-WORKBENCH-VALIDATION.md)
