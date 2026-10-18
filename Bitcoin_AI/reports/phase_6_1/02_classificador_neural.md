# Implementação do classificador neural

O Qwen3-0.6B é carregado uma vez, apenas de arquivos locais, com remote code
desabilitado. A escolha de dispositivo usa CUDA quando disponível e CPU caso
contrário. O snapshot é verificado por revisão e hash, e o limite de memória é
aplicado antes e depois do carregamento.

A resposta inclui sentimento textual, evento principal, ativos, impactos por ativo,
confiabilidade, novidade, intensidade, contradições e informação sobre possível
precificação. Pydantic rejeita campos extras, ativos fora de BTC, ETH e SOL, tipos
inválidos e impactos sem ativo correspondente. Campos de segurança omitidos recebem
padrões conservadores. Conteúdo externo é delimitado como dado não confiável.

O smoke real em CPU carregou 2.384.199.680 bytes de parâmetros e produziu JSON válido
em 70.127,8 ms. A saída marcou informação insuficiente e não criou uma decisão.
Consulte qwen3_smoke.json e model_inventory.json.

