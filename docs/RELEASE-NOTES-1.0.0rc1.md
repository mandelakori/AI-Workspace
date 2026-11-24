# AI Workspace 1.0.0rc1

Operator-review release candidate for the Windows-first engineering controller.
The package is `ai-workspace` and the command is `aiwork`. Python 3.12 or newer
is required. Core Python runtime dependencies are empty. Docker, OpenCode,
Ollama, SSH and native specialist tools are external, opt-in dependencies for
their corresponding execution paths.

## Included

- Reviewed task submission, persistent job state, scoped OpenCode execution,
  exact edits, context persistence, ranked repair and independent verification.
- Calibrated laptop Ollama startup and model residency checks, existing A100
  SSH execution, and bounded opt-in reclamation of an enrolled Ollama model.
- Native PE/ELF intake, Ghidra and REA analysis, and finite differential grading
  for authorized fixtures. Released operation uses existing model installations.
- [Operator guide](OPERATOR-GUIDE.md), [existing-hardware example](../config/rc.example.toml),
  [scoped task template](../examples/scoped-engineering.toml) and
  [Milestones A–E acceptance matrix](ACCEPTANCE.md).

## Open acceptance gates

Complex autonomous engineering acceptance and whole-program stateful native
reconstruction are incomplete. The matched live local/A100 comparison remains
untested as a completed pair. Managed Lambda lifecycle and live external
unloading remain unverified. The [current status](STATUS.md) distinguishes
verified bounded workflows, historical evidence and held grants.

## Upgrade and review

Build and install into a separate release environment using the
[offline commands](OPERATOR-GUIDE.md#install-and-check). Keep current operator
configuration, state, evidence and model stores. The RC example uses its own
queue and the existing shared lane locks. Frozen trial bundles remain tied to
the implementation hashes they originally reviewed.

This candidate is for review on the existing development branch. Publication
and merging require a separate operator decision.

## RC verification

The offline build produced `ai_workspace-1.0.0rc1-py3-none-any.whl` with
SHA-256 `5e2111e936de977e8fd9a9b51059d3255d8e01843f8fa084795e8783103f92bb`.
A fresh venv installed it, passed `pip check`, and reported `aiwork 1.0.0rc1`
from outside the checkout. Package metadata, entrypoint and packaged native
and Pi support files were checked. The installed CLI verified a queued direct
job using pinned offline Docker, accepted each reviewed profile into an
isolated scratch queue without dispatch, and rejected missing config and
unknown profile errors. There was no inference, model download or endpoint
contact. The preceding 260-test release-stabilization run covers the unchanged
runtime code. [RC verification evidence](evidence/v1rc/evidence-hashes.json)
