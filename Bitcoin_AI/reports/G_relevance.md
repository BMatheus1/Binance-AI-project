# G — Relevância estatística

Ablações usam a mesma regressão logística e calibração; delta negativo favorece adicionar o grupo a preços. Remoção de redundância usa correlação absoluta >0.98 somente no treino. Não se apagam variáveis do catálogo.

| Horizonte | Grupo | Features selecionadas | Delta log loss validação vs preços |
|---|---|---|---|
| 1 | logistic_price | 1 | +0.000000 |
| 1 | logistic_price_action | 9 | -0.016659 |
| 1 | logistic_price_trend | 13 | -0.000739 |
| 1 | logistic_price_volatility | 6 | -0.020489 |
| 1 | logistic_price_volume | 6 | -0.001557 |
| 1 | logistic_price_trend_volume | 18 | -0.002043 |
| 1 | logistic_all_selected | 35 | -0.020567 |
| 5 | logistic_price | 1 | +0.000000 |
| 5 | logistic_price_action | 9 | -0.000217 |
| 5 | logistic_price_trend | 13 | -0.001150 |
| 5 | logistic_price_volatility | 6 | -0.000717 |
| 5 | logistic_price_volume | 6 | -0.000361 |
| 5 | logistic_price_trend_volume | 18 | -0.001065 |
| 5 | logistic_all_selected | 35 | -0.000852 |

Importância por feature e grupo: `interpretability/importance.json` (deslocamentos circulares na validação). Walk-forward: `experiments/walk_forward.json`, dois folds anteriores a 2026 para regressão logística e baseline. Estabilidade mensal, calibração e ICs de bootstrap diário estão no JSON final. Sem inferência causal. A avaliação formal com correção por múltiplos testes e walk-forward de todos os algoritmos permanece pendente.
