# Fase 6.4.2 — consolidação operacional

O fluxo operacional foi centralizado sem promover um ensemble nem mudar os modelos, limiares ou parâmetros da política A. A habilitação econômica de padrões e saídas adaptativas **não está concluída**: faltam evidências temporais independentes. A observação mínima de 24 horas continua; não se deve inferir sua conclusão a partir deste documento.

## Entregas e evidências

| Pedido | Entrega |
|---|---|
| Auditoria integral de fontes e dependências | `source_inventory.json`: AST de todas as fontes Python de primeira parte, imports, definições, linhas e hashes; inventário TS/TSX/CSS/JSON do produto |
| Artefatos e inventário de modelos | `model_evidence_inventory.json`, referenciando os resultados e metadados originais das Fases 3, 4, 5 e 6.1 |
| Preservação | `preservation_before.json`, `preservation_current.json`, `preservation_verification.json`; configurações, registro de testes, resultados históricos e pesos joblib |
| Fluxo e componentes consolidados | `01_arquitetura_e_limpeza.md` |
| Especialistas, fusão, padrões, economia, ablações | `02_pesquisa_e_validacao.md`, `expert_comparison.json` |
| Segurança, execução e gerenciamento | `03_execucao_e_seguranca.md` |
| Uso, inicialização, encerramento e autorização | `04_manual_pt_BR.md` |
| Demonstração real sem ordens | `runtime_evidence.json` e `runtime_validation.json` |
| Testes automatizados e ponta a ponta | `tests.xml`, `validation.json` |
| Limitações e critérios ainda não satisfeitos | `05_aceitacao_e_pendencias.md` |

As operações diagnósticas anteriores permanecem separadas. Nenhuma ordem deve ser enviada para validar esta reestruturação. O estado final esperado é OBSERVE, kill switch ativo e nenhuma sessão autorizada.

## Reprodução

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
python .\scripts\run_phase6_4_2.py audit
python .\scripts\run_phase6_4_2.py benchmarks
python .\scripts\run_phase6_4_2.py evidence
python -m pytest -q --junitxml=reports/phase_6_4_2/tests.xml
```

O benchmark usa exclusivamente os exports de desenvolvimento de abril–junho já consumidos na pesquisa anterior. Recalculá-los não cria um teste final independente. Os comandos acima não treinam nem selecionam configurações.
