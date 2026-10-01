# Mongo runtime burn-down

Baseline: 669 chamadas diretas. Contagens geradas de código, não de dados. Um domínio só está concluído quando as rotas reais e sua cobertura PostgreSQL passam. A linha identity inclui acessos de XP/outros domínios à coleção users, não apenas rotas de autenticação.

| Domínio | Chamadas Mongo restantes |
|---|---:|
| agent | 58 |
| contest | 19 |
| files_rag | 49 |
| finance | 65 |
| goals | 9 |
| health | 109 |
| identity | 11 |
| notifications | 24 |
| other | 17 |
| planning | 25 |
| studies | 241 |

Total direto: **627**; collections: **78**; dinâmicos: **9**; construtores GridFS: **1**; imports: **18**.

Scripts de inventário, testes e server_partial.py (sem import pelo app) são excluídos. As chamadas dinâmicas ainda precisam ser migradas, mesmo quando repetem collections já contadas. As chamadas em helpers recebem os domínios das collections; uma operação composta pode aparecer em mais de uma linha.

Histórico de implementação: 669 → 646 (identidade) → 627 (rotas de tarefas/hábitos/calendário). Consulte o JSON para a contagem exata da revisão corrente.
