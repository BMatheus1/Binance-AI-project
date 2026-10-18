# 05 — Integração e retorno dos resultados

`kronos_adapter.py` transforma caminhos OHLCVA em probabilidades usando a mesma convenção temporal da Fase 4. O importador exige as revisões congeladas, probabilidades válidas, decisões pertencentes à amostra exportada e datas anteriores a julho/2026. Depois calcula accuracy, log loss, Brier, calibração, distribuição das probabilidades, diferença pareada contra o modelo da Fase 4 e os mesmos cenários econômicos.

O notebook salva previsões, manifesto do ambiente, perdas de treino, calibradores e checkpoints. Kronos permanece challenger: a integração prospectiva só pode registrar uma versão explicitamente identificada e nunca substitui o modelo atual automaticamente.

`record_shadow_paths` oferece o ponto de integração opcional com o ledger imutável. Ele registra as probabilidades e a identidade do Kronos por horizonte com `threshold=1.0` e decisão `abstain_policy`; dados incompletos geram `abstain_technical`. Assim nenhuma previsão do challenger vira sinal ou ordem durante a coleta de evidência.
