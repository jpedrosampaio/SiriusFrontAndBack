# PostgreSQL — implementação em andamento

Branch `feat/postgres-neon`, base `e2b1bfd60c225d22329b9a28ac0daf3b4e8ee702`.
Este documento não declara o cutover concluído: o servidor existente ainda usa Mongo enquanto os domínios são substituídos e testados na branch.

## Fundação

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

Concluir modelos e repositories de todos os domínios do mapa; conectar rotas/serviços ao SQL; substituir GridFS e workers; RAG vetorial opcional; cleanup explícito; migrar testes de integração existentes; validar auth e smoke de todos os módulos; remover Motor/PyMongo somente quando não houver consumidores. Não publicar esta fundação isolada como se fosse a substituição completa.
