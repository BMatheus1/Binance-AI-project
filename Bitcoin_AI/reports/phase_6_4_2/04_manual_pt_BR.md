# Manual operacional — somente Binance Spot Demo

## Iniciar observação

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
.\scripts\start_dashboard.ps1 -OpenBrowser
```

Use esse comando quando os serviços estiverem parados. Ele inicia supervisor, API e interface e aciona o kill switch. Se já estiverem funcionando, abra [o dashboard local](http://127.0.0.1:3000). Não execute duas instâncias. Somente atualizar a interface/API, preservando o processo do robô, é possível por `scripts\restart_dashboard_ui.ps1`.

Em **Inteligência**, veja a última proposta por ativo, probabilidade de alta em cinco minutos, custo e motivo. “Não comprar” significa abstenção. ETH/SOL sem modelo validado aparecem indisponíveis para negociação. Padrões ficam nas evidências avançadas e não mudam a estratégia experimental. Em **Robô Autônomo**, confira autorização, conta fictícia, reconciliação, posição e histórico. Em **Operações/Resultados**, diagnósticos permanecem separados da estratégia. Em **Saúde**, confira falhas e timestamps.

## Verificar sem operar

```powershell
python .\scripts\run_phase6_4.py positions
python .\scripts\run_phase6_4.py health
python .\scripts\run_phase6_4.py observation-status
python .\scripts\run_phase6_4.py limits
python .\scripts\diagnose_phase6_4_connectivity.py --timeout 8 --summary
python .\scripts\run_phase6_4_2.py evidence
```

Para uma auditoria autenticada de reconciliação, mantenha o kill switch ativo. **Não pare uma sessão com posição aberta apenas para executar um diagnóstico**: o motor precisa acompanhar a saída.

```powershell
python .\scripts\run_phase6_4.py stop-session
python .\scripts\run_phase6_4.py reconciliation-check
```

Esses comandos bloqueiam entradas; uma posição aberta continua sob o monitor e pode ser encerrada pelo kill switch. Um estado “reconciliado” significa consistência com a corretora, não lucro ou autorização.

## Preparar e autorizar outra sessão

Faça isso somente após revisar reconciliação saudável, dados atuais, limites e ausência de estados desconhecidos. Também é possível **preparar** pela página Robô Autônomo; ela mostra o comando de autorização correspondente. Preparar não envia ordens.

```powershell
$demoPreparedJson = python .\scripts\run_phase6_4.py prepare-session
if ($LASTEXITCODE -ne 0) { throw "Não foi possível preparar a sessão Demo" }
$demoPrepared = $demoPreparedJson | ConvertFrom-Json
$demoPrepared | Select-Object session_id, policy, symbol, quote_amount, orders_sent
```

O passo seguinte é a autorização explícita e permite compras/vendas virtuais sem outra confirmação por ordem, apenas dentro dos limites e da duração da sessão. Não é necessário executá-lo para observar o mercado. **Não foi executado durante esta implementação.**

```powershell
python .\scripts\run_phase6_4.py authorize-session --session-id $demoPrepared.session_id --confirm I_AUTHORIZE_10_USDT_BINANCE_DEMO_EXPERIMENTAL
```

Política A, BTCUSDT, horizonte de cinco minutos, alvo de 10 USDT, uma posição e sessão de até 120 minutos. O motor pode permanecer sem comprar: a probabilidade mínima continua 0,60, com filtros e risco independentes. Não há garantia de vender com lucro.

## Interromper e encerrar

```powershell
python .\scripts\run_phase6_4.py stop-session
python .\scripts\run_phase6_4.py positions
.\scripts\stop_dashboard.ps1
```

O script preserva o monitor enquanto há posição sem saída confirmada e pode recusar o encerramento. Não desligue à força para contornar essa condição. Para reiniciar, execute o comando de observação novamente; é necessária uma nova autorização após o boot.

## Auditar a pesquisa

```powershell
python .\scripts\run_phase6_4_2.py audit
python .\scripts\run_phase6_4_2.py benchmarks
python .\scripts\run_phase6_4_2.py evidence
python -m pytest -q --junitxml=reports/phase_6_4_2/tests.xml
Push-Location dashboard\frontend
npm.cmd run build
Pop-Location
```

O protocolo de 24 horas mantém o mesmo SQLite e a mesma sessão de observação após reinícios. Lacunas e falhas ficam registradas; transcorrer 24 horas não transforma disponibilidade insuficiente em aprovação operacional.
