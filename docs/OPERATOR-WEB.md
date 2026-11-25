# Local operator console and screen interpretation

## Windows desktop application

Open **AI-Workspace** from the Windows Desktop. Select a project and model,
enter an engineering request, then review and approve the proposed scope and
verification. The laptop model is selected initially. **Automatic** allows
the reviewed request to use either configured execution plane. The application
does not provision cloud resources.

The application starts the installed Docker verifier if needed and uses the
controller's owned model startup, SSH connections, calibrated context and
memory admission. The initial laptop context estimate starts with the previous
7,440-token local fixture envelope and adds room for larger requests or an
attached screen. The app initializes OmniParser when you ask it to interpret a
preview. It sends approved screen observations only to the owned laptop model.

Projects, conversations, and job evidence are saved under `.aiwork/desktop`.
Inspect a run for tool activity, source diffs, and independent verifier results.
Save a proposed patch from the result. Follow-up requests include recent
conversation context and stage the current project files. They do not apply
older patches to the project. The **Native analysis** menu offers PE/ELF metadata
and available configured analyzers such as Ghidra.

Default verification covers Python unittest and Node test projects, with a
syntax-only alternative for Python, JavaScript, and C. For other build systems,
set the project command in the permission review. Verification runs offline
against the existing pinned image, so repositories requiring additional
dependencies need those dependencies staged or present in the verifier.

To recreate the shortcut on this installation, run
`scripts/Install-Desktop.ps1 -Launch` from the checkout. Ordinary use begins
from the desktop shortcut.

Functional validation used one disposable Python project with the installed
laptop Qwen model. OpenCode inspected the source, applied a scoped edit, and
passed its public test. The separate Docker verifier confirmed the result,
and controller-owned cleanup passed. The native analysis menu was exercised
on an existing ELF fixture with both metadata and installed Ghidra. The
desktop window reported the offline verifier ready and discovered the local
OmniParser installation. A100 appeared in the model menu and was left idle.

## Detailed operator console

The console is an optional addition to the controller after the validated
release candidate at `be627c6`. The development wheel identifies itself
as `1.0.0rc2.dev0`. It uses the same SQLite queue, execution
profiles, OpenCode 2.0.27 adapter, scoped editor, and independent verifier.

## Start the console

From the AI-Workspace checkout, use the existing configuration and select
one repository or a parent directory for the repositories you want to allow.
Omit `--verification-root` if you will only use checks from the approved
workspace. For private checks, give the console a separate operator-owned
directory outside the project root.

```powershell
$python = '.\.venv\Scripts\python.exe'
$cfg = '.\config\rc.local.toml'
$project = 'C:\work\my-project'
$private = 'C:\work\private-verifiers'
& $python -m aiwork --config $cfg web --project-root $project --verification-root $private
```

Open `http://127.0.0.1:8765/`. `--port` changes the port. The listener is
IPv4 loopback only. Keep it on a trusted desktop session.

1. Enter a natural-language objective and choose **Laptop**, **Existing A100**,
   or **Automatic**. Automatic allows the controller to consider both existing
   planes. The review lists the eligible OpenCode profiles and routing reasons.
2. Enter explicit readable paths, writable paths, and any required outputs.
   Enter public and independent commands as JSON arrays. For example, a public
   command can be `[{"argv":["{python}","tests/public_check.py"],"timeout":30}]`.
   For a private directory choose `.` or a child directory of the configured
   verification root. An independent command can be
   `[{"argv":["{python}","{verification}/accept.py"],"timeout":30}]`.
   For sealed comparisons use the existing [oracle contract](ENGINEERING.md#phase-3-operator-workflow).
3. Choose **Review settings**, **Approve & queue**, and **Run** on the queued
   row. Approval queues a snapshot. Run dispatches one attempt using the
   configured offline Docker verifier. Source edits remain in the run
   artifacts, where the console shows the proposed diff and independent
   verdicts. To apply a passing patch, use the [existing CLI workflow](OPERATOR-GUIDE.md).
4. Open the job details for attempt telemetry and reported token usage.
   Checks and token receipts appear as the controller writes them. Closed
   jobs remain available after a restart. A fresh console session can inspect
   an old queued job. Use the CLI to explicitly inspect and run such a job
   using the reviewed configuration.

The console admits only existing unmanaged OpenCode profiles. Existing
calibrated local profiles start their owned model at dispatch if needed.
**Check** probes model identity when an endpoint is available. **Reclaim
local memory** requires a separate confirmation and an `idle_ollama`
enrollment in the config. The existing exclusive lane and enrolled model
identity checks apply. The receipt includes measured memory before and after.

## Set up optional OmniParser V2 on Windows

The perception subprocess uses Microsoft's pinned
[`YOLOv9Detector`](https://github.com/microsoft/OmniParser/blob/354021201345a96178360b28733573e27269f2de/util/yolov9.py),
the MIT `icon_detect_v3` and Florence-2 caption weights from the [OmniParser
V2 model repository](https://huggingface.co/microsoft/OmniParser-v2.0),
and English OCR through EasyOCR. The optional process uses pinned
[Florence-2-base processor assets](https://huggingface.co/microsoft/Florence-2-base/tree/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac)
and [Florence-2-base-ft model code](https://huggingface.co/microsoft/Florence-2-base-ft/tree/f6c1a25888ffc1d945ee8a1a77ac833c7303d46e)
for the caption checkpoint's declared architecture. Upstream source and
weights retain their respective licenses. The controller wheel has zero
Python runtime dependencies. Install the CUDA libraries and model assets
only in the optional environment. The following one-time setup accesses
package and model repositories and requires a supported NVIDIA CUDA driver.

```powershell
$omni = Join-Path (Get-Location) '.aiwork\omni'
& $python -m venv (Join-Path $omni 'venv')
$omniPython = Join-Path $omni 'venv\Scripts\python.exe'
& $omniPython -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128
& $omniPython -m pip install transformers==4.49.0 huggingface-hub==0.30.2 easyocr==1.7.2 timm==1.0.15 einops==0.8.1
& $omniPython -m pip install --no-deps .
git clone https://github.com/microsoft/OmniParser.git (Join-Path $omni 'source')
git -C (Join-Path $omni 'source') checkout --detach 354021201345a96178360b28733573e27269f2de
$modelSetup = @'
from pathlib import Path
import sys
from easyocr import Reader
from huggingface_hub import snapshot_download
from aiwork.perception import PINS

root = Path(sys.argv[1])
cache = root / 'models'
snapshot_download('microsoft/OmniParser-v2.0', revision=PINS['weights'], cache_dir=cache,
    allow_patterns=['icon_detect_v3/model.pt', 'icon_detect_v3/LICENSE', 'icon_caption/*'],
    token=False, max_workers=1)
snapshot_download('microsoft/Florence-2-base', revision=PINS['florence_processor'], cache_dir=cache,
    allow_patterns=['*.json', '*.txt', '*.py', 'LICENSE'], token=False, max_workers=1)
snapshot_download('microsoft/Florence-2-base-ft', revision=PINS['florence_code'], cache_dir=cache,
    allow_patterns=['*.py', 'LICENSE'], token=False, max_workers=1)
Reader(['en'], gpu=False, model_storage_directory=str(root / 'ocr'))
'@
$modelSetup | & $omniPython - $omni
```

Create `.aiwork/omni/perception.toml` with the following content. Paths in
this file resolve relative to it. Memory floors are admission settings
pending hardware measurements.

```toml
python = "venv/Scripts/python.exe"
source = "source"
cache = "models"
ocr = "ocr"
ram_mib = 4096
vram_mib = 6144
timeout = 90
enable_remote = false
```

Add `--perception-config .aiwork/omni/perception.toml` to the console command.
Capture the primary Windows screen or choose a PNG. Preview it before
selecting **Interpret screenshot**. The preview shows normalized boxes and
their labels. Select an item to highlight its box. The JSON panel contains
structured observations suitable for quoting as untrusted context in a task
you review. Capture is explicit and stays on the operator's machine. Local
processing uses the controller's exclusive GPU lane and checks measured free
RAM and VRAM before starting the offline subprocess. The console does not
save screenshots in job artifacts or send screen content to a language-model
profile. Desktop interaction controls are absent.

## Optional A100 peer

The remote path requires separate operator approval to install and run a
peer. It uses a dedicated loopback port and existing SSH host trust. Once the
peer is separately installed in its own CUDA environment and pinned caches
are staged, start it with the remote interpreter and actual paths.

```sh
/path/to/omni-venv/bin/python -m aiwork.omni_worker serve /path/to/source /path/to/models /path/to/ocr --port 18770
```

Set `AIWORK_OMNI_TOKEN` to the same separately managed secret of at least
24 characters on each side. Keep the token out of TOML and shell history.
On Windows, set `enable_remote = true` in the perception config. The default
local forwarding port is 18771 and the peer port is 18770. The `[ssh]` alias
comes from the controller config. The peer rejects parsing without
authentication and checks its own memory floor before each parse. Choose A100
in the UI and explicitly confirm transmission for that screenshot. The entire
PNG goes to the peer for that invocation.

The controller acquires the existing A100 lane before it opens a dedicated
SSH forward. No cloud lifecycle operation is used. After dispatch, a marker
blocks new A100 jobs until the peer confirms cleanup and the owned SSH session
closes. If completion is uncertain, verify the peer is idle and its parser
and SSH forward are gone before clearing `A100_PERCEPTION_UNCERTAIN` in the
configured shared execution state.

## Give OpenCode a reviewed screen observation

After interpreting a screenshot locally, expand **Structured observations**.
Review the OCR text, descriptions and boxes, then use **Save local observation
JSON**. Save the file outside the project workspace. For the engineering task,
set `location = "local"` and choose its explicit calibrated, controller-owned
Ollama/OpenCode profile. Approve the hash for that exact file when submitting.

```powershell
$screen = 'C:\work\reviewed-screen.json'
$hash = (Get-FileHash -LiteralPath $screen -Algorithm SHA256).Hash
& $python -m aiwork --config $cfg task run C:\work\engineering.toml --profile measured-opencode --screen-observation $screen --screen-sha256 $hash
```

The job freezes the reviewed JSON outside the staged workspace. The optional
`checks_screen` tool returns up to 12 elements per call and uses existing
inspection budget. It accepts an optional offset. It has no live capture,
screenshot bytes, arbitrary file reads or desktop control. Remote, automatic,
and unowned profiles cannot receive the data. The approved JSON and tool
responses are retained in local job evidence. The worker treats screen text
as untrusted data.

## Separate perception benchmark

Use a synthetic PNG without sensitive data. Omit `--apply` to preview the
one-request local run. An applied run records detected elements and their
descriptions, initialization and inference times, total latency, CUDA peak
allocated bytes, and sampled system free RAM and VRAM through cleanup.
Concurrent unrelated activity can affect those system measurements.

```powershell
& $python -m aiwork --config $cfg perception-bench C:\work\synthetic-ui.png --perception-config .aiwork/omni/perception.toml
& $python -m aiwork --config $cfg perception-bench C:\work\synthetic-ui.png --perception-config .aiwork/omni/perception.toml --apply
```

The [local validation record](OMNIPARSER-LOCAL-VALIDATION.md) gives the
measured RTX 5070 timings, memory and cleanup, interactive Windows capture,
browser preview, and restored test coverage. The optional A100 peer remains
unverified on live hardware.
