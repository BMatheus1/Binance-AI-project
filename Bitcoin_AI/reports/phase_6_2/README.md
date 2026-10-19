# Fase 6.2 — operação

Comandos a partir de `D:\Binance AI project\Bitcoin_AI`:

```powershell
python scripts/run_phase6_2.py environment
python scripts/run_phase6_2.py public-check
python scripts/run_phase6_2.py auth-check
python scripts/run_phase6_2.py balances
python scripts/run_phase6_2.py symbol-rules --symbol BTCUSDT --quote 10
python scripts/run_phase6_2.py endpoint-safety
python scripts/run_phase6_2.py diagnostic-plan --symbol BTCUSDT --quote 10
python scripts/run_phase6_2.py kill-switch status
python scripts/run_phase6_2.py open-orders --symbol BTCUSDT
python scripts/run_phase6_2.py results
python scripts/run_phase6_2.py autonomous-status
```

O fluxo autorizado de ordem Demo exige, nesta ordem, definir localmente `BITCOIN_AI_ENABLE_DEMO_ORDERS=I_UNDERSTAND_DEMO_ONLY`, liberar o kill switch e executar o comando diagnóstico com a frase explícita. Não execute antes de revisar o plano:

```powershell
python scripts/run_phase6_2.py kill-switch clear --confirm I_AUTHORIZE_BINANCE_DEMO_ONLY
python scripts/run_phase6_2.py diagnostic-order --symbol BTCUSDT --quote 10 --confirm I_AUTHORIZE_ONE_DEMO_DIAGNOSTIC
python scripts/run_phase6_2.py open-orders --symbol BTCUSDT
python scripts/run_phase6_2.py results
```

Para interromper novas entradas imediatamente:

```powershell
python scripts/run_phase6_2.py kill-switch engage --reason parada_manual
python scripts/run_phase6_2.py stop-services
```

Após diagnóstico reconciliado e aprovação prospectiva registrada, a habilitação prevista é:

```powershell
python scripts/run_phase6_2.py enable-autonomous --confirm I_AUTHORIZE_DEMO_AUTONOMOUS
python scripts/run_phase6_2.py run-autonomous
```

Atualmente esses dois últimos comandos permanecem bloqueados pelos pré-requisitos. Não altere os indicadores de aprovação apenas para contornar o bloqueio.
