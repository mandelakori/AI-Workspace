# AI Workspace 1.0.0rc1 operator guide

Use this guide for ordinary jobs on the existing laptop and A100. The
[acceptance matrix](ACCEPTANCE.md) lists the demonstrated scope. Recorded
trial manifests and grants have separate [dispositions](STATUS.md).

## Install and check

Open PowerShell 7 in the repository. Use Python 3.12 or later and Git. The
Windows bootstrap creates `.venv`, installs the package, and copies the starter
config on first use. It can use a package index. `-InstallOpenCode` installs the
reviewed OpenCode 2.0.27 through npm when needed. Existing installations can be
reused. Use Docker Desktop in Linux mode for the pinned offline verifier.

For the existing machine, build the RC offline into a separate environment.

```powershell
Set-Location 'C:\Users\mande\coding\Final RSTP\AI-Workspace'
$python = '.\.venv\Scripts\python.exe'
$wheelhouse = '.aiwork\phase61-discovery\image\wheels'
$dist = '.aiwork\rc-package\dist'
& $python -m pip wheel --no-index --find-links $wheelhouse --no-deps --wheel-dir $dist .
& $python -m venv .aiwork\rc-package\venv
$rcPython = '.\.aiwork\rc-package\venv\Scripts\python.exe'
& $rcPython -m pip install --no-index --no-deps "$dist\ai_workspace-1.0.0rc1-py3-none-any.whl"
$ai = '.\.aiwork\rc-package\venv\Scripts\aiwork.exe'
& $ai --version
& $ai --help
```

Use a wheelhouse containing `setuptools==80.9.0` if the historical cache is
absent. With a prebuilt RC wheel, only the venv and offline install steps are
required. Keep the checkout for PowerShell scripts and example TOMLs. A source
checkout can pick up installed package metadata from its interpreter, so use
the RC environment when checking the release version.

## Existing hardware configuration

```powershell
$cfg = '.\config\rc.local.toml'
if (-not (Test-Path -LiteralPath $cfg)) {
    Copy-Item -LiteralPath '.\config\rc.example.toml' -Destination $cfg
}
& $ai --config $cfg doctor
& $ai --config $cfg harnesses
& $ai --config $cfg task run examples/direct.toml
```

Keep the copied config in `config/` because paths resolve relative to it. This
starts a separate queue at `.aiwork/rc` and reuses the existing `.aiwork` lane
locks. Doctor reports the Linux Docker engine and exact pinned image.

| Profile | Required existing resources |
| --- | --- |
| `measured-opencode` | Installed Ollama and `qwen3.5:9b` Q4_K_M in the pinned calibration model store. The controller reserves the GPU lane, checks real memory and the deadline, then starts an owned Ollama listener. Admission selects a measured context window. No shared Ollama daemon is required. |
| `a100-existing` | The existing `aisak` SSH alias and host key, local port `18881`, remote `127.0.0.1:18080`, and the configured Qwen3.6 35B-A3B Q6_K model. The Windows harness opens an owned forward, and the controller serializes one inference lane. The profile has `managed = false`. |

Both example profiles disable thinking. The A100 profile declares 65,536
context and expects the server to support it. `aiwork --config $cfg a100
status` probes the SSH host and `aiwork --config $cfg models` probes configured
model endpoints. These commands can contact A100. A calibrated laptop profile
can work even if shared Ollama is absent. On this path compare the loaded
digest and context in `local-inference/load-readiness.json`.

### Memory admission and reclamation

Calibrated admission includes RAM, VRAM, context and startup time. Owned
processes are released on exit. Optional `[idle_ollama]` enrollment allows
one graceful, bounded unload of the reviewed local model on known memory
pressure. It is disabled in the RC example. Read
[the enrollment and ownership policy](RELEASE-STABILIZATION.md#memory-admission-and-cleanup)
before opting in. Check `memory-reclamation.json` and the subsequent admission
receipt to see whether memory actually became available. Profile selection
does not add fallback lanes beyond the task's existing eligibility and attempt
budget.

## Submit a real engineering task

Use [the scoped TOML](../examples/scoped-engineering.toml) as a template. In
your copy, set `workspace` to the real project path, describe the intended
change and acceptance in `objective`, and list only needed paths in `inputs`.
Declare writable files in `write_roots` and expected outputs in `deliverables`.
Replace `[[commands]]` with public checks the model may invoke and `[[checks]]`
with the controller's independent checks. Use commands and dependencies already
available in the verifier image. For calibrated laptop execution, set
`context_input_tokens` to a justified observed demand for the task and allow
time for cold startup and verification. The template's value is for the small
conversion fixture.

These commands execute live work when you choose to run them. Substitute your
reviewed real task manifest for the checked-in example.

```powershell
$task = 'C:\path\to\reviewed-task.toml'
& $ai --config $cfg task inspect $task

# Run exactly the selected task on the laptop.
& $ai --config $cfg task run $task --profile measured-opencode

# Or run exactly the selected task on the existing A100.
& $ai --config $cfg task run $task --profile a100-existing
```

To queue instead of immediately running, use the matching profile with
`task submit`. The queue is shared with workers using that config.

```powershell
# Choose one submission and keep its returned job ID.
$job = (& $ai --config $cfg task submit $task --profile measured-opencode | ConvertFrom-Json).job
# A100 alternative:
# $job = (& $ai --config $cfg task submit $task --profile a100-existing | ConvertFrom-Json).job
& $ai --config $cfg worker --once
& $ai --config $cfg runs $job
```

`worker --once` claims the next eligible queued job. For continuous dispatch
use `worker --exclusive`, or `scripts/Controller.ps1 -Action Start -Config $cfg`
if the main `.venv` has the RC installed. Use `control status`, `control stop`,
and `control start` with the same config. Stop uses a cooperative marker.
Ordinary jobs may be resumed after reviewing their receipts, with `--reset`
for the pristine baseline and `--interrupted` once a stale owner has exited.
The one-shot frozen trials use their own non-resumable runner.

## Verify and retrieve results

An engineering job writes a staged candidate, not a patch applied to your
checkout. Open the returned `artifacts` path and inspect the selected attempt's
`workspace`, `proposed.patch`, `evidence.json` and `check-*.json`. Validate a
patch against the intended revision with `git apply --check` before applying
it. A CLI task exit of 1 means it did not verify. Exit 2 indicates command or
configuration error. Review `routing.json`, `admission.json`,
`local-context-admission.json`, `execution-receipt.json` and provider logs for
the failure boundary.

Put private material in a sibling `verification_dir` outside `workspace`.
Sealed black-box checks use `oracle = "cases.json"` in `[[checks]]`. The
verifier sends only the current stimulus to the candidate and compares the
result on the controller. A legacy `{verification}` mount gives the verifier
access to private files in its own check context. Use the sealed protocol for
hidden expectations and a separate evaluator identity for hostile candidates.
The scoped harness runs under the operator's Windows account. For untrusted
projects use a restricted OS account or VM. See [engineering recipes](ENGINEERING.md)
and [security boundaries](SECURITY.md).

## Native analysis and verification

Use authorized PE/ELF inputs. For metadata, use a `kind = "direct"` manifest
with `specialist = "binary"`. For Ghidra add the reviewed installed
`[specialists.ghidra]` headless executable and selector to your config, use
`specialist = "ghidra"`, and authorize that host tool with `--trusted`.
`aiwork tools` reports installed adapters. `scripts/ReaDemo.ps1` demonstrates
the reviewed REA PE resource adapter using the self-authored reference and
installed MSVC. `scripts/NativeDemo.ps1` is a separate live, trusted Windows
PE fixture with MSVC and Ghidra; it requires a host verifier config without
the Linux Docker image in the RC example.

For an authorized ELF reconstruction, adapt the
[native stride manifest](../examples/phase4/stride/native.toml) and use
`aiwork --config $cfg native run <native.toml> --profile a100-existing`.
Use `--evidence ghidra --trusted` only with your reviewed configured analyzer.
Grade a frozen candidate with `native grade <run-dir> --cases <private-inputs>`.
Keep original source, private inputs and expectations in the verifier boundary.
Compilation, public behavior and independently graded behavior are separate
verdicts. REA-Next archive import and campaign commands retain their specific
host/tool requirements. [Native workbench](NATIVE-WORKBENCH-VALIDATION.md)
