# Máquina de estados das posições

Estados persistidos: `ENTRY_SUBMITTING`, `OPEN`, `EXIT_SUBMITTING`, `CLOSED` e `RECOVERY_REQUIRED`. O diário de ordens mantém `PREPARED`, `SUBMITTING`, `UNKNOWN`, estados da corretora e `RECONCILED`. Estado desconhecido bloqueia novas entradas.
