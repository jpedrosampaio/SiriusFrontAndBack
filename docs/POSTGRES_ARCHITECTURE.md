# PostgreSQL — implementação em andamento

Branch `feat/postgres-neon`, base `e2b1bfd60c225d22329b9a28ac0daf3b4e8ee702`.
Este documento não declara o cutover concluído: o servidor existente ainda usa Mongo enquanto os domínios são substituídos e testados na branch.

## Fundação

Catálogo de estudos conectado: áreas, programas, cadernos e notas. Sessões e
tentativas são agregadas por caderno/programa para os totais; não existem novos
contadores cumulativos duplicados. Archive oculta áreas/programas/cadernos e
preserva as evidências. Upload de notas autentica/verifica dono e retorna 503
enquanto storage durável não estiver disponível. Metas também usam transações SQL.

Também conectadas: rotas financeiras de transações/categorias/orçamentos,
cartões/faturas/parcelas, projeções, contas mensais, estatísticas/tendência,
insights e exportações. Cálculos e persistência usam Decimal/NUMERIC; JSON de
entrada é decodificado com Decimal. A conversão para números JSON ocorre apenas
na serialização HTTP/recibo, preservando o contrato numérico do frontend.
Agregados por mês/categoria são SQL, sem limites silenciosos de 500/1000 registros.
Dashboard, relatórios gerais e Agent ainda possuem leitores financeiros Mongo.

Rotas reais já conectadas: autenticação/perfil/credenciais; tarefas e hábitos (incluindo XP transacional, replay e Kanban); calendário com consultas por período. Templates excluídos são arquivados para preservar evidências. Demais consumidores de tarefas/hábitos, como Dashboard e Agent, ainda aguardam migração. O startup ainda depende de Mongo. Testes SQL agora incluem `server.app`, sem servidor Mongo disponível, mas ainda sem executar o lifespan legado.

- SQLAlchemy 2.0.54, typed mappings e AsyncSession.
- Psycopg 3.3.6: driver async em runtime e sync no CLI Alembic. Ambos usam o mesmo dialeto `postgresql+psycopg`. Asyncpg também é suportado pelo SQLAlchemy; psycopg simplifica TLS e o CLI síncrono. [Dialeto oficial](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg).
- Alembic 1.20.0 é a autoridade do schema. Nenhum `create_all`, DDL ou migration no startup.
- Engine lazy único por processo; pool 2 + overflow 1, timeout 15 segundos, reciclagem 240 segundos. `prepare_threshold=None` evita dependência de prepared statements do pooler. [Psycopg/PgBouncer](https://www.psycopg.org/psycopg3/docs/advanced/prepare.html).
- Serviços abrem `unit_of_work`; repositories recebem AsyncSession e fazem flush, nunca commit. Exceções desfazem todas as escritas. Uma sessão nunca é compartilhada entre tarefas concorrentes.
- `run_activity` bloqueia a linha do usuário com `FOR UPDATE`; dados, XP e recibo de idempotência pertencem à mesma transação. Sem retry automático de chamadas externas/IA dentro da transação.
- UUID nativo, instantes `timestamptz`, dias civis `date`, dinheiro `NUMERIC(18,2)`. Entrada monetária rejeita float na fronteira do repository.
- FKs compostas `(user_id, entity_id)` impedem cruzar proprietários também no banco. Histórico usa RESTRICT; projeções descartáveis usam CASCADE. Exclusão de conta ainda precisa de serviço explícito de limpeza do histórico.
- JSONB restrito a preferências, metadados, argumentos/resultados variáveis, evidências e análise estruturada. Mensagens, tentativas e revisões são linhas individuais.
- Senhas permanecem bcrypt; tokens de sessão serão armazenados somente como hash SHA-256. URLs e parâmetros SQL não são registrados.

## Execução local

`docker compose -f compose.postgres.yml up -d` inicia apenas PostgreSQL local. Em `backend`, definir DATABASE_URL para a conexão local e executar `python -m alembic upgrade head` e `python -m alembic check`. CI usa banco descartável próprio, nunca Neon.

No Windows, psycopg async precisa de SelectorEventLoop; testes configuram a política antes de criar o loop. A configuração do entrypoint de produção Windows deve preservar isso. Render/Linux não precisa desse ajuste.

## Trabalho ainda necessário

Concluir modelos e repositories de todos os domínios do mapa; conectar rotas/serviços ao SQL; concluir os demais workers; RAG vetorial opcional; cleanup explícito; migrar testes de integração existentes; validar auth e smoke de todos os módulos; remover Motor/PyMongo somente quando não houver consumidores. Não publicar esta fundação isolada como se fosse a substituição completa.

## Editais: análises e fila conectadas

Salvar, abrir, listar, comparar, revisar cargos/páginas, cache e exclusão usam PostgreSQL. Revisões são protegidas por versão e lock. Fila usa `edital_jobs`, claim com SKIP LOCKED e lease; não repete IA após interrupção. Sem object storage, upload em segundo plano retorna 503 e o worker não inicia. O adaptador local exige opt-in e recusa Render/produção. Worker configurado acorda no envio e consulta em intervalos de 60 s quando ocioso, não a cada 3 s. GridFS saiu do runtime. Importação de programas/cronogramas agora é SQL; RAG e eventos do Agent ainda têm persistência Mongo.

Importação direta de PDF e por cargo salvo utilizam o mesmo writer SQL: programa, preparação, cadernos, tópicos, horários, XP e recibo são atômicos. Área é validada antes da IA e novamente na gravação. Cronograma/verticalização/indicadores, ajustes de disciplinas e blocos semanais usam SQL; indicadores não duplicam minutos cumulativos. Simulados/quizzes/flashcards e demais leitores ainda precisam de integração.

Simulados agora usam Exam/Question/ExamQuestion/ExamAttempt nas rotas de geração, PDF, listagem, detalhe, correção, resultados e exclusão lógica. Estatísticas são agregados SQL; exclusão preserva fatos de estudo e oculta a prova/histórico da biblioteca. Correção grava respostas inclusive brancos, mas brancos não entram como tentativas individuais de domínio/revisão. IA mantém os prompts existentes e executa fora da transação.

Flashcards/revisões SM-2 e quizzes (manuais e IA) usam SQL, incluindo XP/recibo na mesma transação. Quizzes reaproveitam Exam/Question/ExamAttempt com kind quiz. Cartões excluídos são arquivados para preservar revisões, e biblioteca/fila/indicadores filtram o archive. Tags de cartões são ARRAY.

Tarefas de estudo, estatísticas gerais, gráficos de foco/questões e sugestões usam SQL. Conclusões têm unicidade por dono/tarefa/data, com XP e recibo atômicos. Alterar recorrência com histórico retorna conflito para preservar as evidências.

Mapas mentais e redações persistem em SQL; IA fora da transação, resultado/XP/recibo atômicos. Listagens por dono têm limite 50. Arquivos dessas gerações são temporários, sempre removidos em finally, sem promessa de retenção do binário.

PDF para materiais valida caderno antes da IA e novamente no writer. Notas/cartões/quiz/XP/recibo são atômicos, com quantidades de geração validadas. Caderno obrigatório evita materiais órfãos; a interface já envia o caderno selecionado. IA continua fora da transação; replay evita duplicar dados/XP, mas uma repetição ainda pode chamar a IA antes de consultar o recibo.
