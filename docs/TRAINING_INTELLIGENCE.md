# Training Intelligence 2.0

## Auditoria antes da implementação

Base: main `3e968711392364ac4858fe3981b0d29c9fcae6ca` (PR #38). `health.py` já normaliza WorkoutSession → SessionExercise → WorkoutSet e WorkoutLog → WorkoutLogExercise → WorkoutSet. A conclusão cria um único log vinculado à sessão; os logs podem ser desmarcados ou excluídos. A projeção deve partir de logs concluídos, sem contar a sessão novamente. Séries efetivamente registradas são distintas da prescrição textual; logs antigos sem séries não comprovam cargas/repetições/RPE reais.

`workout_history_routes.py` e `serialize_logs` oferecem leitura em lote e ownership. A sugestão antiga usa apenas o último log e não exige repetições ou RPE; será substituída pelo mesmo motor factual que alimenta a nova tela, preservando seu contrato. Sessões, revisões, receipts, XP, tutoriais e calendário não precisam mudar. Os planos não possuem catálogo de movimento nem calendário obrigatório de comparecimento: aderência às séries é calculável; aderência a uma frequência semanal prescrita não é.

Life State já publica planos e sessão ativa, e o Global Planner existente continua sendo o único distribuidor de horários. O Agent dispõe de ferramentas somente leitura. A inteligência de treino deve enriquecer esses contratos, sem criar prioridades concorrentes nem aplicar sugestões.

## Contratos e critérios

Estado somente leitura, com janela explícita no fuso da conta e limite de histórico divulgado. PRs são recordes **na janela analisada**, nunca recordes de toda a vida quando não há cobertura integral. Carga máxima e carga máxima para a mesma quantidade de repetições usam apenas séries concluídas com carga positiva e repetições positivas. Volume é carga registrada × repetições; carga zero registrada é válida, mas carga ausente não é zero. Volume completo fica desconhecido quando faltam séries/cargas/repetições. Grupos musculares usam rótulos registrados, sem atribuir músculos secundários.

Progressão exige duas execuções comparáveis do mesmo plano **e dia de origem da sessão**, prescrição, carga e exercício, todas as séries efetivas, faixa de repetições interpretável e RPE registrado. Dias diferentes nunca emprestam evidência entre si. Logs manuais sem dia de origem permanecem desconhecidos para progressão específica, preservando volume/recordes. A sugestão numérica é uma hipótese de +2,5%, limitada a 2,5 kg, sujeita aos incrementos disponíveis e confirmação da pessoa. RPE alto e dados incompletos não geram aumento. Alertas de variação são regras operacionais, sem diagnóstico.

Substituições são propostas a partir dos próprios planos: objetivo explicitamente igual, grupo registrado igual e, quando disponível, movimento classificado por uma pequena tabela explícita de exercícios. Sem movimento conhecido, a interface informa que a equivalência não foi confirmada. Nenhuma proposta escreve em plano/sessão.

## Validação e publicação

`GET /api/workouts/intelligence/state?days=90` aceita janelas de 7–365 dias. `POST /api/workouts/intelligence/substitutions` recebe somente plano/dia/índice de exercício, valida ownership e é somente leitura. Ambos usam snapshot repeatable-read/read-only. O endpoint existente `next-loads` conserva seu formato, mas exige a evidência conservadora do motor e prescrição atual compatível.

Leituras limitadas a 300 logs, 2.000 exercícios e 10.000 séries; listas de exercícios a 200 identidades e histórico resumido às últimas 20 execuções por identidade. A truncagem é declarada. Substituições leem metadados de até 20 planos recentes mais o plano selecionado, até 1.000 candidatos, retornando no máximo 10. Não carregam tutoriais de todos os planos. O Agent recebe 20 exercícios, seus recordes principais, 20 grupos e 12 semanas, com flags de truncagem; não carrega o histórico detalhado. Life State usa um agregado de 28 dias e enriquece justificativas dos candidatos do Global Planner existente, sem alterar prioridade/duração ou compromissos.

Autorrevisão técnica antes da PR: ownership em cada fonte, leitura sem XP/receipts, snapshot consistente, replay/retomada existentes, remoção/desmarcação e arquivo de plano, valores desconhecidos/zero, identificação sem colisões, prescrição modificada, limites de materialização, UI sob demanda e retry. O plano-mestre mantém os mesmos bytes e as 14 fases. Não há migration, serviço novo, chamada de IA nem gravação de teste em produção.

A verificação dos consumidores confirmou uma inconsistência no comparador antigo: `Number('')` produzia carga zero e séries não concluídas podiam entrar no total. O comparador agora exige séries concluídas e valores conhecidos em toda a comparação, mantendo o fallback e o fluxo da UX2. O interceptor do cliente reconhece a consulta POST de alternativas como análise somente leitura; gravações reais continuam invalidando os dados.

CI completo, PostgreSQL descartável, segurança, regressões, todas as suítes responsivas e revisão Codex final permanecem gates de publicação. Estado publicado e evidências finais serão registrados após merge e validação dos dois deploys; a implementação não equivale a publicação.
