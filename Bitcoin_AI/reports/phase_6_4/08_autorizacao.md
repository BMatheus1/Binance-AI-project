# Mecanismo de autorização

A CLI prepara uma sessão vinculada ao `boot_id` do worker em execução. A confirmação explícita cria autorização temporária de até 120 minutos. Reiniciar o worker altera o `boot_id` e invalida a autorização antiga. O kill switch volta a ser acionado no encerramento.
