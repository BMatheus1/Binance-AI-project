# Periodicidade e latência

O supervisor foi executado entre 19:24:42 e 19:26:58 UTC. Dois ciclos de notícias
foram concluídos, com cadência configurada de 120 segundos. O último terminou às
19:26:42 UTC. O arquivo service_smoke.json registra a execução.

O coletor de notícias, o monitor de mercado e o heartbeat são tarefas independentes.
A inferência neural usa uma fila limitada, timeout e thread separada, portanto uma
notícia lenta não pausa o mercado ou o próximo ciclo de feeds. Fila cheia, timeout,
erro do modelo ou JSON inválido produzem resultado insuficiente e abstenção.

Na CPU disponível, a inferência Qwen3 válida levou 70,1 segundos. GPU não estava
disponível. Essa latência é aceitável apenas para pesquisa assíncrona e precisa ser
medida novamente no hardware de implantação.

