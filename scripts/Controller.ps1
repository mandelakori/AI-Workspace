[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Start','Stop','Status','Foreground')][string]$Action,
    [string]$Config = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
$service = Join-Path $repo '.aiwork\service'
$baseArgs = @('-m', 'aiwork')
$backgroundArgs = @('-m', 'aiwork')
if ($Config) {
    $resolvedConfig = (Resolve-Path -LiteralPath $Config).Path
    $baseArgs += @('--config', $resolvedConfig)
    $backgroundArgs += @('--config', ('"{0}"' -f $resolvedConfig))
}
New-Item -ItemType Directory -Path $service -Force | Out-Null
Push-Location $repo
try {
    switch ($Action) {
        'Start' {
            $status = & $python @baseArgs control status | ConvertFrom-Json
            if ($status.background_worker_active -and -not $status.paused) { return }
            & $python @baseArgs control start
            if ($LASTEXITCODE -ne 0) { throw 'Unable to enable dispatch.' }
            if ($status.background_worker_active) { return }
            $run = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
            Start-Process -WindowStyle Hidden -FilePath $python -ArgumentList ($backgroundArgs + @('worker','--exclusive')) `
                -WorkingDirectory $repo -RedirectStandardOutput (Join-Path $service "$run.stdout.log") `
                -RedirectStandardError (Join-Path $service "$run.stderr.log")
        }
        'Stop' { & $python @baseArgs control stop }
        'Status' { & $python @baseArgs control status }
        'Foreground' { & $python @baseArgs worker --exclusive }
    }
} finally {
    Pop-Location
}
