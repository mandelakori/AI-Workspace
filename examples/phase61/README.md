# Bounded Phase 6.1 preparation

The [handoff](../../docs/PHASE61.md) distinguishes the Windows CI fix, focused-tool
smoke, deferred Click checks and approval-pending HTTPX task. No expensive
comparison or unfamiliar-repository model campaign runs automatically.

From the repository root, using the existing configured Python environment:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_focus.py -v
.venv/Scripts/python.exe examples/phase61/audit_traces.py .aiwork/phase6 .aiwork/phase61 .aiwork/phase61/audit-replay
```

Full local regression uses the existing Docker image and installed OpenCode:

```powershell
$env:AIWORK_TEST_DOCKER_IMAGE='aiwork-engineering:phase3'
$env:AIWORK_TEST_OPENCODE_BOUNDARY='1'
.venv/Scripts/python.exe -m unittest discover -s tests -q
```

`Dockerfile.click-checks`, `check-requirements.txt`, `Dockerfile.httpx` and the
preserved `.aiwork/phase61/checks-image/wheels` reproduce the local verifier images.
Copy a Dockerfile and requirements file into a new build directory with those
wheels. Build with `--network=none --pull=false`. Base images already exist;
no model downloads or inference-service changes are needed. The public
[dependency evidence](../../docs/evidence/phase61/dependency-evidence.json) records
every wheel hash and the cached Python documentation inventory hash. Dependencies
were collected from PyPI; actual candidate checks ran offline.

`check_click.py <new-state-root> .aiwork/phase6` runs baseline and candidate checks
in new copies. The state root must exist, its `click-checks` subdirectory must
not exist, and an optional `python.inv` enables the fully offline Sphinx variant.
Never point output directories at the frozen Click tree. No formatter fixes are
permitted. Original environment failures are under `.aiwork/phase61/click-checks`.

To reproduce HTTPX preparation, choose a new state root and clone the pinned tag:

```powershell
$root = '.aiwork/phase61-preparation-replay'
git clone --config core.autocrlf=false --branch 0.28.1 --depth 1 https://github.com/encode/httpx.git "$root/httpx-upstream"
git -C "$root/httpx-upstream" rev-parse HEAD # 26d48e0634e6ee9cdc0533996db289ce4b430177
# Copy/review the existing LOCAL profile configuration into $root/local.toml.
# It must not enable remote models, cloud lifecycle operations or new services.
.venv/Scripts/python.exe examples/phase61/prepare_httpx.py $root
```

This stages unmodified source, `HTTPX-FEATURE.md`, 16 public checks, frozen input
hashes and `httpx-review.json`; it runs only unmodified baseline tests. Existing
prepared files are not overwritten. There is no agent invocation and no final
sealed suite. Current prepared inputs are `.aiwork/phase61/httpx-task` and
`.aiwork/phase61/httpx-input-freeze`; the reviewed-image baseline has 75 passing
upstream tests and nine expected feature failures among 16 public checks.

Before **any measured autonomy trial**, the operator must review and approve the
exact `httpx-review.json` digest, four write roots, public commands, local profile,
image and cumulative resource policy. The public
[preparation summary](../../docs/evidence/phase61/httpx-preparation.json) contains
the current digest. No task manifest is emitted while approval is pending.
Use the existing reviewed planning/workflow and ranked controller for a future
dispatch, after the cumulative deadline/warm-model protocol is resolved.

During such a trial, models may inspect approved code, edit and run approved
public checks. Permission expansion or operator implementation guidance stops
the unassisted classification. Preserve every attempt. Freeze the strongest
candidate before independently creating private final cases. Do not use sealed
feedback for repair or candidate selection. The current resource budget does
not authorize starting that comparison as part of this handoff.
