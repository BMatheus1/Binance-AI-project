# 4. Configuração no Windows

No PowerShell, a partir da raiz do projeto:

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
python -m pip install -e ".[demo]"
Copy-Item .env.example .env -ErrorAction Stop
notepad .env
python scripts/run_phase6_2.py environment
```

Se o `.env` já existe, não execute `Copy-Item`. Nunca cole os valores no terminal, em commits ou em mensagens.
