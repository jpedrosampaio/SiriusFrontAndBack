# Mongo runtime burn-down

Baseline: 669 chamadas diretas. Contagens geradas de código, não de dados. Um domínio só está concluído quando as rotas reais e sua cobertura PostgreSQL passam. A linha identity inclui acessos de XP/outros domínios à coleção users, não apenas rotas de autenticação.

| Domínio | Chamadas Mongo restantes |
|---|---:|
| agent | 58 |
| contest | 19 |
| files_rag | 49 |
| finance | 65 |
| goals | 9 |
| health | 111 |
| identity | 11 |
| notifications | 24 |
| other | 17 |
| planning | 40 |
| studies | 243 |

Total direto: **646**; collections: **78**; dinâmicos: **9**; construtores GridFS: **1**; imports: **18**.

Scripts de inventário, testes e server_partial.py (sem import pelo app) são excluídos. As chamadas dinâmicas ainda precisam ser migradas, mesmo quando repetem collections já contadas. As chamadas em helpers recebem os domínios das collections; uma operação composta pode aparecer em mais de uma linha.

Histórico de implementação: 669 → 646 (identidade/perfil/credenciais e uso Gemini). Consulte o JSON para a contagem exata da revisão corrente.
