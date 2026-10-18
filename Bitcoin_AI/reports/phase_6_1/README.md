# Fase 6.1

Status: engenharia concluída para observação local; validação econômica pendente.

Entregáveis:

1. 00_auditoria_arquitetura.md
2. 01_licencas_modelos_nlp.md
3. 02_classificador_neural.md
4. 03_comparacao_classificadores.md
5. 04_fontes_noticias.md
6. 05_periodicidade_latencia.md
7. 06_reacao_mercado.md
8. 07_politicas_abcd.md
9. 08_paper_trading.md
10. 09_conta_demo.md
11. 10_gerenciamento_risco.md
12. 11_benchmarks.md
13. 12_metricas_prospectivas.md
14. 13_testes_automatizados.md
15. 14_limitacoes_recomendacoes.md

Artefatos verificáveis: model_inventory.json, qwen3_smoke.json,
service_smoke.json, preservation.json, engineering_status.json e validation.json.

Comandos:

- Preparar relatórios: PYTHONPATH=src python scripts/run_phase6_1.py prepare
- Baixar revisão fixada: PYTHONPATH=src python scripts/run_phase6_1.py download-qwen3
- Testar Qwen3: PYTHONPATH=src python scripts/run_phase6_1.py nlp-smoke
- Observar serviços: PYTHONPATH=src python scripts/run_phase6_1.py serve
- Encerrar: Ctrl+C; o supervisor solicita parada graciosa aos serviços.

O comando serve não carrega o Qwen3 no caminho crítico. A inferência neural deve ser
usada pela fila assíncrona para não bloquear mercado ou notícias.
