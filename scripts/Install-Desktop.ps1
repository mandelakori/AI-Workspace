[CmdletBinding()]
param([switch]$Launch)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'The AI-Workspace runtime is missing. Run the existing Bootstrap.ps1 once.'
}
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
if (-not (Test-Path -LiteralPath $desktop -PathType Container)) {
    throw 'Windows could not locate your Desktop folder.'
}
$path = Join-Path $desktop 'AI-Workspace.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($path)
if ((Test-Path -LiteralPath $path) -and $shortcut.TargetPath -ne $python) {
    throw "A different shortcut already uses $path"
}
$shortcut.TargetPath = $python
$shortcut.Arguments = '-m aiwork.desktop'
$shortcut.WorkingDirectory = $repo
$shortcut.Description = 'Open the local AI-Workspace engineering application'
$shortcut.Save()
Write-Output $path
if ($Launch) {
    Start-Process -FilePath $python -ArgumentList '-m','aiwork.desktop' -WorkingDirectory $repo -WindowStyle Hidden
}
