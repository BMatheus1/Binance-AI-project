# Fase 3 — resultado executivo

O piloto oficial de 14 dias foi concluído com ingestão íntegra, features causais, comparação A–D, coletor público, ledger imutável e paper trading. Nenhuma ordem real ou API autenticada foi implementada.

As variantes escolhidas apenas para observação prospectiva foram `D_selected_train_only` em 1m e `A_original_xgboost_37` em 5m. Em 1m, a escolhida obteve accuracy de 51.3112% e log loss de 0.767187, contra 51.3112% e 0.768756 do XGBoost original com 37 features. Em 5m, a escolhida obteve 50.6388% e 0.707734, contra 50.6388% e 0.707734 do mesmo baseline.

O ganho de log loss da variante escolhida em 1m foi -0.001569. Em 5m, acrescentar microestrutura mudou a log loss em +0.000865 e o próprio XGBoost original venceu A–D. A microestrutura não apresentou vantagem consistente entre horizontes. Todos os cenários Spot ficaram negativos, inclusive a 5 bps por lado; resultados positivos isolados de payout não têm intervalo diário confiável em apenas três dias.

A validação cobre só três dias, e a escolha foi feita nesse mesmo bloco; portanto, não existe teste independente posterior para promoção. A política oficial permanece em **abstenção integral**.

Consulte `results.json` para números completos, gaps, probabilidades, cenários de custo e limitações.
