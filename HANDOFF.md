# Sirius — handoff

## PostgreSQL / Neon — em implementação, NÃO concluído

Após planning `85a8018`, rotas financeiras conectadas ao SQL: transações, categorias, orçamentos, cartões/compras/parcelas/faturas, projeções/recorrências, contas mensais/pagamentos, estatísticas/tendência, insights e exportação PDF/XLSX. Schema agora 60 tabelas, Alembic head `0e61828b3519`. Burndown **669 → 646 → 627 → 584**. Finance ainda tem 22 acessos em leitores de outros módulos; não confundir rotas próprias com domínio inteiro concluído. Sete testes HTTP financeiros passaram, cobrindo centavos, replay concorrente, rollback, isolamento, dezembro/janeiro, importação de contas, empty states e exportações. Cálculos Decimal; somente boundary HTTP converte para JSON numérico. Mongo ainda inicializa no server; não fazer merge/cutover.

Continuação autoritativa: anexo `0d137e4e-c640-43c1-b035-1bda4c319f08/Texto colado.txt`, seções 1–55. Continuar PR #21 até runtime Mongo zero. Não perguntar credenciais novamente, não merge parcial.

Runtime já conectado: auth/cadastro/login/perfil/credenciais e uso Gemini (commit `7092735`); tarefas/hábitos/calendário agora usam SQL nas rotas reais. Migração Alembic `d18c704a928e`: archive de templates para preservar histórico e constraint de consistência status/completed. 56 tabelas. Burndown **669 → 646 → 627**; 78 collections, 9 acessos dinâmicos, 1 GridFS. Chamadas restantes de planning em Dashboard/Agent/outros leitores ainda precisam ser portadas. Inventário por domínio em `docs/MONGO_BURNDOWN.md`.

Validação da conexão de planning: 33 testes PostgreSQL passaram (11,677 s), incluindo banco vazio e rotas reais com Mongo inacessível; 139 regressões passaram (20 Mongo-only ignoradas localmente e ainda cobertas por jobs Mongo). Casos de planning foram portados/consolidados, com mapa em `docs/POSTGRES_TEST_PORTS.md`. `alembic check` sem divergências. Isso ainda NÃO prova startup sem Mongo: inicialização e demais domínios continuam Mongo. Próximo: finanças completas, metas e demais domínios conforme prompt. Não declarar cutover concluído.

Pedido autoritativo: anexo `6bb87c02-c033-4291-8374-c3491a44283c/Texto colado.txt`, seções 0–133 completas. Substituir Mongo por PostgreSQL/Neon; não migrar dados, não dual-write, não Performance 2.0, não continuação UX/Studies. Usuário autoriza commits/push/PR/merge quando tudo estiver seguro; sem DATABASE_URL não quebrar produção. Não apagar Atlas.

Branch `feat/postgres-neon`, base main `e2b1bfd60c225d22329b9a28ac0daf3b4e8ee702`. PR draft [#21](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/21). Primeiro commit `46e7c1b` subiu com fundação; CI PostgreSQL e backend passaram. Nenhum merge/cutover foi feito. O runtime `server.py` ainda é Mongo; os novos services/repositories ainda precisam ser conectados às rotas. Não declarar a migração pronta por os testes da fundação passarem.

Fundação atual: SQLAlchemy 2.0.54, psycopg 3.3.6, Alembic 1.20.0, 56 tabelas. Head Alembic `b64cd6f47873`. Engine lazy pool 2+1, TLS Neon, UoW de serviços, lock de usuário/recibos, FKs compostas por dono, NUMERIC. Auth service/router testado isoladamente com HTTP; tarefas/hábitos, core writes Agent, treino e RAG lexical têm repositories/serviços/testes SQL. 18 testes PostgreSQL passaram localmente (última rodada 6,034 s), incluindo proposta de R$48 concorrente e rollback após despesa; treino de 4 semanas/20 dias; isolamento RAG e revogação. pgvector **não ativo**, pacote apenas instalado.

Inventário: 80 collections, 669 chamadas diretas, 9 acessos dinâmicos, GridFS edital_inputs. `docs/DATABASE_REDESIGN_MAP.md` e JSON adjacente são mapa estático com origens; não migração de registros. Documentação de arquitetura/Neon/modelo/performance aponta explicitamente pendências.

Local Windows sem Docker/psql instalado: baixados binários oficiais EDB PostgreSQL 17.11 para `Sirius/tmp/postgres` (fora do Git). Cluster descartável em `tmp/postgres/data`, host apenas 127.0.0.1, porta 55432, usuário sirius_test, banco sirius_test, auth trust exclusivamente local. Executável iniciado sem janela. Caminho curto 8.3 necessário para initdb devido ao nome Windows com acento. Testes: definir DATABASE_URL para esse banco local e RUN_POSTGRES_TESTS=true; `python -m alembic upgrade head`, `python -m alembic check`, `python -m unittest discover -s tests -p 'test_postgres_*.py' -q` em backend. Não usar Neon nos testes. Psycopg Windows usa SelectorEventLoop nos testes.

Pendência externa perguntada uma vez: usuário já configurou DATABASE_URL pooled e DATABASE_URL_DIRECT no Render? Sem resposta até este registro. Nunca pedir que cole secrets no chat. Ausência de Neon não bloqueia continuar código/CI.

Restante substancial: modelos/repositories/serviços de todos os domínios restantes (finance completo, planos/questões/simulados/edital, saúde completa, relatórios, notificações/Telegram/automations/contest já existentes), ligar auth e demais rotas, substituir GridFS pela abstração de storage com comportamento válido sem storage configurado, worker sem polling frequente no Neon Free, vetorial opcional se apropriado, cleanup, health/readiness, seed, E2E banco vazio/primeiro acesso, adaptar todos testes existentes e CI de Mongo, remover runtime/deps Mongo, smoke completo/frontend/lint/build, CI e só depois merge seguro. Não implementar um emulador de Mongo sobre uma coluna JSONB para acelerar o corte.

## UX 2.0 / Studies 2.0 — publicada

Branch `feat/sirius-ux-studies-2`, baseada em `883d790`. AppShell único, Sirius contextual com anexos, quatro áreas de estudos, preparações genéricas, foco retomável, domínio por evidências, banco de erros, revisões, plano adaptativo, simulados transacionais e acompanhamento de fontes públicas. Arquitetura, limites e operação em [docs/UX_STUDIES_2.md](docs/UX_STUDIES_2.md).

PR [#20](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/20) incorporado à main: `c9aa889980f78281f73f87b645e99a738ee1786f`. Revisão de código validada: `37086a3821016a7a8ea27447c8964a4d6850b7ad`. CI final do PR passou integralmente: [backend/Mongo](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/36285727080) e [frontend/browser](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/36285727047).

Validação: lint sem avisos, build de produção, 39 testes frontend, 18 de segurança e 162 regressões backend (37 dependentes de Mongo ignoradas na execução isolada; cobertas pelos jobs dedicados). Replica set: atividades/rollback, 13 testes do Agent e cinco de estudos/simulados, incluindo replay concorrente e isolamento. Smoke em 1440/1024/768/390/320 px, troca de conta, compacto/tela cheia com anexo, fechamento com teclado móvel, preparo/biblioteca/desempenho e foco persistente. Treinos ativos também passaram em desktop/mobile.

Foi reproduzida e corrigida uma contenção intermitente entre recompensas de XP independentes e transações de tarefas/hábitos. Em replica sets, recompensas independentes agora usam transações com retry; Mongo standalone mantém CAS. O teste misto permaneceu ativo e passou na revisão final.

Smoke público após merge: `/studies` HTTP 200 com bundle `main.067ce350.js`; OpenAPI HTTP 200 com 248 caminhos, incluindo targets, attempts, performance, library, overview, timeline, blueprint e anexos. Novas leituras privadas retornam 401 sem autenticação. Preflight permite a origem do frontend e `Idempotency-Key`. Frontend e backend novos estão disponíveis; validação pública não escreveu dados de usuários nem chamou provedores de IA.

O pedido recebido termina truncado em `67. IMPACT ANAL`. A continuação foi solicitada e não recebida; não presumir requisitos posteriores. Credencial de criptografia no Render continua sem confirmação do usuário. Não foram feitas chamadas pagas de IA nem escritas autenticadas em produção.

## Entrega anterior: Sirius Agent

## Resultado final da entrega

PR #19 incorporado à main. Merge: `bfc03eb777989f657b12c19f73d0d7a47a1f0d1e`; revisão final validada: `2c3055380733244d9ec9daf15b5a2aafc330b4aa`.

CI da revisão final e do merge passou integralmente. Workflows da main: [backend](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/36277388147) e [frontend](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/36277388127). Agent: 13 testes com Mongo replica set; segurança: 18 testes; frontend: 39 testes unitários, lint, build e smoke desktop/mobile. Os jobs Mongo passaram, incluindo concorrência mista de XP após garantir o índice por `user_id`.

Smoke público após o merge: frontend `/assistant/settings` HTTP 200 com novo bundle `main.d526ef9c.js`; backend OpenAPI HTTP 200 com 230 caminhos e novas rotas de status, confirmação de ações, planejamento diário, revisão semanal, memória e transcrição. Status, memória e ações retornam 401 sem autenticação. Preflight do chat retorna 200 com origem CORS correta. Vercel reportou deploy bem-sucedido.

Limite da validação: não houve chamadas reais a Gemini/Groq nem escritas autenticadas em produção. Provedores foram simulados; gravações transacionais foram verificadas no Mongo de CI. A configuração de `AI_KEY_ENCRYPTION_KEY` no Render pelo usuário ainda não foi confirmada.

Os registros abaixo descrevem a evolução anterior ao merge; o resultado final acima substitui as pendências de publicação mencionadas neles.

## Histórico da implementação

Branch: `feat/sirius-agent`, criada da main `ce9103bd024a911a3ba5c1ae665d5f26535648ae`.

Implementação: roteador Gemini/Groq, ferramentas por usuário, propostas confirmadas transacionais, migração das chamadas antigas, credenciais mascaradas/criptografadas, conversas, memória, RAG, planejamento, sugestões, voz e configurações. Detalhes e limitações: [docs/SIRIUS_AGENT.md](docs/SIRIUS_AGENT.md), [docs/AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md).

PR: https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/19

CI validado no commit `1c12c1f`: backend/security, XP, transações Mongo e frontend/build/smoke. Confirmação concorrente do agente grava uma única despesa e auditoria; rollback e isolamento de proprietário passaram. Lint sem avisos, build com `CI=true` e smoke Chromium em 1440/390/320 px. Chamadas a provedores foram simuladas. O teste antigo de concorrência mista de XP revelou uma leitura desnecessária dentro da transação; a correção reutiliza o saldo já bloqueado, reinicializado em cada retry, e tem regressão dedicada.

Últimos ajustes antes de publicar: limitar a entrada da conferência independente sem truncar o JSON no meio; teste verifica tamanho, parsing e rejeição de evidência inventada. A rodada seguinte voltou a reproduzir timeout na concorrência mista de XP, portanto o cache sozinho não foi considerado solução suficiente. A preparação de atividades agora garante índice por `user_id` para as consultas que adquirem o bloqueio. Merge e smoke de produção serão registrados após os checks desta revisão.

Configuração externa: `AI_KEY_ENCRYPTION_KEY` no Render para salvar novas chaves e migrar as antigas. Atlas Vector Search é opcional; exige índice e variável específicos. Nenhum faturamento deve ser ativado. Autoações e streaming permanecem sem implementação operacional, mesmo se suas flags reservadas forem alteradas.
