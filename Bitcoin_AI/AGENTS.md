# Instruções persistentes

- Projeto de pesquisa BTCUSDT, sem execução financeira real, credenciais ou integração autenticada.
- Não alterar/mover ZIPs em data/raw ou PDFs em data/knowledge/books. Gerar derivados separados.
- Não publicar livros, datasets, credenciais ou modelos. Manter exclusões do .gitignore.
- Features só podem usar candles encerrados e disponíveis; targets/preços futuros ficam separados. Reiniciar indicadores após lacunas.
- Não embaralhar treino/teste. Ajustar seleção, scaler e modelos só no treino; calibrar em bloco separado. Purga deve respeitar o fim dos rótulos.
- Julho–setembro/2026 já foi observado como teste final. Não remover reports/test_registry.json para reutilizá-lo como teste independente de novas escolhas. Reservar dados futuros para mudanças posteriores.
- Não promover modelos automaticamente. Resultados negativos, abstenção e limitações devem permanecer explícitos.
- Antes de alterar fórmulas/dados, revisar catálogo e testes causais. Documentar qualquer mudança que torne resultados históricos desatualizados.
- Executar `python -m pytest -q` para mudanças de lógica. PYTHONPATH=src para CLI sem instalação.
