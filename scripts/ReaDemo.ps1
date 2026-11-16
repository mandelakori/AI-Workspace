[CmdletBinding()]
param([string]$ReaEntry = '')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not $ReaEntry) { $ReaEntry = Join-Path $repo '.aiwork\rea-dependency\node_modules\rea-agents\scripts\rea.mjs' }
if (-not (Test-Path -LiteralPath $ReaEntry)) { throw 'Run Bootstrap.ps1 -InstallRea or pass the pinned REA entry point.' }
if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    throw 'Run this script in an x64 Visual Studio Developer PowerShell with MSVC installed.'
}
$entry = (Resolve-Path -LiteralPath $ReaEntry).Path.Replace('\', '/')
$runner = New-Item -ItemType Directory -Path (Join-Path $repo ('.aiwork\rea-fixtures\' + [Guid]::NewGuid().ToString('N'))) -Force
Push-Location $runner.FullName
try {
    New-Item -ItemType Directory -Path project | Out-Null
    & cl.exe /nologo /O2 /Fe:project\reference.exe (Join-Path $repo 'examples\native\reference.c')
    if ($LASTEXITCODE -ne 0) { throw 'Reference compilation failed.' }
    $encodedState = ConvertTo-Json -InputObject ((Join-Path $repo '.aiwork').Replace('\', '/')) -Compress
    $encodedEntry = ConvertTo-Json -InputObject $entry -Compress
    @"
state = $encodedState

[specialists.rea]
format = "json"
argv = ["node.exe", $encodedEntry, "inspect-pe-resources", "{binary}", "--format", "json", "--max-entries", "256"]
"@ | Set-Content -LiteralPath 'rea-config.toml' -Encoding utf8NoBOM
    @'
objective = "Collect REA PE resource metadata from the self-authored reference executable."
workspace = "project"
kind = "direct"
category = "toy-static-analysis"
specialist = "rea"
inputs = ["reference.exe"]
timeout = 120

[[checks]]
argv = ["{python}", "-c", "from pathlib import Path; assert Path('reference.exe').read_bytes()[:2] == b'MZ'"]
'@ | Set-Content -LiteralPath 'task.toml' -Encoding utf8NoBOM
    Push-Location $repo
    try {
        & $python -m aiwork --config (Join-Path $runner.FullName 'rea-config.toml') task run (Join-Path $runner.FullName 'task.toml') --trusted
        if ($LASTEXITCODE -ne 0) { throw 'REA fixture did not verify.' }
    } finally { Pop-Location }
} finally { Pop-Location }
