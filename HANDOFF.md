# Sirius — handoff

## UX 2.0 / Studies 2.0 — entrega em validação

Branch `feat/sirius-ux-studies-2`, baseada em `883d790`. AppShell único, Sirius contextual com anexos, quatro áreas de estudos, preparações genéricas, foco retomável, domínio por evidências, banco de erros, revisões, plano adaptativo, simulados transacionais e acompanhamento de fontes públicas. Arquitetura, limites e operação em [docs/UX_STUDIES_2.md](docs/UX_STUDIES_2.md).

Validação local: lint sem avisos, build de produção, 39 testes frontend, 18 de segurança e 162 regressões backend (37 dependentes de Mongo ignoradas localmente; executadas nos jobs dedicados de CI). Smoke local de navegador passou em 1440/1024/768/390/320 px após corrigir o cabeçalho, métricas e abas de Treinos. PR #20 aberto. CI final e smoke público serão registrados após publicação.

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
