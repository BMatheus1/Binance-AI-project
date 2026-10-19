$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtimeRoot = Join-Path $projectRoot 'runtime\phase_6_3'
$statePath = Join-Path $runtimeRoot 'dashboard_processes.json'
$enginePath = Join-Path $projectRoot 'runtime\phase_6_4\engine.json'
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$engineBefore = Get-Content -LiteralPath $enginePath -Raw | ConvertFrom-Json

function Get-UiListener([int]$Port) {
    $pattern = "^\s*TCP\s+127\.0\.0\.1:$Port\s+0\.0\.0\.0:0\s+LISTENING\s+(\d+)\s*$"
    $entry = netstat -ano -p TCP | Select-String -Pattern $pattern | Select-Object -First 1
    if ($entry) { return [int]$entry.Matches[0].Groups[1].Value }
    return $null
}

# Validate ownership before touching either listener. The trading worker is
# deliberately absent from the list; no authorization/kill-switch CLI is used.
foreach ($item in @(@{Port=8000; Id=$state.backend_pid}, @{Port=3000; Id=$state.frontend_pid})) {
    $listener = Get-UiListener $item.Port
    if ($listener -and $listener -ne $item.Id) {
        throw "A porta $($item.Port) pertence a outro processo; reinício da interface interrompido."
    }
}
foreach ($processId in @($state.backend_pid, $state.frontend_pid)) {
    if ($processId) { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue }
}

$stamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$env:PYTHONPATH = Join-Path $projectRoot 'src'
$env:NEXT_PUBLIC_API_BASE = 'http://127.0.0.1:8000'
$backend = Start-Process -FilePath 'python' -ArgumentList @('-m','uvicorn','btc_research.dashboard_api:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot "$stamp-backend.log") -RedirectStandardError (Join-Path $runtimeRoot "$stamp-backend.err.log")
$frontend = Start-Process -FilePath 'node' -ArgumentList @('node_modules\next\dist\bin\next','dev','--hostname','127.0.0.1','--port','3000') -WorkingDirectory (Join-Path $projectRoot 'dashboard\frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot "$stamp-frontend.log") -RedirectStandardError (Join-Path $runtimeRoot "$stamp-frontend.err.log")
$state.backend_pid = $backend.Id
$state.frontend_pid = $frontend.Id
$state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
for ($attempt=0; $attempt -lt 30; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/healthz' -TimeoutSec 2
        $page = Invoke-WebRequest -Uri 'http://127.0.0.1:3000' -TimeoutSec 2 -UseBasicParsing
        if ($health.status -eq 'ok' -and $page.StatusCode -eq 200) { break }
    } catch { }
    Start-Sleep -Milliseconds 500
}
$backendListener = Get-UiListener 8000
$frontendListener = Get-UiListener 3000
if (-not $backendListener -or -not $frontendListener) { throw 'A interface não respondeu; consulte os logs de ui restart.' }
$state.backend_pid = $backendListener
$state.frontend_pid = $frontendListener
$state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
$engineAfter = Get-Content -LiteralPath $enginePath -Raw | ConvertFrom-Json
if ($engineAfter.boot_id -ne $engineBefore.boot_id) { throw 'O motor foi reiniciado por outro processo durante a atualização da interface.' }
Write-Output "Interface atualizada: http://127.0.0.1:3000"
Write-Output "Worker preservado: PID $($state.decision_pid); boot_id $($engineAfter.boot_id)"
Write-Output "Estado do motor: $($engineAfter.state); ordens habilitadas: $($engineAfter.orders_enabled)"
