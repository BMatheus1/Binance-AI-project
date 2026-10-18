# Fase 5 — Kronos no Google Colab

A preparação foi concluída sem alterar os resultados das Fases 1–4. O pacote de dados causal, o notebook GPU, o adaptador probabilístico e o importador local estão prontos. O smoke real de inferência e de um passo de treinamento passou; ainda não existem resultados do experimento completo no Colab.

O risco central é a sobreposição de pré-treinamento: o Kronos declara dados Binance até junho/2024. Por isso o treino local começa em julho/2024 e a avaliação usa abril–junho/2026. A política permanece em **abstenção integral**.

Arquivos principais:

- `notebooks/phase5_kronos_colab.ipynb`
- `data/phase_5/bitcoin_ai_phase5_colab.zip`
- `reports/phase_5/export_manifest.json`
- `scripts/export_phase5_colab.py`
- `scripts/import_phase5_results.py`
- `06_instrucoes_colab.md`
- `preservation.json`
- `validation.json`
