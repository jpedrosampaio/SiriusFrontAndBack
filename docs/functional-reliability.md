# Corre??es funcionais

Base auditada: main 8b9424d (PR 9).

- Cargos: compara??o exata ap?s normaliza??o tipogr?fica, preservando n?veis e qualificadores. Nomes similares e c?digos diferentes permanecem separados; pode haver duplicatas incertas, prefer?veis ? perda de cargo oficial.
- Recorr?ncia: data persistida na cria??o, regra ?nica em tarefas/dashboard/calend?rio. Mensal em 29/30/31 usa ?ltimo dia de meses menores; semanal usa dia da semana da data inicial. Dados antigos sem data usam cria??o no fuso de S?o Paulo.
- Dashboard: progresso percentual armazenado nas metas, tarefas aplic?veis hoje, conclus?es distintas por tarefa.
- Relat?rios: di?rio/semana desde segunda/m?s at? hoje; sprint exige datas expl?citas. Treze consultas independentes em paralelo, agrega??o no Mongo. Atividades limitadas ao intervalo; cadastros criados no intervalo e progresso atual dessas metas identificados separadamente, pois n?o h? hist?rico de percentuais.
- Sugest?es: regras determin?sticas, evid?ncias num?ricas e links reais, sem chamada de IA.

Regress?es: n?veis I?IV/J?nior/Pleno/S?nior, c?digos/campos de identidade, meses curtos/bissexto, ano/semana, datas futuras, propriedade dos dados e hist?ricos acima de 1.000 registros. Suites isoladas locais passaram; integra??o Mongo roda no CI. N?o mede lat?ncia de produ??o nem altera dados online. Sem merge autom?tico.
