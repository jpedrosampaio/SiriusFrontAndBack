# Mongo runtime burn-down

Baseline: 669 chamadas diretas. Contagens geradas de código, não de dados. Um domínio só está concluído quando as rotas reais e sua cobertura PostgreSQL passam. A linha identity inclui acessos de XP/outros domínios à coleção users, não apenas rotas de autenticação.

| Domínio | Chamadas Mongo restantes |
|---|---:|
| agent | 38 |
| contest | 19 |
| files_rag | 19 |
| finance | 16 |
| goals | 2 |
| health | 3 |
| identity | 7 |
| notifications | 24 |
| other | 14 |
| planning | 4 |
| studies | 19 |

Total direto: **165**; collections: **39**; dinâmicos: **4**; construtores GridFS: **0**; imports: **13**.

Scripts de inventário, testes e server_partial.py (sem import pelo app) são excluídos. As chamadas dinâmicas ainda precisam ser migradas, mesmo quando repetem collections já contadas. As chamadas em helpers recebem os domínios das collections; uma operação composta pode aparecer em mais de uma linha.

Histórico de implementação: 669 → 646 (identidade) → 627 (tarefas/hábitos/calendário) → 584 (finanças) → 578 (metas) → 544 (catálogo de estudos) → 526 (atividades de estudo) → 504 (workspace) → 462 (Studies 2.0) → 433 (análises/fila de editais; GridFS removido) → 407 (importação/cronogramas/verticalização) → 384 (simulados) → 369 (flashcards/quizzes) → 351 (tarefas/estatísticas de estudo) → 347 (aulas/histórico) → 340 (mapas/redações) → 337 (materiais PDF) -> 326 (workout sessions) -> 320 (workout plans) -> 318 (workout generation/import) -> 314 (workout improvements) -> 306 (workout logs/stats) -> 301 (workout history) -> 291 (daily workout) -> 279 (measurements/insights) -> 262 (nutrition core) -> 257 (recipes) -> 242 (nutrition plans/shopping) -> 238 (study/nutrition exports) -> 233 (reports) -> 227 (dashboard summary) -> 225 (analytics/XP) -> 201 (dashboard panels) -> 200 (workout health preference) -> 194 (global search) -> 187 (Agent reads/context) -> 165 (Agent actions/preferences). Consulte o JSON para a contagem exata da revisão corrente.
