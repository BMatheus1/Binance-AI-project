# Fase 6 — resultado executivo

A base de engenharia multiactivos foi implementada para BTCUSDT, ETHUSDT e SOLUSDT. Ela inclui coleta pública independente, notícias oficiais a cada 120 segundos, event store causal, classificação conservadora, políticas A/B, seleção por expectativa líquida, risco independente, paper broker, fronteira Binance Demo e ledger encadeado.

O modo inicial é **observação**. Um ciclo público persistiu 45 eventos do Federal Reserve/SEC; o BLS respondeu HTTP 403 e foi registrado como indisponível. Um smoke multiactivos de 15 segundos recebeu 1.116 mensagens, manteve os três livros sincronizados e não observou reconexões, gaps ou invalidações. Nenhum serviço persistente foi deixado ativo, nenhuma credencial foi usada e nenhuma ordem demo ou real foi enviada. O adapter recusa todos os endpoints que não sejam o Demo oficial.

O experimento econômico ainda não começou. Não existe resultado novo de lucro nem evidência de que notícias ajudem. O ajuste direcional por notícias está desligado; na primeira coleta, elas servem como contexto e veto de risco. A política continua em **abstenção integral** até dados prospectivos suficientes.

## Execução

```powershell
$env:PYTHONPATH = 'src'
python scripts/run_phase6.py prepare
python scripts/run_phase6.py news-once
python scripts/run_phase6.py observe-market --seconds 30
python -m pytest -q
```

`news-once` e `observe-market` acessam apenas feeds e mercado públicos. `serve-news` mantém o ciclo de 120 segundos até interrupção manual. Nenhum desses comandos envia ordens.

Leia `00_plano_congelado.md`, `03_fontes_noticias.md`, `09_risco.md`, `15_plano_prospectivo.md` e `16_manual_demo.md` antes de qualquer operação virtual.
