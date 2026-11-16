[CmdletBinding()]
param(
    [string]$Profile = 'a100-existing',
    [string]$Config = '',
    [string]$GhidraHeadless = '',
    [string]$Python = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $Config) { $Config = Join-Path $repo 'aiwork.local.toml' }
if (-not $Python) { $Python = Join-Path $repo '.venv\Scripts\python.exe' }
if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    throw 'Run this script in a Visual Studio x64 Developer PowerShell with MSVC installed.'
}
if (-not $GhidraHeadless) { throw 'Set -GhidraHeadless to the installed analyzeHeadless.bat.' }
$runner = Join-Path $repo ('.aiwork\native-fixtures\' + [Guid]::NewGuid().ToString('N'))
$work = New-Item -ItemType Directory -Path (Join-Path $runner 'work') -Force
$private = New-Item -ItemType Directory -Path (Join-Path $runner 'private')
$fixture = Join-Path $repo 'examples\native'
Copy-Item -LiteralPath (Join-Path $fixture 'candidate.c') -Destination $work.FullName
Copy-Item -LiteralPath (Join-Path $fixture 'differential.py') -Destination $private.FullName
Push-Location $runner
try {
    & cl.exe /nologo /O2 /Fe:"$($work.FullName)\reference.exe" (Join-Path $fixture 'reference.c')
    if ($LASTEXITCODE -ne 0) { throw 'Reference compilation failed.' }
    $configData = if (Test-Path -LiteralPath $Config) { Get-Content -Raw -LiteralPath $Config } else { '' }
    if ($configData -match '(?m)^\s*\[specialists\.ghidra\]') {
        throw 'Pass a configuration without a specialists.ghidra table to this fixture script.'
    }
    $headless = (Resolve-Path -LiteralPath $GhidraHeadless).Path.Replace('\', '/')
    $encodedHeadless = ConvertTo-Json -InputObject $headless -Compress
    $stateLine = 'state = ' + (ConvertTo-Json -InputObject ((Join-Path $repo '.aiwork').Replace('\', '/')) -Compress)
    $configData = $configData -replace '(?m)^\s*state\s*=.*(?:\r?\n|$)', ''
    $configData = $stateLine + "`n" + $configData + "`n[specialists.ghidra]`nheadless = $encodedHeadless`nfunction = 'shipping_points'`n"
    Set-Content -LiteralPath 'native-config.toml' -Value $configData -Encoding utf8NoBOM
    @'
objective = "Use the static Ghidra evidence for the exported shipping_points function in the self-authored reference executable. Reconstruct it in candidate.c. Preserve the command-line interface."
workspace = "work"
kind = "agent"
category = "toy-reconstruction"
specialist = "ghidra"
inputs = ["reference.exe", "candidate.c"]
deliverables = ["candidate.c"]
verification_dir = "private"
complexity = 4
attempts = 1
timeout = 360

[[checks]]
argv = ["cl.exe", "/nologo", "/O2", "/Fe:candidate.exe", "candidate.c"]
timeout = 45

[[checks]]
argv = ["{python}", "{verification}/differential.py"]
stdout = "182 finite cases matched\n"
timeout = 90
'@ | Set-Content -LiteralPath 'task.toml' -Encoding utf8NoBOM
    & $Python -m aiwork --config (Join-Path $runner 'native-config.toml') task run (Join-Path $runner 'task.toml') --profile $Profile --trusted
    if ($LASTEXITCODE -ne 0) { throw "Native fixture did not verify. Fixture: $runner" }
} finally {
    Pop-Location
}
