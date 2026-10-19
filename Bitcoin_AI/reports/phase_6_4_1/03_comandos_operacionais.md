# Comandos operacionais exatos

## Iniciar em observação

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
.\scripts\start_dashboard.ps1
python .\scripts\diagnose_phase6_4_connectivity.py --timeout 10 --summary
python .\scripts\run_phase6_4.py status
```

Abra `http://127.0.0.1:3000/autonomous`. O startup rearma o kill switch e executa o diagnóstico somente leitura. Deixe os serviços ativos para continuar o protocolo prospectivo de 24 horas.

## Acompanhar sem operar

```powershell
python .\scripts\run_phase6_4.py health
python .\scripts\run_phase6_4.py observation-status
python .\scripts\run_phase6_4.py positions
Get-Content .\runtime\phase_6_1\heartbeat.json -Wait
```

## Preparar e autorizar uma sessão experimental Demo

Execute esta seção somente depois de revisar `/autonomous` e decidir autorizar a sessão. Preparar não envia ordem; o segundo comando abre a autorização temporária do processo atual.

```powershell
python .\scripts\run_phase6_4.py prepare-session
python .\scripts\run_phase6_4.py authorize-session --session-id "ID_RETORNADO_PELO_COMANDO_ANTERIOR" --confirm I_AUTHORIZE_10_USDT_BINANCE_DEMO_EXPERIMENTAL
```

Depois da autorização, o motor continua exigindo todos os gates congelados. Ele pode terminar a sessão sem operar se nenhum sinal for elegível.

## Interromper novas entradas e encerrar os serviços

```powershell
python .\scripts\run_phase6_4.py stop-session
.\scripts\stop_dashboard.ps1
```

Se existir posição Demo aberta, o stop mantém o monitor ativo para encerramento seguro e informa a ação necessária. Não force o processo a encerrar sem reconciliar a posição.
