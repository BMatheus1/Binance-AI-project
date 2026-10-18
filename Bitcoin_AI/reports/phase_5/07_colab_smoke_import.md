# 07 — Smoke produzido no Colab e importado localmente

O pacote `bitcoin_ai_phase5_results.zip`, SHA-256 `1d01a543ec3ca3a53ca1710014ffe513c446a76d5930f402e4d35f1bed296518`, foi validado e importado em `20261018T150416841626Z-phase5-import`.

O manifesto confirma o build `2026-10-18.3`, Python 3.13.15, PyTorch 2.11.0+cu130, CUDA 13.0 e Tesla T4. A inferência pré-treinada gerou oito previsões: duas decisões para cada horizonte de 1, 5, 15 e 30 minutos. O smoke de treinamento executou um passo e registrou loss finita `2,627445697784424`.

O importador confirmou revisões, hash das previsões, probabilidades, decisões, alvos, preços, retornos e instantes UTC. A diferença entre unidades físicas de timestamp dos Parquets do Colab (ns) e locais (us) foi normalizada sem relaxar a igualdade dos instantes.

As métricas sobre duas observações por horizonte não medem capacidade preditiva ou econômica e não devem ser interpretadas. O pacote está em modo `smoke`; não contém a comparação completa de 256 decisões, fine-tuning de 500 passos ou as quatro variantes exigidas. `automatic_promotion=false`, `real_orders=false` e a política permanece em abstenção integral.
