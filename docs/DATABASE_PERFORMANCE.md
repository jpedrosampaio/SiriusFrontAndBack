# Baseline de persistência

Nenhuma comparação de latência Mongo versus PostgreSQL foi medida ainda. Não usar tempos de testes como benchmark de endpoints.

Ambiente de validação local: PostgreSQL 17.11, Windows, porta loopback 55432, banco descartável, pool 2+1. A migration da fundação criou 38 tabelas e `alembic check` não encontrou divergências. Sete testes de fundação passaram em 0,864 s (2026-10-01); isso valida comportamento, não performance de produção.

Pendente: EXPLAIN de consultas mensais, histórico de tentativas, revisões e conversas com dataset de teste representativo. SQL financeiro já usa intervalo `[início, próximo mês)` sobre coluna date; sem formatar a coluna no WHERE. Não há campanha Performance 2.0 nesta branch.

Estatísticas de estudo agregam sessões e questões no SQL, limitando gráficos diários aos últimos sete dias civis do usuário. Listagem de tarefas carrega as últimas conclusões em lote com DISTINCT ON, sem consulta por tarefa.

Nutrição agrega refeições por dia com subquery por refeição e agrupa água em SQL; o gráfico semanal não faz duas consultas por dia. Totais não dependem dos limites das listagens. Planos e receitas carregam filhos em lote com selectinload, sem consulta por alimento. Nenhuma comparação de latência foi inferida desses ajustes.
