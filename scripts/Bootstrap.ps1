[CmdletBinding()]
param([string]$Python = '', [switch]$InstallOpenCode, [switch]$InstallQwen, [switch]$InstallRea)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    $venvPython = Join-Path $repo '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        if ($Python) {
            & $Python -m venv .venv
        } elseif (Get-Command uv.exe -ErrorAction SilentlyContinue) {
            & uv.exe venv --python 3.12 --seed .venv
        } else {
            & py.exe -3.12 -m venv .venv
        }
        if ($LASTEXITCODE -ne 0) { throw 'Creating the Python environment failed.' }
    }
    & $venvPython -m pip install --disable-pip-version-check .
    if ($LASTEXITCODE -ne 0) { throw 'Installing AI Workspace failed.' }
    if ($InstallOpenCode) {
        & npm.cmd install --global '@opencode/cli@2.0.27'
        if ($LASTEXITCODE -ne 0) { throw 'Installing the tested OpenCode release failed.' }
    }
    if ($InstallQwen) {
        & npm.cmd install --prefix .aiwork\qwen-dependency --ignore-scripts --no-audit --no-fund '@qwen-code/qwen-code@0.27.4'
        if ($LASTEXITCODE -ne 0) { throw 'Installing Qwen Code failed.' }
    }
    if ($InstallRea) {
        & npm.cmd install --prefix .aiwork\rea-dependency --ignore-scripts --no-audit --no-fund 'rea-agents@6.7.0'
        if ($LASTEXITCODE -ne 0) { throw 'Installing REA failed.' }
    }
    if (-not (Test-Path -LiteralPath 'aiwork.local.toml')) {
        Copy-Item -LiteralPath 'aiwork.example.toml' -Destination 'aiwork.local.toml'
    }
    & $venvPython -m aiwork doctor
    if ($LASTEXITCODE -ne 0) { throw 'Doctor failed.' }
} finally {
    Pop-Location
}
