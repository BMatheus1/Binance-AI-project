# Comandos exatos

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
.\scripts\start_dashboard.ps1 -OpenBrowser
python .\scripts\run_phase6_4.py status
python .\scripts\run_phase6_4.py observation-status
python .\scripts\run_phase6_4.py policy
python .\scripts\run_phase6_4.py limits
python .\scripts\run_phase6_4.py prepare-session
python .\scripts\run_phase6_4.py authorize-session --session-id ID_EXIBIDO --confirm I_AUTHORIZE_10_USDT_BINANCE_DEMO_EXPERIMENTAL
python .\scripts\run_phase6_4.py positions
python .\scripts\run_phase6_4.py results
python .\scripts\run_phase6_4.py status
python .\scripts\run_phase6_4.py stop-session
.\scripts\stop_dashboard.ps1
```

O comando `authorize-session` é o passo que permite ordens virtuais se todos os gates passarem. Não o execute para mera observação.
