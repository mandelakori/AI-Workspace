[CmdletBinding()]
param([string]$Python = '', [switch]$InstallOpenCode)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    if ($Python) {
        & $Python -m venv .venv
    } elseif (Get-Command uv.exe -ErrorAction SilentlyContinue) {
        & uv.exe venv --python 3.12 --seed .venv
    } else {
        & py.exe -3.12 -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Creating the Python environment failed.' }
    $venvPython = Join-Path $repo '.venv\Scripts\python.exe'
    & $venvPython -m pip install --disable-pip-version-check .
    if ($LASTEXITCODE -ne 0) { throw 'Installing AI Workspace failed.' }
    if ($InstallOpenCode) {
        & npm.cmd install --global '@opencode/cli@2.0.27'
        if ($LASTEXITCODE -ne 0) { throw 'Installing the tested OpenCode release failed.' }
    }
    if (-not (Test-Path -LiteralPath 'aiwork.local.toml')) {
        Copy-Item -LiteralPath 'aiwork.example.toml' -Destination 'aiwork.local.toml'
    }
    & $venvPython -m aiwork doctor
    if ($LASTEXITCODE -ne 0) { throw 'Doctor failed.' }
} finally {
    Pop-Location
}
