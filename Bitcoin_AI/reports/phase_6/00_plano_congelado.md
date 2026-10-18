# Fase 6 — protocolo congelado

O universo inicial é `BTCUSDT`, `ETHUSDT` e `SOLUSDT`. O ciclo de notícias é de 120 segundos. As políticas A (sem notícias) e B (com notícias) recebem os mesmos instantes elegíveis, custos e limites. A política B pode usar notícias recebidas e analisadas antes da decisão; nesta primeira versão, notícias aplicam contexto e veto de risco, mas não acrescentam retorno direcional porque esse efeito ainda não foi calibrado prospectivamente.

A métrica primária será a diferença pareada do retorno líquido após custos. O mínimo antes de qualquer conclusão é 30 dias futuros e 200 operações resolvidas por política, além de estabilidade temporal e controle de testes múltiplos por Holm. Esses mínimos não garantem evidência; apenas impedem análise prematura.

Julho–setembro de 2026 permanece consumido. Nenhum período histórico congelado será reutilizado para selecionar regras da Fase 6. A configuração completa está em `configs/phase_6.json`.

Modos: observação por padrão, paper local opcional e Binance Demo desabilitada. Dinheiro real e endpoints de produção não fazem parte do software.
