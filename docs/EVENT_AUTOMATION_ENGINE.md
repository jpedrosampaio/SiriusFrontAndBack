# Event & Automation Engine 2.0

## Contratos e fontes

`event_contracts.py` define eventos tipados, fatos, razões e preferências. Eventos referenciam registros canônicos próprios, não copiam o ledger nem criam domínio/planejador concorrente. O motor notifica e propõe; nunca conclui atividades, paga contas, muda cargas, registra alimentos, altera planos ou move compromissos. Global Planner continua sendo o único alocador. As integrações reutilizam Life State, Questions, Finance, Training e Nutrition Intelligence.

- Tarefas vencidas usam ocorrências reais; recorrentes mostram a última pendência nos 32 dias anteriores (inclui mensal/último dia do mês). O histórico anterior fica preservado, fora da janela de alerta. Conclusões, estudos e treinos usam seus registros próprios recentes.
- Revisões usam o último `ReviewEvent` do tópico ativo, com paginação incremental. Erros reutilizam `forensic_clusters`: três questões distintas no mesmo assunto/causa, excluindo agregados/em branco e resolvendo erros com acertos posteriores. Janela de sete dias/até 500 tentativas recentes; cobertura parcial explícita, sem diagnóstico semântico completo.
- Provas usam data/origem registrada e marcos 90/30/14/7/2/1/0 dias. Dados manuais/extrativos não viram fontes oficiais. Editais apontam para o impacto existente; não inventamos impacto.
- Despesas vêm do ledger, orçamentos de limites efetivos com Decimal (80%/excedido). Obrigações usam somente vencimentos conhecidos do FinanceEngine; contas apenas mensais não recebem dia inventado. Saldo bancário fica desconhecido.
- Metas vencidas usam prazo/progresso; nenhuma trajetória ideal é presumida. Nutrição após 18h locais usa somente metas confirmadas e composição conhecida; sem prescrição, gasto energético ou diagnóstico.
- Limites e avisos dos motores são preservados. Lotes parciais não representam totais completos.

## Fila e transações

Reutilizamos `ai_events`, `ai_insights`, `ai_preferences` e recibos. Migration `e47c2b6a901d` (parent `c9e42a7d160b`) adiciona prazos/tentativas, `ai_event_deliveries` com FK composta de ownership, leases, vínculo/recibo/histórico, e entrega durável de respostas Telegram. Históricos/textos anteriores permanecem; estados legados entregues não recebem IDs inventados do provedor. Downgrade recusa apagar auditoria nova.

Uma `system.scan` persistida por conta optante guarda cursor e próximo prazo no PostgreSQL. Bootstrap lê até dez contas; rodada reserva um dos quatro claims para varredura e três para eventos, com empréstimo de vagas ociosas entre categorias: varreduras recorrentes não bloqueiam seus alertas e alertas não impedem novas varreduras. Processa até duas entregas de eventos e uma resposta Telegram por rodada. Páginas canônicas de quarenta itens avançam por UUID; vários lotes podem ser necessários. Sucesso agenda nova varredura após quinze minutos. O worker existente só desperta: `AUTOMATION_POLL_INTERVAL_SECONDS` 30–900 segundos, padrão 60. Prazos futuros não dependem da memória; indisponibilidade do serviço pode atrasar execução.

Claims usam `FOR UPDATE SKIP LOCKED`, lease e token. Eventos têm até cinco tentativas automáticas/backoff persistido; esgotamento é terminal. Origem é revalidada sob lock da conta, na mesma transação dos motores, evitando conexões aninhadas/pool esgotado. Publicação de insight/outbox é atômica. Fonte/ocorrência/período deduplicam produtores transacionais e varredura; replays não duplicam XP, pontuação ou canais. Automação não emite eventos de alterações próprias nem modifica dados de negócio.

## Política, API e entrega

Rotas autenticadas: `/api/automations/state`, `PUT /policy`, `GET /events` com cursor, `GET /inbox`, `POST /deliveries/{id}`. Escritas exigem `Idempotency-Key`; retry HTTP repete chave/intenção. O opt-in é o existente `Preferences.automations`; perfil/ferramentas bloqueadas permanecem. Clientes antigos que omitem a política nova a preservam.

Cada tipo tem ativação, prioridade explícita e canais `in_app`/`telegram`. Condições persistentes têm frequência diária/semanal por condição/ocorrência; relatórios e meta alimentar deduplicam pelo período. Conclusões, despesas e atualizações são transições: uma vez por registro, sem avisá-las novamente só porque outro dia começou. Ocorrências distintas continuam evidências distintas. Cap diário existente: 0–10 insights; zero cancela nova publicação. Horário silencioso de minuto herda Agent quando ausente; fuso IANA e instantes UTC respeitam DST. Nenhuma prioridade ignora silêncio automaticamente. Nunca/dismiss/snooze continuam considerados.

No Sirius, `available` significa disponível para consulta; só leitura explicitamente confirmada pelo dono gera `delivered/owner_read`. Fechar toast não confirma leitura. O console mostra observação histórica, razões, erros, tentativas e paginação; Telegram revalida a fonte antes de enviar.

Telegram usa segredo de webhook, conversa privada/origem, vínculo exato e chat. Mudanças de vínculo são bloqueadas durante envio. IO externo fica fora da transação. Só `ok=true` com `message_id` e chat correspondente confirma entrega. Recusas temporárias conhecidas têm até cinco retries/backoff 30–3600s. Timeout, recibo inválido e crash no intervalo externo ficam `uncertain`, sem reenvio automático. API externa sem idempotência não garante exatamente uma entrega: reenvio exige confirmação do risco de duplicação, até oito tentativas totais. Histórico completo limitado pelo número de tentativas; erros brutos/credenciais não são logados.

Flags existentes: `AUTOMATION_DRY_RUN=true` mantém insights internos e cancela Telegram automático como `simulation_only`; `AI_AUTOMATIONS_ENABLED` controla eventos proativos. O transporte das respostas de comandos continua ativo com bot configurado, mesmo quando eventos proativos estão desativados; retries conhecidos permanecem duráveis. A tela informa disponibilidade real. Vincular Telegram não ativa canais de regras silenciosamente. Lembretes legados continuam; email/WhatsApp/browser não aparecem como novos provedores confirmados.

## Resumos, Agent e Telegram

`GET /api/dashboard/daily-briefing?mode=morning|night|weekly&day=AAAA-MM-DD` é somente leitura. `daily-summary` legado permanece intacto. Daily Briefing2 conecta estado atual/Global Planner; Night Review e Weekly Coach comparam registros executados ao planejamento atual e apresentam pendências/agenda seguinte. Templates atuais não justificam aderência histórica exata. Datas passadas (até 30 dias) não recebem Life State atual falsamente rotulado como histórico. Treino planejado exige plano próprio ativo/disponibilidade declarada; alimentação desconhecida continua desconhecida. Propostas levam ao Calendário para revisar/confirmar.

Textos novos são determinísticos, sem API real de IA. Ferramentas de leitura: `get_daily_briefing`, `get_night_review`, `get_weekly_coach`, `get_automation_state`. Telegram reconhece `/hoje`, `/treino`, `/semana`, `/revisoes` e perguntas naturais antes do parser financeiro; essas consultas não chamam IA nem escrevem despesas. Comandos financeiros explícitos preservam recibos/Decimal. Respostas têm lease, binding fixo, retries limitados e expiram em um dia. `GET /api/automations/telegram-replies` pagina o histórico próprio; `POST /telegram-replies/{update_id}` exige consentimento explícito e chave idempotente para recuperar apenas a resposta armazenada incerta/falha, sem reexecutar o comando nem duplicar transações, até oito tentativas. Resumo manual diário deduplica conta/data e conta envio somente com recibo real.

## Validação e publicação

PostgreSQL descartável/providers mockados verificam ownership, resoluções, dedup, opt-out/cap, DST, concorrência/pool, crash/retry, recibos ambíguos, vínculos, clientes antigos, consultas sem IA e agregação completa. Smoke real nas cinco larguras inclui falhas/retry HTTP, consentimento, recibos e overflow, acrescentado a todas as suítes existentes. Quatro workflows e revisão Codex limpa no SHA final permanecem obrigatórios.

Este documento descreve a branch. Publicação exige registro imutável do SHA aprovado, workflow protegido com aprovação do dono, migration confirmada antes do merge funcional, deploys exatos Vercel/Northflank e validação de produção somente leitura. Consulte HANDOFF para estado atual. Fase 13 não está autorizada.
