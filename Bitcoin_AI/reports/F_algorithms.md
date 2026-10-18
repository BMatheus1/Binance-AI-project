# F — Comparação de algoritmos

Teste final avaliado uma vez; escolha do modelo baseada exclusivamente na validação. Accuracy inclui empates; macro-F1 atribui peso igual às três classes. Matrizes, precisão, recall, AUC e calibração estão no JSON final.

| Horizonte | Modelo | Log loss val | Log loss teste | Accuracy teste | Brier multiclasse | F1 macro |
|---|---|---|---|---|---|---|
| 1 | frequency | 0.797131 | 0.861573 | 47.4700% | 0.546458 | 0.214597 |
| 1 | constant | 2.366977 | 2.428687 | 47.4700% | 1.019683 | 0.214597 |
| 1 | momentum | 0.802473 | 0.863255 | 49.1066% | 0.548132 | 0.335598 |
| 1 | reversion | 0.802011 | 0.869673 | 46.0145% | 0.554336 | 0.314388 |
| 1 | logistic_price | 0.796937 | 0.865095 | 47.5734% | 0.546744 | 0.214914 |
| 1 | logistic_price_action | 0.780278 | 0.818783 | 49.8660% | 0.538303 | 0.381844 |
| 1 | logistic_price_trend | 0.796198 | 0.860764 | 47.8904% | 0.546214 | 0.319835 |
| 1 | logistic_price_volatility | 0.776448 | 0.814915 | 47.5621% | 0.538675 | 0.317784 |
| 1 | logistic_price_volume | 0.795381 | 0.862184 | 48.0648% | 0.546092 | 0.308566 |
| 1 | logistic_price_trend_volume | 0.794895 | 0.858097 | 48.8152% | 0.545231 | 0.331820 |
| 1 | logistic_all_selected | 0.776370 | 0.813351 | 49.6879% | 0.537184 | 0.383149 |
| 1 | random_forest | 0.775591 | 0.810486 | 50.7545% | 0.534875 | 0.406754 |
| 1 | xgboost | 0.774909 | 0.809687 | 50.6549% | 0.534845 | 0.382313 |
| 1 | catboost | 0.776061 | 0.810953 | 50.5832% | 0.535294 | 0.345758 |
| 5 | frequency | 0.703990 | 0.729788 | 49.2643% | 0.506480 | 0.220032 |
| 5 | constant | 2.325511 | 2.346416 | 49.2643% | 0.984872 | 0.220032 |
| 5 | momentum | 0.711199 | 0.735101 | 49.4546% | 0.511762 | 0.330606 |
| 5 | reversion | 0.707058 | 0.734445 | 49.7731% | 0.511109 | 0.332789 |
| 5 | logistic_price | 0.704133 | 0.729306 | 50.0857% | 0.506440 | 0.222476 |
| 5 | logistic_price_action | 0.703916 | 0.721077 | 51.0573% | 0.505580 | 0.341388 |
| 5 | logistic_price_trend | 0.702983 | 0.727868 | 51.1320% | 0.505815 | 0.341785 |
| 5 | logistic_price_volatility | 0.703416 | 0.719932 | 51.1433% | 0.505558 | 0.342058 |
| 5 | logistic_price_volume | 0.703772 | 0.728737 | 50.4126% | 0.506218 | 0.333804 |
| 5 | logistic_price_trend_volume | 0.703068 | 0.727330 | 51.3690% | 0.505646 | 0.343169 |
| 5 | logistic_all_selected | 0.703282 | 0.719559 | 51.1078% | 0.505394 | 0.341545 |
| 5 | random_forest | 0.702432 | 0.717828 | 51.5359% | 0.504897 | 0.344070 |
| 5 | xgboost | 0.702061 | 0.717344 | 51.6876% | 0.504735 | 0.344814 |
| 5 | catboost | 0.702267 | 0.718013 | 51.8409% | 0.504732 | 0.345757 |
