# AI Workspace

AI Workspace runs manifests for software development, testing and bounded static-analysis jobs from a Windows controller. It stages inputs, selects an execution profile, runs OpenCode or a deterministic check, independently verifies the result and retains the work and evidence. The A100 can serve inference over the existing SSH connection while the harness and workspace stay on Windows.

The project is in **final integration and stabilization** on the original
roadmap. The [release handoff](docs/RELEASE-STABILIZATION.md) describes the
verified workflow, remaining limitations and separately authorized local
smoke test. [Status](docs/STATUS.md) retains the historical trial outcomes.

## Windows first run

Use PowerShell 7, Python 3.12 or newer, and Git. The bootstrap accepts a path to an existing Python executable and uses uv or the Python launcher when that path is omitted. Node.js 22+ and npm are needed for optional npm installations. Bootstrap may use package indexes. For an offline setup, install the built wheel with `pip install --no-index --no-deps <wheel>`, copy `aiwork.example.toml` to `aiwork.local.toml`, and configure installed binaries. Building offline requires the pinned `setuptools` wheel from `pyproject.toml` in a local wheelhouse.

```powershell
Set-Location 'C:\Users\mande\coding\Final RSTP\AI-Workspace'
.\scripts\Bootstrap.ps1 -Python "$env:USERPROFILE\.local\bin\python3.12.exe"
$ai = '.\.venv\Scripts\aiwork.exe'
& $ai --help
& $ai doctor
& $ai harnesses
& $ai task run examples/direct.toml --trusted
```

Add `-InstallOpenCode` to bootstrap if OpenCode 2.0.27 is missing. Bootstrap creates `aiwork.local.toml` from the example on first use. Set `opencode` at the top level for a custom executable. `aiwork models` probes the configured services, including SSH for an A100 profile. Shared-service profiles expect the installed model endpoint to be available. A calibrated local profile starts its own isolated service after admission. Scoped engineering and sealed checks need Docker Desktop in Linux mode and the configured offline image already installed. `--trusted` authorizes the named host checks. The separately reviewed local smoke launches a live worker only after its own approval.

## Submit work and retrieve results

The [Phase 3 engineering guide](docs/ENGINEERING.md#phase-3-operator-workflow) covers the Docker runner, sealed acceptance tests, repeated comparisons, repository indexing, plan revision and self-development patches.

```powershell
& $ai task inspect examples/coding.toml
& $ai task submit examples/coding.toml --trusted
& $ai worker --once
& $ai runs
& $ai runs <job-id>
```

Create a TOML manifest modeled on [examples/coding.toml](examples/coding.toml). Keep the objective and input paths specific. Use `deliverables` to declare the files the harness may edit and `[[checks]]` for fixed arguments and exit-code or exact-output criteria. `{python}` uses the controller interpreter, or the image’s Python in Docker. Put private checks in a sibling directory named by `verification_dir` and address it with `{verification}` in check arguments. Each agent check gets a disposable copy. The independent verification phase uses a separate copy of the candidate and runs its checks in order.

Use `--profile <id>` for a hard override, or set `location` to `auto`, `local` or `a100` in the manifest. For ordinary jobs, `aiwork task resume <job-id>` preserves earlier attempts and can reuse a checkpoint. Add `--reset` for a clean baseline or `--interrupted` for a stale running job after the original worker exits. One-shot measured trials have their own protocol. Open the returned `artifacts` directory and use its verification receipts to identify the verified attempt. Review the candidate in `attempt-*/workspace` for model jobs or `attempt-*/verification` for direct jobs.

### Controller and A100

```powershell
.\scripts\Controller.ps1 -Action Start
.\scripts\Controller.ps1 -Action Status
.\scripts\Controller.ps1 -Action Stop
& $ai a100 status
.\scripts\Smoke.ps1 -Profile a100-existing
& $ai benchmark examples/coding.toml --profile laptop-ollama --profile a100-existing --repeats 3 --trusted
& $ai workflow examples/multi-agent.toml --id conversion-dual-01 --workers 2 --trusted
```

You can also keep the worker visible with `-Action Foreground`. The worker operates while Windows is running and the process stays alive. `Stop` pauses dispatch and interrupts checks or harnesses at their next stop poll. Use `aiwork control start` before manually restarting a stopped worker.

The A100 profile uses the existing `aisak` alias and the observed remote loopback port 18080. Provisioning uses a separate opt-in profile. Follow [the Lambda setup procedure](docs/NEXT_STEPS.md#lambda-managed-profile) before allowing a billable action.

### Optional harnesses and native work

To install and run Qwen Code against the verified A100 profile:

```powershell
.\scripts\Bootstrap.ps1 -InstallQwen
& $ai --config config/qwen.example.toml task run examples/coding.toml --profile a100-qwen --trusted
```

The Qwen profile uses the serving context reported by the A100 llama.cpp endpoint. Keep the profile’s context synchronized with the server.

In an x64 Visual Studio Developer PowerShell with MSVC and Ghidra installed, run:

```powershell
.\scripts\NativeDemo.ps1 -Profile a100-existing -GhidraHeadless 'C:\path\to\ghidra\support\analyzeHeadless.bat'
```

The native fixture compiles a self-authored reference, extracts Ghidra evidence, limits the generated C to the toy function body, and compares compiled behavior on 182 inputs. See [security](docs/SECURITY.md) before opening a different binary or running generated code.

Add `-InstallRea` to your bootstrap command and run `scripts/ReaDemo.ps1` from the same Developer PowerShell to exercise official REA’s static PE resource adapter.

## Development

[Engineering mode](docs/ENGINEERING.md) adds scoped multi-file editing, Docker command recipes, automatic planning, verified artifact integration and reviewable patches. It includes an isolated self-development command.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Use [AGENTS.md](AGENTS.md) and [Architecture](docs/ARCHITECTURE.md) to extend the platform. [Status](docs/STATUS.md), [Benchmarks](docs/BENCHMARKS.md) and [Next steps](docs/NEXT_STEPS.md) describe the validated configurations and remaining work.
