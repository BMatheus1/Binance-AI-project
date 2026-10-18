# Estudo dos livros — índice e alcance

Atualizado em 17/10/2026. O estudo aprofundou conceitos, diferenças entre autores, riscos de interpretação e propostas de pesquisa para BTCUSDT. **A revisão semântica ainda não é integral.** O processamento automático de todas as páginas foi concluído e é registrado separadamente da leitura.

## Documentos de estudo

| Documento | Conteúdo |
|---|---|
| [Síntese crítica](synthesis.md) | Concordâncias, divergências e consequências para o projeto |
| [Adam Grimes](grimes.md) | Estrutura, oito modelos de operação, indicadores, gestão e avaliação |
| [Al Brooks](brooks.md) | Sequências, H1/H2, falhas, glossário e sete exercícios visuais detalhados |
| [David Aronson](aronson.md) | Regras objetivas, vieses, inferência, reamostragem e seleção múltipla |
| [Steve Nison](nison.md) | Famílias de candles, contexto, confirmações e técnicas complementares |
| [Protocolo proposto](protocol.md) | Causalidade, quatro eventos concretos, baselines, custos e critérios pendentes |
| [16 hipóteses estruturadas](hypotheses.json) | Definições, disponibilidade, comparadores, evidência contrária e fontes |

Os seis textos analíticos somam aproximadamente 9.600 palavras. São sínteses e críticas próprias; não reproduzem os livros. As referências nos dossiês indicam a página **física do PDF**, a partir de 1. Quando uma fórmula é nossa adaptação, isso está explicitado.

## Cobertura auditável

| Arquivo | Páginas processadas | Páginas com passagens analisadas | Páginas com inspeção visual registrada | Alcance |
|---|---:|---:|---:|---|
| Grimes | 480 | 143 | 0 | Passagens dos 12 capítulos e apêndice B; exemplos e trechos ainda pendentes |
| Brooks | 212 | 16 | 8 | Suplemento: glossário, sumário, varredura parcial de legendas e figuras selecionadas |
| Aronson | 300 | 73 | 0 | Passagens dos capítulos 1–6 presentes; arquivo interrompido |
| Nison | 316 | 92 | 12 | Passagens temáticas, glossário A e figuras selecionadas; revisão integral pendente |
| **Total** | **1.308** | **324** | **20** | Contagens de texto e visual podem se sobrepor |

“Passagens analisadas” não certifica que cada palavra, nota e figura da página tenha sido revisada. A coluna visual inclui inspeções da etapa inicial e da continuação. Os exemplos visuais detalhados de Brooks estão no dossiê; a oitava página é a figura 1.5 da revisão anterior.

OCR local concluído em **528 páginas**: 212 de Brooks e 316 de Nison. A extração nativa foi executada nos quatro arquivos. Em Brooks, o texto nativo de muitas páginas é apenas rodapé; em Nison, a camada nativa é vazia. Nenhum desses fatos foi confundido com leitura concluída.

O [registro de cobertura](coverage.json) informa o estado de cada página e lista as páginas sem revisão semântica/visual registrada. O [registro de preservação](preservation.json) confirma SHA-256 inalterado dos 36 ZIPs e quatro PDFs, comparados à auditoria anterior.

## Limitações dos materiais fornecidos

- **Brooks:** PDF identificado como suplemento do audiobook. O texto integral e o áudio não estão no material estudado. É possível analisar as figuras disponíveis, mas não afirmar que a exposição integral foi lida ou ouvida.
- **Aronson:** o arquivo termina no meio do capítulo 6, PDF 300/página impressa 302. O sumário anuncia capítulos 7–9 e apêndice que não estão presentes. A tradução automática também introduz ambiguidades.
- **Nison:** OCR em inglês realizado com o mecanismo local de idioma pt-BR. Edição e sequência editorial não certificadas. A paginação irregular, isoladamente, não demonstra falta de texto.
- **Grimes:** o texto permite aprofundamento adicional; permanecem exemplos e passagens ainda não revisados. Extração completa não atesta leitura completa.

## Conclusões de trabalho

Uma forma de candle é diferente de uma previsão; uma previsão é diferente de uma operação lucrativa. Contexto, disponibilidade temporal, magnitude, custos e seleção de hipóteses fazem parte da avaliação. Vários nomes dos livros podem descrever a mesma informação, portanto não são confirmações independentes.

As 16 propostas estão **não testadas**. Nenhuma altera o status das hipóteses anteriores ou a política de abstenção do experimento existente. O teste final de julho–setembro/2026 permanece consumido e não foi reutilizado nesta etapa.

## Continuidade da leitura

O registro de páginas permite continuar sem reiniciar o trabalho. A próxima revisão integral deve:

1. Completar os trechos e figuras de Grimes ainda não analisados, com atenção a relações entre mercados, gestão e exemplos de falhas.
2. Examinar os demais gráficos do suplemento Brooks, mantendo explícita a ausência da narração/texto integral.
3. Completar as passagens disponíveis de Aronson, conferir traduções/formulações e deixar as páginas ausentes como indisponíveis.
4. Completar os exemplos e padrões menos estudados de Nison, verificar critérios de gaps e confrontar OCR com as imagens.

Essa lista é trabalho ainda pendente, não uma alegação de que as páginas já foram estudadas. A profundidade desta entrega está nas análises e comparações produzidas; não em uma falsa declaração de 100% de leitura.

## Reprodução da auditoria

Na raiz `Bitcoin_AI`:

```powershell
python scripts\audit_book_study.py
python scripts\read_book_pages.py grimes 166-169
python scripts\read_book_pages.py nison 40-43 --ocr
python scripts\read_book_pages.py aronson 234-240 --layout
```

Os textos integrais extraídos e imagens intermediárias permanecem locais em `tmp/book_study`, excluído pelo `.gitignore`. O registro editorial de revisão não é atualizado automaticamente por uma mera chamada de leitura. A auditoria valida presença dos derivados e preservação dos originais, não mede compreensão.
