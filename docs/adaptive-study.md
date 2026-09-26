# Estudo por resultado

Na página Estudar, registre resolvidas e acertos do assunto selecionado. A operação exige chave de idempotência, verifica propriedade e índices do conteúdo e grava histórico, contadores e próxima revisão na mesma transação MongoDB. Repetir a requisição após perda de resposta não duplica questões. Estes registros não concedem XP; não registre novamente uma resolução já contabilizada em quiz ou lançamento manual.

A fila guarda o último resultado por assunto e a próxima data sugerida: 1 dia abaixo de 60%, 7 dias entre 60% e 85%, 21 dias a partir de 85%. Cada lançamento fica no histórico de questões. A revisão seguinte se registra pelo mesmo formulário. Não há classificação automática de erros de simulados antigos, que não têm vínculo estável com assunto.

Na agenda, a opção adaptativa é explícita e desativada por padrão. Usa o peso atual multiplicado por `1 + taxa de erros` quando há pelo menos cinco questões históricas da disciplina, acrescentando 0,25 ao multiplicador se houver blocos pendentes anteriores ao início escolhido. O bloco mostra a justificativa. Os pesos oficiais não são alterados. Dias e capacidade são preservados e blocos concluídos não são apagados.

Risco: todos os registros da disciplina participam da taxa; isso não representa previsão de aprovação. A fila é uma sugestão determinística e não uma obrigação. O planner não marca revisões como concluídas automaticamente.

Validação: limites e virada de ano; amostra mínima; alocação diferenciada, capacidade e preservação do histórico; integração Mongo com replay, contadores, propriedade e valores inválidos.
