# Operational Corrections — Fase A

Base auditada: `main` em `c10b907c9ebdf79aaecc49aee3d2a1ae358b22b5` (PR #23), worktree limpo antes das alterações. Arquitetura preservada: React/Vercel → FastAPI/Northflank → PostgreSQL/Neon.

## Diagnóstico e contratos

- Chat: a resposta do POST usava `conversations` capturado pelo closure; uma hidratação ainda pendente também podia substituir o cache atualizado. A composição agora lê o QueryClient e une os resultados tardios por ID/receipt. A conversa atual fica no topo, títulos conhecidos são mantidos, máximo 30 conversas/200 mensagens. Nenhum GET extra depois do POST.
- Marcações de ficha: o guard por plano descartava toques durante a escrita; checkbox e contêiner também acionavam o mesmo toggle. Agora existe fila serial por plano, projeção de todas as intenções e uma chave por operação. Uma rejeição definitiva desfaz somente aquela intenção; timeout/rede/5xx pausa a fila e oferece reenvio com a mesma chave, pois a primeira tentativa pode ter sido persistida. Reset/finalização aguardam a fila. Não há sistema offline completo.
- Briefing: progresso é a proporção de tarefas/hábitos concluídos sobre tarefas/hábitos planejados, arredondada de 0 a 100. O score do modelo é ignorado. Texto mantém o cache de quatro horas; as contagens de planejamento são relidas para o percentual não congelar. Sem itens, a UI mostra “— / Sem itens planejados”; pendências reais mostram “0% / do dia”.
- Task: `scheduled_time` é TIME sem timezone, nullable, contrato HTTP `HH:MM` (00:00–23:59); `duration_minutes` é integer nullable 5–720, com constraint PostgreSQL. Campos ausentes continuam opcionais para clientes anteriores. `PUT /api/tasks/{id}` edita o template com ownership/idempotência. `template_date` evita trocar a âncora de recorrência pela data de uma ocorrência. A edição preserva instâncias e recompensas XP existentes.
- Agent: schema e instruções separam horário/duração explicitamente informados do título. A interpretação é feita pelo modelo, sem regex de título no planner. Os testes usam respostas estruturadas simuladas; não houve chamada a Gemini/Groq para avaliar compreensão linguística real. Propostas continuam exigindo confirmação; fallback sem modelo não inventa horários.

## Planner

Prévia sem writes, baseada no horário atual no fuso IANA do usuário. Para hoje, o início flexível é `max(08:00, agora arredondado para cima em 5 minutos)`; fim padrão 18:00. Após 18:00 não há novo encaixe flexível. Datas passadas não recebem novos encaixes; datas futuras usam a janela completa.

Compromissos e tarefas com horário são preservados, inclusive antes de 08:00/depois de 18:00. Tarefas fixas pendentes cujo início passou são `past_due`; nunca são deslocadas e não são oferecidas como próximo passo. Sobreposições entre os três pares possíveis de itens fixos são mostradas. Disponibilidade desconta a união dos intervalos fixos e o tempo passado. Duração ausente é estimada em 30 min, sinalizada por `duration_estimated`; a estimativa não é persistida. A janela não é uma preferência pessoal de expediente. Recorrência continua Task + TaskInstance, sem materializar centenas de ocorrências.

## Migration e ordem de publicação

- Revision: `84d2a71ef309`.
- Down revision: `126b856daebb`.
- Adição: `tasks.scheduled_time`, `tasks.duration_minutes` e constraint de duração. Sem backfill, mudanças de hospedagem, DDL de startup ou `create_all`.
- **Não mergear antes da confirmação da migration no Neon.**

1. Usar o código da branch `fix/operational-planning-races` e entrar em `backend`.
2. Disponibilizar `DATABASE_URL_DIRECT` com a conexão direta do Neon no ambiente privado do processo de migration. Não compartilhar a URL/chave no chat ou versionar `.env`.
3. Executar `python -m alembic current` e confirmar `126b856daebb`.
4. Executar exatamente:

   ```sh
   python -m alembic upgrade head
   ```

5. Executar `python -m alembic current` e confirmar `84d2a71ef309`; `python -m alembic check` deve indicar ausência de operações novas.
6. Confirmar a aplicação; só então mergear a PR. Northflank/Vercel publicam o runtime/frontend novos.
7. Conferir `/health/live`, `/health/ready` e smoke de tarefas/planejamento. Testes automáticos em produção são somente leitura.
8. Iniciar `feat/workout-session-ux2` somente após merge e produção saudável. A Fase B permanece pendente por essa dependência explícita.

A migration é compatível com o runtime anterior (campos nullable). Em rollback de aplicação, manter as colunas; não executar downgrade destrutivo em produção.

## Validação

Testes locais: 183 PostgreSQL; banco vazio + primeiro usuário; upgrade desde a revisão anterior; Alembic check; 105 regressões backend, cinco testes de rotas de segurança; 45 unit frontend; lint e build. A primeira execução concorrente com o build teve uma falha do subprocesso Alembic no Windows sem stderr; a repetição isolada e a suíte completa seguinte passaram.

Browser smoke adicional controla GET/POST para hidratação tardia, cliques rápidos e falha intermediária; criação/edição/limpeza de horário/duração, briefing parcial/vazio/zero real, planner após meio-dia, horários fixos vencidos e conflitos. Viewports 1440/1024/768/390/320. Fixtures sintéticas: não comprovam latência real de Neon, qualidade de respostas de LLM nem teclado físico de celular. Kanban usa uma coluna antes de 1280 para não comprimir os campos.
