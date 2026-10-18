# Fase 3 — plano técnico congelado

Data: 17/10/2026. Plano registrado antes da ingestão e dos experimentos.

## Escopo temporal

Piloto oficial Binance Spot BTCUSDT AggTrades: **01/10/2026 a 14/10/2026**, inclusive. O intervalo é posterior ao teste final da Fase 1. Como será observado durante desenvolvimento da Fase 3, seus resultados serão classificados como exploratórios e não como teste confirmatório futuro.

Julho–setembro/2026 continua consumido e não poderá orientar modelos, features ou políticas novos.

## Etapas e recursos

1. Auditar classes, log loss, calibração, causalidade e interpretação econômica das Fases 1–2.
2. Baixar no máximo 14 arquivos diários AggTrades e seus CHECKSUMs do repositório oficial `data.binance.vision`.
3. Validar ZIP, SHA-256 oficial, esquema, timestamps em microssegundos, IDs agregados, intervalos cobertos, duplicatas e ordem. Lacunas de IDs de trades subjacentes serão registradas sem assumir que todo salto é perda, pois AggTrades agregam uma ordem tomadora.
4. Processar um arquivo por vez, produzir Parquet diário e agregados causais de um minuto. Preservar os ZIPs e checksums originais em `data/phase_3/raw/`.
5. Construir catálogo de microestrutura e comparar A (37 candles), B (somente AggTrades), C (combinação) e D (subconjunto fixado em validação temporal), separadamente em 1m e 5m.
6. Implementar coletor público WebSocket, estado de livro que invalida após lacuna, ledger prospectivo append-only, resolução posterior e paper trading sem ordens.
7. Testar componentes offline. Um smoke test de rede ao vivo será curto e apenas de mercado público; nenhum serviço ficará ativo ao final.

CPU: até quatro threads. Memória: leitura em chunks e partições diárias. Disco: somente 14 dias no piloto; nenhuma expansão automática para 30–90 dias.

## Riscos metodológicos

- AggTrade representa uma ordem tomadora agregada, não cada negócio individual.
- O campo `isBuyerMaker=true` implica agressor vendedor; direção agressora é inferida dessa convenção documentada.
- AggTrades históricos não contêm bid/ask, spread nem profundidade. Esses campos só poderão ser medidos prospectivamente.
- Um único intervalo de 14 dias é curto, dependente do regime e incapaz de demonstrar vantagem sustentável.
- Comparações A–D devem usar exatamente os mesmos minutos e divisões temporais.
- Seleção D e limiares serão desenvolvimento interno. Nenhum resultado autoriza dinheiro real.
- Se o download oficial ou a qualidade dos dados falhar, a limitação será registrada; dados não serão inventados.

## Critério de decisão

Microestrutura só será considerada candidata se melhorar log loss e Brier de forma consistente nas divisões cronológicas, mantiver calibração e não piorar a análise econômica após custos. Na ausência dessa evidência, permanece abstenção integral.
