# Native workbench evidence

- `regressions.log` records the 54 targeted tests. Set `AIWORK_TEST_DOCKER_IMAGE`
  to `aiwork-engineering:phase3` and `AIWORK_TEST_OPENCODE_BOUNDARY` to `1` before
  running `python -m unittest discover -s tests -k native -k specialist -k oracle
  -k engineering -k harness_boundary -k trial_budget -k a100_readiness -v`.
- `catalog-editor.log` records four additional installed inert OpenCode tests
  selected by `-k edit_harness -k editor_recovery_harness`.
- `static/` retains metadata, specialist process receipts and REA resource
  results. The positive resource build used `rc.exe /nologo fixture.rc` and
  `cl.exe /nologo /O2 /Fe:reference.exe reference.c fixture.res` with the original
  `examples/native/reference.c` under x64 Developer PowerShell.
- `replay/` retains build and grading receipts. For each replay, copy `target/`,
  `development/`, `frozen/`, `run.json` and `frozen.json` from the original run
  to a disposable directory. Compare inventories against the copied receipts.
  Invoke `native grade <copy> --cases <original-final/inputs.json> --workers 4`
  using the installed offline Docker runner. The exact source run and case-file
  hash are in `replay/replay-results.json`. The historical private case contents
  and raw per-case transcripts remain in `.aiwork`.
- `prepared/` binds the native trial target and existing public assets. The
  executable bundle is `.aiwork/native-workbench-validation/a100-ledger` and
  starts with no source candidate. `preparation-checks.json` records read-only
  endpoint inventory, approval rejection and drift checks. `controller-intake.json`
  records the actual snapshot of a disposable submission. The trial has no grant.
- `preservation.json` records the prior archive hash audit. `evidence-hashes.json`
  binds all files in this committed evidence directory.

To reproduce preparation under a new directory, use the existing archived
ledger runs and fresh local Ghidra receipts as follows. A re-prepared manifest
must be reviewed under its own digest if any input bytes or settings change.

```powershell
$nativePy = '.venv/Scripts/python.exe'
$nativeReference = '.aiwork/phase4/native/f540f4381804475f9bdfc76093968bd9'
$nativePublic = '.aiwork/phase4-followup/controller/native/635e56972ecf44b2a4166734ebbad2db'
$nativeClosed = @($nativeReference, $nativePublic,
    '.aiwork/phase4-followup/controller/native/962023747c5b486eabefa3b0de69390b',
    '.aiwork/phase4-closeout/native-matched/ledger/initial',
    '.aiwork/phase4-closeout/native-best-compiled/ledger')
$nativeExclusions = @()
foreach ($nativeOld in $nativeClosed) {
    Get-ChildItem -LiteralPath (Join-Path $nativeOld 'final') -Filter inputs.json -Recurse |
        ForEach-Object { $nativeExclusions += @('--exclude', $_.FullName) }
}
& $nativePy examples/native/ledger_trial.py prepare '<fresh bundle>' `
    --source $nativeReference --public $nativePublic `
    --static .aiwork/native-workbench-validation/checks `
    --config config/self.local.toml @nativeExclusions
```
