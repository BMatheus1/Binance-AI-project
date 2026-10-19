$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$statePath = Join-Path $projectRoot "runtime\phase_6_3\dashboard_processes.json"
$env:PYTHONPATH = Join-Path $projectRoot "src"

$phase64 = Join-Path $projectRoot "scripts\run_phase6_4.py"
$stopJson = python $phase64 stop-session | ConvertFrom-Json
if ($stopJson.open_position) {
    Write-Host "Posição Demo aberta: novas entradas bloqueadas; aguardando o motor solicitar a saída."
    $closed = $false
    for ($attempt = 0; $attempt -lt 12; $attempt++) {
        Start-Sleep -Seconds 5
        $status = python $phase64 status | ConvertFrom-Json
        if (-not $status.autonomous.open_position) {
            $closed = $true
            break
        }
    }
    if (-not $closed) {
        throw "A plataforma permaneceu ativa porque existe posição Demo não encerrada. Use o comando emergency-close após revisar o estado."
    }
}

if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    foreach ($processId in @($state.backend_pid, $state.frontend_pid, $state.decision_pid)) {
        if ($processId) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "Dashboard encerrado. O kill switch permanece ativo."
