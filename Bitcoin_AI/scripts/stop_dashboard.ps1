$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$statePath = Join-Path $projectRoot "runtime\phase_6_3\dashboard_processes.json"
$env:PYTHONPATH = Join-Path $projectRoot "src"

python (Join-Path $projectRoot "scripts\run_phase6_2.py") kill-switch engage --reason dashboard_shutdown

if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    foreach ($processId in @($state.backend_pid, $state.frontend_pid, $state.decision_pid)) {
        if ($processId) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "Dashboard encerrado. O kill switch permanece ativo."
