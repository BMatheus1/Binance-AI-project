# Fase 5 — Kronos no Google Colab

A preparação e o experimento completo foram concluídos sem alterar os resultados das Fases 1–4. O pacote integral do Colab foi importado com 4.096 previsões. O melhor Kronos foi o pré-treinado calibrado, mas não reduziu a log loss contra XGBoost/CatBoost em nenhum horizonte. O fine-tuning controlado também não apresentou vantagem incremental.

O risco central é a sobreposição de pré-treinamento: o Kronos declara dados Binance até junho/2024. Por isso o treino local começa em julho/2024 e a avaliação usa abril–junho/2026. A política permanece em **abstenção integral**.

Arquivos principais:

- `notebooks/phase5_kronos_colab_v2.ipynb` (build corrigido `2026-10-18.3`)
- `data/phase_5/bitcoin_ai_phase5_colab.zip`
- `reports/phase_5/export_manifest.json`
- `scripts/export_phase5_colab.py`
- `scripts/import_phase5_results.py`
- `06_instrucoes_colab.md`
- `preservation.json`
- `validation.json`
- `07_colab_smoke_import.md`
- `08_full_results.md`
- `full_analysis.json`
- `full_artifact_inventory.json`
