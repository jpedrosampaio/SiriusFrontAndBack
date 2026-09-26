# Correções funcionais

Base auditada: main 8b9424d (PR 9).

- Cargos: comparação exata após normalização tipográfica, preservando níveis e qualificadores. Nomes similares e códigos diferentes permanecem separados; pode haver duplicatas incertas, preferíveis à perda de cargo oficial.
- Recorrência: data persistida na criação, regra única em tarefas/dashboard/calendário. Mensal em 29/30/31 usa último dia de meses menores; semanal usa dia da semana da data inicial. Dados antigos sem data usam criação no fuso de São Paulo.
- Dashboard: progresso percentual armazenado nas metas, tarefas aplicáveis hoje, conclusões distintas por tarefa.
- Relatórios: diário/semana desde segunda/mês até hoje; sprint exige datas explícitas. Treze consultas independentes em paralelo, agregação no Mongo. Atividades limitadas ao intervalo; cadastros criados no intervalo e progresso atual dessas metas identificados separadamente, pois não há histórico de percentuais.
- Sugestões: regras determinísticas, evidências numéricas e links reais, sem chamada de IA.

Regressões: níveis I–IV/Júnior/Pleno/Sênior, códigos/campos de identidade, meses curtos/bissexto, ano/semana, datas futuras, propriedade dos dados e históricos acima de 1.000 registros. Suites isoladas locais passaram; integração Mongo roda no CI. Não mede latência de produção nem altera dados online. Sem merge automático.
