[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('Start','Stop','Status','Foreground')][string]$Action)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
$service = Join-Path $repo '.aiwork\service'
New-Item -ItemType Directory -Path $service -Force | Out-Null
Push-Location $repo
try {
    switch ($Action) {
        'Start' {
            $status = & $python -m aiwork control status | ConvertFrom-Json
            if ($status.background_worker_active -and -not $status.paused) { return }
            & $python -m aiwork control start
            if ($LASTEXITCODE -ne 0) { throw 'Unable to enable dispatch.' }
            if ($status.background_worker_active) { return }
            $run = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
            Start-Process -WindowStyle Hidden -FilePath $python -ArgumentList @('-m','aiwork','worker','--exclusive') `
                -WorkingDirectory $repo -RedirectStandardOutput (Join-Path $service "$run.stdout.log") `
                -RedirectStandardError (Join-Path $service "$run.stderr.log")
        }
        'Stop' { & $python -m aiwork control stop }
        'Status' { & $python -m aiwork control status }
        'Foreground' { & $python -m aiwork worker --exclusive }
    }
} finally {
    Pop-Location
}
