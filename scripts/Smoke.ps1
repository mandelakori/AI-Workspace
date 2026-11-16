param([string]$Profile = 'laptop-ollama')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    & .\.venv\Scripts\python.exe -m aiwork task run examples/coding.toml --profile $Profile --trusted
    if ($LASTEXITCODE -ne 0) { throw "Coding fixture did not verify for $Profile." }
} finally {
    Pop-Location
}
