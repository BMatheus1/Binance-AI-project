# Execução no Windows

Instalação:

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
python -m pip install -e ".[demo,dashboard]"
cd dashboard\frontend
pnpm.cmd install
pnpm.cmd run build
```

Iniciar:

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
powershell -ExecutionPolicy Bypass -File scripts\start_dashboard.ps1 -OpenBrowser
```

Encerrar com o kill switch ativo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_dashboard.ps1
```
