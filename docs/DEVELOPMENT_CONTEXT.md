# Contexto de desenvolvimento

Este documento orienta a seleção de contexto, não substitui contratos nem critérios de entrega. Regras permanentes ficam em [AGENTS.md](../AGENTS.md); estado operacional em [HANDOFF.md](../HANDOFF.md). Não importe automaticamente as referências abaixo.

## Auditoria e fontes

Base auditada: `main` em `280dcd73d688d3f34ab3cb9a5deedb83a278e4c7`. Não havia AGENTS no repositório. O HANDOFF acumulava aproximadamente 70 KB de status e históricos; documentos antigos ainda descreviam Mongo/Render e migrations manuais. O RTK local tratava toda saída condensada como completa, regra substituída pelas instruções atuais de preservação de evidências e leitura integral quando necessária.

- [Histórico integral do HANDOFF](history/HANDOFF_THROUGH_PHASE_9.md): cópia exata do blob dessa base, SHA-256 `7e543cd8c4a54112d92523f8f7fbcc32a78f42f97f2cd0fdc8c00c0aba1f550e`. É um registro histórico, incluindo estados já superados; não execute seus comandos como instruções atuais.
- [Plano-mestre original](SIRIUS_3_MASTER_PLAN.md): cópia integral do anexo fornecido pelo proprietário, sem editar suas 14 fases; 69.111 bytes, SHA-256 `bdd07d91175fd5024f18a05b541e8677fc3884b34a21648087e942a653f1c056`. Atributo Git específico preserva seus bytes/CRLF. Pedidos de execução no texto original são históricos; a autorização vigente vem da sessão e do HANDOFF.
- Código, contratos, workflows e evidências de publicação atuais prevalecem sobre descrições antigas de implementação. Quando uma fonte divergir, investigue a diferença e registre a decisão; não invente compatibilidade ou fatos ausentes.

## Seleção de contexto

1. Leia AGENTS/HANDOFF uma vez ao retomar uma tarefa. Identifique escopo autorizado, próxima fase e gates pendentes.
2. Localize a seção pertinente com `rg -n` antes de ler. Ao iniciar fase autorizada, confira os requisitos gerais aplicáveis do plano e a seção dessa fase; não carregue todas as fases ou todo o histórico. Para achar limites de uma fase, por exemplo: `rg -n '^FASE (10|11)' docs/SIRIUS_3_MASTER_PLAN.md`.
3. Audite os pontos de entrada, modelos/ownership, contratos, produtores/consumidores e testes dessa área. Siga as integrações realmente alcançadas, inclusive calendário, Agent e efeitos financeiros/XP quando envolvidos. A tabela é um ponto de partida, não um limite de investigação.
4. Use leituras por trecho e pesquisas específicas. Abra inventários grandes, logs completos e histórico somente para responder uma dúvida concreta. Amplie o escopo se uma falha, dependência ou contrato exigir.

| Área afetada | Referências iniciais |
|---|---|
| Edital, upload, preparação | [EDITAL_ANALYSIS_MODES](EDITAL_ANALYSIS_MODES.md), [FILE_UPLOAD_AUDIT](FILE_UPLOAD_AUDIT.md), [PREPARATION_ENGINE](PREPARATION_ENGINE.md) |
| Radar e evidências | [EDITAL_INTELLIGENCE](EDITAL_INTELLIGENCE.md), [edital-evidence](edital-evidence.md) |
| Questões, estratégia, simulados | [QUESTIONS_INTELLIGENCE](QUESTIONS_INTELLIGENCE.md), [ADAPTIVE_STRATEGY_ENGINE](ADAPTIVE_STRATEGY_ENGINE.md), [EXAM_INTELLIGENCE](EXAM_INTELLIGENCE.md) |
| Tutor e conhecimento | [SIRIUS_TUTOR](SIRIUS_TUTOR.md), código atual em `backend/ai/` e serviços de estudo |
| Vida integrada, tarefas, agenda, hábitos, metas | [LIFE_STATE_GLOBAL_PLANNER](LIFE_STATE_GLOBAL_PLANNER.md), [OPERATIONAL_PLANNING](OPERATIONAL_PLANNING.md), `backend/services/life_adapters.py`, `backend/ai/planning.py` |
| Financeiro | [FINANCE_INTELLIGENCE](FINANCE_INTELLIGENCE.md), contratos/rotas e integrações financeiras atuais |
| Treinos | [TRAINING_INTELLIGENCE](TRAINING_INTELLIGENCE.md), [WORKOUT_SESSION_UX2](WORKOUT_SESSION_UX2.md), [WORKOUT_YOUTUBE](WORKOUT_YOUTUBE.md), `backend/training_contracts.py`, `backend/services/training_intelligence*`, `backend/services/workout_*`, componentes/páginas de treino |
| Nutrição | `backend/services/nutrition*`, modelos, rotas/componentes atuais e integrações com Life State/Agent |
| Agent e IA compartilhada | `backend/ai/registry.py`, `core.py`, `agent.py`, `backend/services/core_writes.py`, [shared-assistant](shared-assistant.md), documentos dos motores envolvidos |
| Persistência e migrations | [POSTGRES_ARCHITECTURE](POSTGRES_ARCHITECTURE.md), [DATA_MODEL](DATA_MODEL.md), [PRODUCTION_MIGRATIONS](PRODUCTION_MIGRATIONS.md), modelos/revisões Alembic atuais |
| Desempenho, mobile e confiabilidade | [DATABASE_PERFORMANCE](DATABASE_PERFORMANCE.md), [performance-loading](performance-loading.md), [reliability-mobile](reliability-mobile.md), [functional-reliability](functional-reliability.md) |

`AI_ARCHITECTURE`, `AI_MIGRATION_MAP`, `SIRIUS_AGENT` e `SIRIUS_CORE_3` preservam descrições de etapas anteriores. Leia seus trechos apenas quando relevantes; Mongo/Atlas, Render, duração padrão e instruções manuais antigas não descrevem necessariamente o runtime atual. POSTGRES_ARCHITECTURE contém a auditoria da migração original; o status de sua antiga branch não é um bloqueio atual. O workflow protegido é a referência de migrations de produção.

## Autorrevisão antes de abrir a PR

- Compare o diff com o pedido: todos os objetivos atendidos, módulos preservados, nenhum escopo/serviço indevido. Confira o diff completo do conteúdo editado, não só o resumo. Em cópias integrais sem edição, verifique igualdade e proveniência em vez de reler o documento extenso.
- Revise contratos e seus produtores/consumidores: fontes e vínculos reais, ownership, Decimal, datas/fuso, limites, paginação, índices/consultas e comportamento de dados antigos.
- Exercite mentalmente e nos testes apropriados criação/alteração/exclusão, replay, retomada, concorrência, rollback, falha parcial, dados desconhecidos e ausência de provedor. Verifique que prévias não gravam e que pontuação/XP não duplicam.
- Confira a experiência em desktop/mobile, estados vazios/erro/carregamento, acessibilidade dos controles, fechamento/retomada e atualização após mutações. Não trate uma tela de erro como smoke aprovado.
- Confirme que os testes exercitam os riscos e não apenas espelham a implementação; mantenha todos os gates existentes. Declare resultados locais/remotos com SHA e limitações reais. Corrija problemas antes da revisão externa, sem substituir a revisão Codex por autorrevisão.
- Em PR apenas documental, confira referências, proveniência, preservação integral das fontes, status atual versus histórico e ausência de alterações funcionais/workflows. Não crie testes redundantes que apenas reproduzam o texto.

## Validação e entrega — gates inalterados

As definições executáveis abaixo são a fonte dos comandos, dependências e serviços de CI; não copie sua configuração para criar outro processo concorrente. Saída resumida economiza contexto, não trabalho ou cobertura.

| Workflow obrigatório | Cobertura preservada |
|---|---|
| [security-tests.yml](../.github/workflows/security-tests.yml) | Sintaxe backend, regressões `test_*regression.py`, segurança e unitários frontend/service worker; sem serviços reais de IA |
| [postgres-tests.yml](../.github/workflows/postgres-tests.yml) | Banco PostgreSQL descartável desde vazio, Alembic upgrade/check, todos `test_postgres_*.py` e YouTube com mocks |
| [production-migration-tests.yml](../.github/workflows/production-migration-tests.yml) | Segurança do workflow, aprovação/SHA, locks, gates de versão, retry/rollback em banco descartável |
| [frontend-build.yml](../.github/workflows/frontend-build.yml) | `npm ci`, lint, unitários, build de produção, **todas** as suítes de `npm run test:smoke`, artefatos inclusive em falha |

Preserve as cinco larguras reais: **320, 390, 768, 1024 e 1440 px**. Não use filtro de suítes para substituir a execução completa exigida. Não desabilite checks nem mude triggers para economizar contexto. Em falha, investigue o log necessário e repita o check corrigido; quando uma mudança tornar evidência anterior inválida, renove os checks/revisão no novo SHA. Não repita testes já válidos sem novo motivo técnico.

Antes do merge: autorrevisão, CI completo verde, revisão Codex limpa do head final e apontamentos relevantes resolvidos. Se houver migration, siga o workflow protegido/aprovação do proprietário e aguarde sua confirmação antes do merge funcional. Depois: deploys Vercel/Northflank no SHA do merge, leituras de `health/live`, `health/ready` e frontend. Nenhuma gravação de teste em produção.

Ao concluir, informe resultado, testes/revisão, publicação e limitações materiais de forma curta. Não declare uma fase concluída enquanto algum gate obrigatório estiver pendente.

## Continuidade e manutenção

HANDOFF deve conter somente estado atual, próxima fase/autorização, migrations/bloqueios e decisões materiais, com links para evidências. Não acrescente logs, cada tentativa de teste ou instruções permanentes repetidas. Registre detalhes de publicação em documento histórico separado ou na PR; preserve snapshots históricos sem reescrevê-los.

Ao retomar outra sessão, releia o estado atual e verifique Git/PR/checks/deploys relevantes antes de agir. Atualize apenas fatos que mudaram; a existência do plano ou de comandos antigos não autoriza novas fases. Esta melhoria termina após sua integração e validação; aguarde nova autorização para a Fase 10.
