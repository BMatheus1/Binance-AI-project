# 06 — Execução exata no Google Colab

1. Encerre sessões antigas que tenham executado outra versão, acesse [Google Colab](https://colab.research.google.com/) e envie `notebooks/phase5_kronos_colab_v2.ipynb`. Confirme no topo `Build Colab: 2026-10-18.3`.
2. Em **Runtime → Change runtime type**, selecione **GPU**. A célula 3 interrompe a execução se CUDA não estiver disponível.
3. Execute as células 1–8 em ordem. Quando solicitado na célula 2, envie `data/phase_5/bitcoin_ai_phase5_colab.zip`.
4. Confirme `PRETRAIN_SMOKE_OK = True` após a inferência pré-treinada e `TRAIN_SMOKE_OK = True` após o passo de treinamento. Esses resultados apenas validam o ambiente.
5. Para executar a comparação congelada, altere `FULL_EXPERIMENT = False` para `FULL_EXPERIMENT = True` na célula 9 e execute as células 9–10. Não altere datas, revisões, amostras, quantidade de caminhos ou hiperparâmetros.
6. A célula 10 baixa `bitcoin_ai_phase5_results.zip`. Guarde também o log do runtime se houver falha.

O experimento completo executa, nesta ordem: inferência pré-treinada em calibração e validação; calibração probabilística ajustada apenas em janeiro–março/2026; recarga dos pesos originais; fine-tuning somente do predictor em julho/2024–dezembro/2025; inferência e calibração da variante ajustada; exportação de previsões, calibradores, checkpoints, perdas, ambiente e hashes.

No Windows, extraia o ZIP retornado e importe a pasta:

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
$env:PYTHONPATH = 'src'
python scripts/import_phase5_results.py "C:\caminho\phase5_results"
```

O caminho informado deve conter diretamente `run_manifest.json` e `kronos_predictions.parquet`. O importador rejeita revisão diferente, hash divergente, observação duplicada, conjunto incompleto, uso do período proibido ou qualquer diferença em decisão, fim do evento, alvo, retorno, entrada e saída. O resultado aceito fica em `reports/phase_5/runs/<run_id>/results.json`, e `reports/phase_5/latest_import.json` aponta para ele.

As métricas são accuracy, log loss, Brier multiclasse, calibração, distribuição probabilística e intervalo por blocos diários da diferença pareada de log loss contra o modelo congelado da Fase 4. Os cenários econômicos reutilizam payouts, custos, limiares, não sobreposição, limite diário e drawdown existentes. Todos são hipotéticos. A importação mantém `automatic_promotion=false`, `real_orders=false` e abstenção integral.

### Compatibilidade do runtime Colab

A célula 1 não executa o `requirements.txt` completo do repositório. Einops, Hugging Face Hub, Safetensors e tqdm são instalados em `/content/phase5_deps`, isolados das bibliotecas globais. Torch, NumPy, pandas, PyArrow, scikit-learn e joblib da imagem do Colab são apenas importados e registrados. Assim o notebook não altera dependências usadas por Transformers, Diffusers, Gradio ou pelo próprio runtime.
