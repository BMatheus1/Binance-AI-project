# Correção operacional — pipeline contínuo de decisões

Validado em 19/10/2026, exclusivamente em modo `OBSERVE`, com kill switch ativo e sem envio de ordens.

## Diagnóstico

O comando `run_phase6_1.py serve` executava notícias, três coletores públicos e heartbeat, mas nenhum componente transformava candles em previsões e decisões. O dashboard lia ledgers sem preencher o estado mais recente de cada política. Não existia tabela normalizada de avaliações.

## Implementação

- `ContinuousDecisionWorker` recebe apenas candles de um minuto encerrados e sincronizados de BTCUSDT, ETHUSDT e SOLUSDT.
- Cotações e livro são coalescidos em memória; somente candles encerrados entram na fila.
- Lacunas observadas após reconexão são recuperadas pelo endpoint público, sem interpolação.
- O worker aguarda o `close_time` nominal antes da inferência e rejeita relógio futuro excessivo.
- Os quatro modelos congelados da Fase 4 produzem probabilidades BTC para 1, 5, 15 e 30 minutos, com hash validado.
- O escopo congelado é BTC. ETH e SOL recebem os mesmos instantes de avaliação, mas abstêm explicitamente porque não existe modelo validado para esses ativos.
- Custos usam spread observado mais taxas e slippage congelados. O retorno bruto esperado fica nulo porque não há calibração prospectiva válida de magnitude.
- Cada ativo/política é persistido em `evaluations.sqlite3`; cada ciclo também entra no ledger encadeado por hash.
- Qwen3 é carregado sob demanda. Falha de Qwen afeta as políticas C/D e não paralisa A/B.
- Uma trava do sistema operacional impede supervisores duplicados.

## Evidência supervisionada

O ensaio principal durou aproximadamente 196 segundos e o smoke final, após correções de fila e causalidade, durou aproximadamente 81 segundos. O estado final observado foi:

- três ativos com 240 candles de aquecimento e cotação/livro disponíveis;
- 4 ciclos causais válidos no snapshot de `2026-10-19T03:54:15Z`, totalizando 48 avaliações válidas;
- 12 avaliações por ciclo: 3 ativos × 4 políticas;
- fila zerada e nenhum evento descartado;
- todas as decisões em abstenção;
- zero ordens enviadas;
- ledger íntegro.

O último ciclo desse snapshot foi avaliado em `2026-10-19T03:54:15.170901+00:00`, após o fechamento nominal `2026-10-19T03:53:59.999000+00:00`. Para BTCUSDT no horizonte de um minuto, o modelo produziu `p_down=0.494440`, `p_tie=0.037534` e `p_up=0.468026`; a política absteve por não atingir o limiar congelado e por não haver expectativa bruta calibrada. O custo estimado observado foi `14.001212 bps`.

Duas execuções de smoke anteriores produziram 24 linhas antes do fechamento nominal por menos de um segundo devido a desvio de relógio da origem. Essas linhas foram marcadas `causal_valid=0`, receberam registros explícitos de invalidação no ledger e são excluídas do dashboard e de análises.

O smoke Qwen3 existente continua válido: saída estruturada válida, modelo `Qwen/Qwen3-0.6B`, revisão congelada, CPU e nenhuma ordem.

Nenhum resultado desta correção sustenta lucratividade ou habilitação autônoma.
