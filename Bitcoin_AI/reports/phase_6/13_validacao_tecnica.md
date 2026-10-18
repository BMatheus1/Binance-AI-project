# Validação técnica

Validações implementadas:

- ciclo mínimo de 120 segundos, rate limit, retry e prevenção de sobreposição;
- causalidade de publicação/recebimento/análise;
- deduplicação e revisões;
- prompt injection tratada como dado;
- filtros de ativo e expectativa líquida;
- risco, kill switch, duração e extensão;
- idempotência paper e demo;
- bloqueio de endpoints de produção;
- estados parcial/rejeitado sem presumir fill;
- ledger encadeado e detecção de alteração;
- comparação pareada com abstenções.

`validation.json` diferencia implementação, execução operacional e evidência econômica. A suíte padrão usa somente mocks/fixtures; não envia ordens.

Execução final local em 18/10/2026: **107 testes aprovados**, sendo 36 testes específicos da Fase 6. `compileall` também terminou sem erros. Os hashes registrados das Fases 1–5 foram recalculados e todos coincidiram.
