# Mongo runtime burn-down

Baseline: 669 chamadas diretas. Contagens geradas de código, não de dados. Um domínio só está concluído quando as rotas reais e sua cobertura PostgreSQL passam. A linha identity inclui acessos de XP/outros domínios à coleção users, não apenas rotas de autenticação.

| Domínio | Chamadas Mongo restantes |
|---|---:|
| agent | 58 |
| contest | 19 |
| files_rag | 19 |
| finance | 22 |
| goals | 3 |
| health | 109 |
| identity | 9 |
| notifications | 24 |
| other | 17 |
| planning | 23 |
| studies | 37 |

Total direto: **340**; collections: **60**; dinâmicos: **8**; construtores GridFS: **0**; imports: **13**.

Scripts de inventário, testes e server_partial.py (sem import pelo app) são excluídos. As chamadas dinâmicas ainda precisam ser migradas, mesmo quando repetem collections já contadas. As chamadas em helpers recebem os domínios das collections; uma operação composta pode aparecer em mais de uma linha.

Histórico de implementação: 669 → 646 (identidade) → 627 (tarefas/hábitos/calendário) → 584 (finanças) → 578 (metas) → 544 (catálogo de estudos) → 526 (atividades de estudo) → 504 (workspace) → 462 (Studies 2.0) → 433 (análises/fila de editais; GridFS removido) → 407 (importação/cronogramas/verticalização) → 384 (simulados) → 369 (flashcards/quizzes) ? 351 (tarefas/estat?sticas de estudo) ? 347 (aulas/hist?rico) ? 340 (mapas/reda??es). Consulte o JSON para a contagem exata da revisão corrente.
