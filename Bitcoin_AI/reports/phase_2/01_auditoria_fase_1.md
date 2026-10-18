# 01 — Auditoria da Fase 1

Estado: **aprovada_com_limitações**. Foram confirmados 1,578,240 candles, 37 features, zero lacunas, zero duplicatas e zero linhas do teste proibido carregadas pela Fase 2.

Os instantes são causais: candle `t` fecha antes da decisão, a entrada histórica é `open[t+1]`, a saída é `close[t+h]`, e a purga considera o fim do evento. Treino, calibração e validação são cronológicos. Os 40 originais permanecem inalterados.

Limitações encontradas: importância da Fase 1 com apenas duas permutações; walk-forward restrito a logística e frequência; amostragem uniforme do treino; ausência de correção de multiplicidade; e exposição descritiva de candidatos/limiares no teste já consumido. Isso não invalida os números históricos, mas impede reutilizá-los para selecionar a Fase 2.

O teste julho–setembro/2026 permanece registrado como consumido. A execução desta fase terminou antes de 01/07/2026.
