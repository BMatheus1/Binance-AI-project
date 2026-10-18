# 08 — Resultado completo do Kronos no Colab

Δ log loss = Kronos − modelo congelado da Fase 4; valor negativo favorece Kronos.

| Horizonte | Melhor variante Kronos | Accuracy | Baseline | Log loss | Baseline | Δ LL | IC95% diário | ECE |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1m | pretrained_calibrated | 0.5000 | 0.5234 | 0.800020 | 0.761938 | +0.038081 | [+0.010736, +0.071616] | 0.0593 |
| 5m | pretrained_calibrated | 0.5117 | 0.5156 | 0.702651 | 0.695215 | +0.007436 | [-0.006070, +0.021706] | 0.0118 |
| 15m | pretrained_calibrated | 0.5703 | 0.4453 | 0.698068 | 0.697741 | +0.000326 | [-0.018720, +0.021071] | 0.0670 |
| 30m | pretrained_calibrated | 0.5195 | 0.4961 | 0.703745 | 0.694621 | +0.009123 | [-0.016520, +0.032403] | 0.0676 |

### Log loss de todas as variantes

| Variante | 1m | 5m | 15m | 30m |
|---|---:|---:|---:|---:|
| pretrained_raw | 0.898309 | 0.868638 | 0.937859 | 1.053910 |
| pretrained_calibrated | 0.800020 | 0.702651 | 0.698068 | 0.703745 |
| finetuned_raw | 0.900211 | 0.826088 | 0.912345 | 1.039818 |
| finetuned_calibrated | 0.800281 | 0.710546 | 0.699786 | 0.706885 |
| Fase 4 | 0.761938 | 0.695215 | 0.697741 | 0.694621 |

## Fine-tuning

Foram executados 500 passos. A loss média dos primeiros 50 passos foi 2.490470 e dos últimos 50 foi 2.477973. A inclinação linear foi +0.000009051 por passo.

Após calibração, o modelo pré-treinado obteve log loss menor que a variante fine-tuned nos quatro horizontes. O fine-tuning configurado não demonstrou vantagem incremental.

## Economia e decisão

Configurações com limite inferior positivo e pelo menos 200 trades: **3**. As três são a mesma política efetiva da variante `finetuned_raw` em 15m, payout 90%, com limiares 0,55/0,58/0,60 que selecionaram os mesmos 215 trades: expectativa +0,131163 unidade/trade, IC95% diário [+0,001332, +0,253364]. Trata-se de payout fixo hipotético; não é resultado Spot.

Todos os cenários Spot foram negativos após custos. O melhor valor observado ainda foi -0,000695 por trade com 5 bps por lado, e seu IC95% permaneceu abaixo de zero.

Nenhuma variante Kronos apresentou ganho de log loss com IC diário inteiramente abaixo de zero contra XGBoost/CatBoost. A política permanece em abstenção integral; não há promoção automática nem evidência para declarar lucratividade.

A amostra de abril–junho/2026 já foi usada na Fase 4, portanto esta comparação é exploratória e não é um novo teste final independente.
