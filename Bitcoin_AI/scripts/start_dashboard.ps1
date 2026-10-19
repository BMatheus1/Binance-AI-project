param(
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendRoot = Join-Path $projectRoot "dashboard\frontend"
$runtimeRoot = Join-Path $projectRoot "runtime\phase_6_3"
$statePath = Join-Path $runtimeRoot "dashboard_processes.json"

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null

function Test-LocalPort([int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.ConnectAsync("127.0.0.1", $Port)
        return $connection.Wait(300) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Get-ListeningProcessId([int]$Port) {
    $pattern = "^\s*TCP\s+127\.0\.0\.1:$Port\s+0\.0\.0\.0:0\s+LISTENING\s+(\d+)\s*$"
    $entry = netstat -ano -p TCP | Select-String -Pattern $pattern | Select-Object -First 1
    if ($entry -and $entry.Matches.Count -gt 0) {
        return [int]$entry.Matches[0].Groups[1].Value
    }
    return $null
}

foreach ($port in @(3000, 8000)) {
    if (Test-LocalPort $port) {
        throw "A porta local $port já está em uso. Execute scripts\stop_dashboard.ps1 ou encerre o serviço correspondente."
    }
}

if (-not (Test-Path (Join-Path $frontendRoot "node_modules"))) {
    throw "Dependências do frontend ausentes. Execute: cd dashboard\frontend; pnpm.cmd install"
}

$env:PYTHONPATH = Join-Path $projectRoot "src"
$env:NEXT_PUBLIC_API_BASE = "http://127.0.0.1:8000"

python (Join-Path $projectRoot "scripts\run_phase6_2.py") kill-switch engage --reason dashboard_observe_start

Write-Host "Validando conectividade somente leitura com a Binance Demo..."
python (Join-Path $projectRoot "scripts\diagnose_phase6_4_connectivity.py") --timeout 8 --summary
if ($LASTEXITCODE -ne 0) {
    Write-Warning "O diagnóstico Demo falhou. O dashboard será iniciado em OBSERVE com ordens bloqueadas."
}

$decisionScript = Join-Path $projectRoot "scripts\run_phase6_1.py"
$decisionService = Start-Process -FilePath "python" `
    -ArgumentList @("`"$decisionScript`"", "serve") `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput (Join-Path $runtimeRoot "decision-service.log") `
    -RedirectStandardError (Join-Path $runtimeRoot "decision-service.err.log") `
    -WindowStyle Hidden -PassThru

$backend = Start-Process -FilePath "python" `
    -ArgumentList @("-m", "uvicorn", "btc_research.dashboard_api:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput (Join-Path $runtimeRoot "backend.log") `
    -RedirectStandardError (Join-Path $runtimeRoot "backend.err.log") `
    -WindowStyle Hidden -PassThru

$nextCli = "node_modules\next\dist\bin\next"
$frontend = Start-Process -FilePath "node" `
    -ArgumentList @($nextCli, "dev", "--hostname", "127.0.0.1", "--port", "3000") `
    -WorkingDirectory $frontendRoot `
    -RedirectStandardOutput (Join-Path $runtimeRoot "frontend.log") `
    -RedirectStandardError (Join-Path $runtimeRoot "frontend.err.log") `
    -WindowStyle Hidden -PassThru

$state = @{
    started_at = [DateTimeOffset]::UtcNow.ToString("o")
    backend_pid = $backend.Id
    frontend_pid = $frontend.Id
    decision_pid = $decisionService.Id
    backend_url = "http://127.0.0.1:8000/healthz"
    dashboard_url = "http://127.0.0.1:3000"
    host_binding = "127.0.0.1"
    trading_enabled = $false
    decision_mode = "OBSERVE"
}
$state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8

$backendReady = $false
$frontendReady = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/healthz" -TimeoutSec 2
        if ($response.status -eq "ok") { $backendReady = $true }
    } catch {
        $backendReady = $false
    }
    try {
        $page = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -TimeoutSec 2 -UseBasicParsing
        if ($page.StatusCode -eq 200) { $frontendReady = $true }
    } catch {
        $frontendReady = $false
    }
    if ($backendReady -and $frontendReady) { break }
    Start-Sleep -Milliseconds 500
}

if (-not ($backendReady -and $frontendReady)) {
    foreach ($processId in @($backend.Id, $frontend.Id, $decisionService.Id)) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
    throw "Dashboard não respondeu. Consulte os logs em runtime\phase_6_3."
}

$backendListenerPid = Get-ListeningProcessId 8000
$frontendListenerPid = Get-ListeningProcessId 3000
if ($backendListenerPid) { $state.backend_pid = $backendListenerPid }
if ($frontendListenerPid) { $state.frontend_pid = $frontendListenerPid }
$state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8

Write-Host "Dashboard: http://127.0.0.1:3000"
Write-Host "API local: http://127.0.0.1:8000"
Write-Host "Worker de decisões: OBSERVE (PID $($decisionService.Id))"
Write-Host "Kill switch ativo; negociação autônoma continua bloqueada até autorização própria da Fase 6.4."

if ($OpenBrowser) {
    Start-Process "http://127.0.0.1:3000"
}
