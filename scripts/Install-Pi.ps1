param([string]$Destination = '')
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $Destination) { $Destination = Join-Path $projectRoot '.aiwork\pi-dependency' }
$target = [IO.Path]::GetFullPath($Destination)
$allowed = [IO.Path]::GetFullPath((Join-Path $projectRoot '.aiwork')) + [IO.Path]::DirectorySeparatorChar
if (-not $target.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Pi dependencies must be installed beneath this project .aiwork directory.'
}
$node = Get-Command node.exe -ErrorAction Stop
$npm = Get-Command npm.cmd -ErrorAction Stop
$version = [version]((& $node.Source --version).TrimStart('v'))
if ($version -lt [version]'22.19.0') { throw 'Pi 1.6.0 requires Node 22.19 or newer.' }
$package = Join-Path $target 'node_modules\@earendil-works\pi-coding-agent\package.json'
if (Test-Path -LiteralPath $package) {
    if ((Get-Content -Raw -LiteralPath $package | ConvertFrom-Json).version -ne '1.6.0') {
        throw 'Existing Pi dependency has a different version; review it before replacing it.'
    }
    Write-Output "Pi 1.6.0 already installed at $target"
    exit 0
}
if ((Test-Path -LiteralPath (Join-Path $target 'node_modules'))) {
    throw 'Unknown existing dependency directory; choose a new .aiwork destination.'
}
New-Item -ItemType Directory -Path $target -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot 'harnesses\pi\package.json') -Destination $target
Copy-Item -LiteralPath (Join-Path $projectRoot 'harnesses\pi\package-lock.json') -Destination $target
& $npm.Source ci --prefix $target --ignore-scripts --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Pinned Pi installation failed.' }
Write-Output "Installed pinned Pi 1.6.0 at $target. No models were downloaded."
