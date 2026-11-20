# Next steps

## Phase 6.1 next approved work

The newly authorized recovery comparison is now **QUARANTINED**. Read the
[result and preserved evidence](HTTPX-RECOVERY-COMPARISON-RESULT.md): navigation
reached relevant code and two duplicate excerpts were suppressed, but both edit
attempts failed exact matching. No source change or public-test attempt was
delivered before the harness timeout. The hierarchical arm and sealed grading
were not started. This grant cannot be reused; earlier preparation/review
instructions below are historical.

Review the [execution recovery report and fresh HTTPX manifest](PHASE61-EXECUTION-RECOVERY.md).
Navigation and objective fixes pass 120 regressions and one bounded local
fixture smoke (1/4 → 4/4 public). This is not unfamiliar-repository completion.
The fresh HTTPX bundle remains PREPARED_NOT_AUTHORIZED and needs approval of its
new exact digest. Both historical quarantined trials remain closed; instructions
below concerning earlier review bundles are historical.

The authorized replacement comparison is now **QUARANTINED** following a direct
worker harness timeout. Read the [result and preserved evidence](HTTPX-REPLACEMENT-RESULT.md).
The worker made no source changes; the fallback is 7/16 public. Hierarchical
execution and sealed grading were not started. Do not resume either arm or reuse
its authorization. The preparation/review instructions below are historical.

The [cleanup correction and new authorization instructions](HTTPX-CLEANUP-REPAIR.md)
are ready. All 115 regressions pass. The fresh replacement bundle remains
PREPARED_NOT_AUTHORIZED and requires approval of its new exact digest; no
engineering campaign was started during diagnosis. Do not reuse the original grant.

The subsequently authorized HTTPX comparison is now **QUARANTINED** after a
Docker cleanup ownership-query timeout following direct warm-up. Read the
[outcome and preserved receipts](HTTPX-COMPARISON.md). No engineering worker or
sealed grader ran. Do not execute the authorization-review commands again or
resume the unspent reservations. A replacement trial is not authorized.

The original preparation/review guidance below remains historical:

Review the [exact HTTPX authorization bundle](HTTPX-AUTHORIZATION.md) and
[bounded handoff](PHASE61.md) before any new measured trial. The CI failure is
fixed and both original matrix jobs passed.
Focused inspection passed its local hardware fixture; unfamiliar-repository
completion remains untested. With sufficient budget, approve the frozen inputs,
four write roots, model/image and cumulative direct/hierarchical limits. The
frozen 20/180/40-second phase reservations now enforce a 240-second maximum per
arm, without resumption or time transfers. Preparation remains unauthorized and
made no inference requests. Prohibit mid-run implementation guidance and create
private final inputs only after
candidate freeze. Do not change the frozen Click artifact to address its newly
measured style failures; preserve them as historical results.

## Current Phase 6 handoff

Review the [Click feature patch and verification receipts](../deliverables/phase6/README.md).
The frozen result passes 31/31 public and 32/32 fresh sealed checks, plus 1,392
default repository tests and offline wheel integration. Production code/tests
are model-authored; recovery and documentation review required operator help.
No unassisted hierarchical advantage was demonstrated. Preserve the frozen
candidate and private final suite; do not feed sealed feedback into repair.
The [report](PHASE6-REPORT.md) records all unsuccessful attempts, the evaluator
correction and reproducible commands. Main and the Phase 5 release remain unchanged.

## Current ledger handoff

The bounded Phase 5 finalization is complete. The local function-replacement trial exhausted six requests without an accepted correction. Preserve framing 4/7, validation 14/18 and the imported A100 balance 9/10 checkpoint, plus the archived verified dependencies. All three selected sources pass UBSan execution but remain behaviorally incomplete. See the [final handoff](PHASE5-HANDOFF.md) for exact failures, costs and commands. Further repair requires new bounded authorization. Keep integration gated and freeze a verified executable before authoring a fresh sealed suite.

## Lambda managed profile

1. Confirm your Lambda API access independently of `aisak`. Copy `config/lambda.example.toml` to `config/lambda.local.toml` and set `LAMBDA_API_KEY` in the PowerShell process from your credential manager. Run `aiwork --config config/lambda.local.toml a100 instances` and `a100 types` to find instance types and capacity in your account.
2. Fill a unique `aiwork-*` instance name, approved region/type, registered public key name and existing persistent filesystem in the copied file. Add a dedicated SSH config alias for the existing key you intend to use. Set `ssh_host_alias` and enroll the trusted host key or host CA you control for the managed host. For unattended reprovisioning, arrange a trusted host-certificate issuance path in your image/bootstrap. A newly generated unknown host identity blocks automatic SSH.
3. Place a versioned GPU-compatible `llama-server` bundle and matching GGUF in your persistent filesystem. Adapt `config/cloud-init.example.yaml` to your mount, model, port and image, including the user name and linked CUDA libraries. Set `user_data_file` to the reviewed file. Set the managed profile’s exact model alias and context. [Lambda OpenAPI](https://cloud.lambda.ai/api/v1/openapi.json) · [llama.cpp server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)
4. Run `aiwork --config config/lambda.local.toml a100 plan` and inspect the nonsecret payload. Keep `allow_launch = false` until the persistent filesystem, host trust and server recipe are ready. With `allow_launch = true`, an explicitly dispatched managed job may launch one instance when none with that name is active. `a100 start --apply` separately requests creation and waits for provider readiness. `models` checks tunnel and model readiness without launching a new instance. Use an increased manifest timeout for cold startup.
5. To terminate a managed instance, first stop dispatch and let jobs finish. Check `a100 stop --instance <id>` for scope. Only with `allow_terminate = true` and `--apply` does the controller submit termination. For an ambiguous launch, inspect the provider’s instance list and confirm no unresolved creation before removing the named launch-intent file. Persistent storage is managed separately.

## REA and REA-Next

The `rea` and `rea-next` specialists take a trusted argv command. Use an absolute native executable or `{python}`. The controller replaces `{binary}` with the staged input and `{artifacts}` with its attempt directory. Stdout feeds bounded evidence. A nonzero exit blocks the run. Configure a static, version-pinned entry point. Do not run evaluation campaigns against the original REA-Next workspace.

```toml
[specialists.rea-next]
argv = ["{python}", "C:/path/to/reviewed_adapter.py", "{binary}", "{artifacts}"]
```

To check the existing pinned MCP installation on this laptop, run `python -B -m reanext.cli probe-mcp --profile native --timeout 30` from the inner REA-Next directory with its Python dependencies available. Use Ghidra for the validated native pipeline while bringing up another specialist. [REA](https://github.com/morluto/rea)

## Priorities for the next implementation

1. Add a separate evaluator identity for sealed holdouts. The current Docker pipeline runs staged code and its independent tests in the same container for a given check.
2. Exercise Lambda launch, cloud-init and SSH using a dedicated approved instance and host CA. Confirm shutdown and persistent volume recovery before enabling unattended launch.
3. Add actual GPU and server-side telemetry sampling, capacity-aware per-model reservations, and sustained repetitions across the profile matrix. Treat the existing A100 service as one serialized model lane until concurrency is measured.
4. Add targeted official REA decompilation and REA-Next campaign exports to the specialist result contract. Add hardened MCP server administration, remote harness placement and a local logon trigger if needed.
5. Extend engineering mode to additional harnesses and larger workspaces. Explore content-addressed snapshot storage and incremental materialization. Current isolated copies are bounded by file and byte counts, while review artifacts and checkpoints describe deltas.
