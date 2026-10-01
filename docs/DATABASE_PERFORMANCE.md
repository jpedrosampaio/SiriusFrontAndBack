# Baseline de persistência

Nenhuma comparação de latência Mongo versus PostgreSQL foi medida ainda. Não usar tempos de testes como benchmark de endpoints.

Ambiente de validação local: PostgreSQL 17.11, Windows, porta loopback 55432, banco descartável, pool 2+1. A migration da fundação criou 38 tabelas e `alembic check` não encontrou divergências. Sete testes de fundação passaram em 0,864 s (2026-10-01); isso valida comportamento, não performance de produção.

Pendente: EXPLAIN de consultas mensais, histórico de tentativas, revisões e conversas com dataset de teste representativo. SQL financeiro já usa intervalo `[início, próximo mês)` sobre coluna date; sem formatar a coluna no WHERE. Não há campanha Performance 2.0 nesta branch.

Estat?sticas de estudo agregam sess?es e quest?es no SQL, limitando gr?ficos di?rios aos ?ltimos sete dias civis do usu?rio. Listagem de tarefas carrega as ?ltimas conclus?es em lote com DISTINCT ON, sem consulta por tarefa.
