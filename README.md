# AI Workspace 1.0.0rc1

AI Workspace is a Windows-first controller for scoped engineering jobs. It
stages reviewed inputs, selects an execution profile, runs OpenCode or a
deterministic task, and keeps independently verified candidates and receipts.
The harness and workspace stay on Windows when inference uses the existing
A100 over SSH.

## Use the release candidate

- [Operator guide](docs/OPERATOR-GUIDE.md) covers install, the exact laptop and A100 commands, memory admission, native analysis, and verification.
- [Existing hardware config](config/rc.example.toml) and [scoped engineering manifest](examples/scoped-engineering.toml) are editable operator examples. They are separate from frozen trial bundles.
- [Acceptance matrix](docs/ACCEPTANCE.md), [current status and grants](docs/STATUS.md), and [release notes](docs/RELEASE-NOTES-1.0.0rc1.md) state what the evidence supports.

For a fresh Windows environment, PowerShell 7, Python 3.12+ and Git are enough
for the first direct check. Bootstrap may contact package indexes. The
operator guide provides an offline wheel build and isolated install for the
existing machine. Run these from the checkout after installing the RC into
`.venv`:

```powershell
$ai = '.\.venv\Scripts\aiwork.exe'
& $ai --version
& $ai doctor
& $ai task run examples/direct.toml --trusted
```

Scoped engineering with the RC examples requires OpenCode, the selected
inference profile and the installed Linux Docker verifier. The local path has
passed an end-to-end bounded smoke. Complex autonomous engineering acceptance
and whole-program stateful reconstruction are incomplete. The matched live
cross-plane comparison remains untested as a completed pair.

[Architecture](docs/ARCHITECTURE.md) · [Engineering recipes](docs/ENGINEERING.md) · [Security](docs/SECURITY.md) · [Next steps](docs/NEXT_STEPS.md)
