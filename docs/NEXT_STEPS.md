# Next steps

## Current ledger handoff

The Phase 5.2 closeout exhausted two local source-edit attempts per failing component. Integration remains blocked by framing, operand validation and balance's arithmetic ordering. Preserve the selected checkpoints and reused verified jobs. The [frozen benchmark](LEDGER-BENCHMARK.md) records that baseline without new inference and prepares the existing A100 coding profile for a separately authorized, matched six-request experiment. No remote dispatch is currently authorized. Freeze a verified executable before authoring a fresh sealed suite.

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
