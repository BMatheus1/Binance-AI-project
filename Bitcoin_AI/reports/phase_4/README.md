# Fase 4 — resultado executivo

Execução histórica congelada: `20261018T013856021255Z-phase4`. Os horizontes 1, 5, 15 e 30 minutos foram comparados sem acessar julho–setembro/2026. Todos os candidatos de um horizonte receberam exatamente as mesmas observações.

| Horizonte | Modelo shadow | Accuracy | Log loss | Δ log loss vs. frequência | IC95% diário do Δ |
|---:|---|---:|---:|---:|---:|
| 1m | XGBoost | 50,6180% | 0,774881 | -0,022185 | [-0,027525; -0,018041] |
| 5m | XGBoost | 51,7793% | 0,702095 | -0,001886 | [-0,002404; -0,001355] |
| 15m | XGBoost | 52,4751% | 0,694784 | -0,001852 | [-0,002645; -0,001003] |
| 30m | CatBoost | 52,3299% | 0,694014 | -0,001705 | [-0,003058; -0,000462] |

Os ganhos probabilísticos são pequenos e não autorizam operação. Todos os cenários Spot ficaram sem limite inferior positivo após custos. Cenários positivos de payout fixo em 5/15/30m são exploratórios, dependem de contrato hipotético e foram encontrados no mesmo bloco usado para comparar modelos.

O ensaio operacional final recebeu 6.244 mensagens públicas em 130 segundos: zero reconexões, gaps de AggTrade, invalidações do livro e abstenções técnicas novas. Foram registradas oito novas previsões válidas, todas abstidas pela política congelada; nenhuma ordem foi enviada. O ledger acumulado tem 28 previsões e quatro resultados, amostra muito inferior aos mínimos de 200 resultados, 30 dias e regimes diversos.

A política oficial continua em **abstenção integral**. O próximo passo permitido é acumular observação prospectiva independente em shadow/paper, sem retreinar esta geração com o período reservado.
