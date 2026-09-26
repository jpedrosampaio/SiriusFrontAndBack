# Desempenho e carregamento

Base: PR 11, p?ginas de Estudos/Treinos ainda com os mesmos chunks da main. Baseline gzip: Estudos 50.757 bytes; Treinos 26.105 bytes (docs/performance-baseline.json). Gr?ficos, simulados, reda??o e evolu??o extra?dos para abas lazy; compara??o final registrada ap?s build.

Dashboard: antes auth + stats + 7 pain?is = 9 requests. Depois auth + stats (j? cont?m sugest?es) + bundle de 5 pain?is = 3 iniciais, mais analytics ao aproximar o gr?fico = 4 no total. Bundle usa gather(return_exceptions=True) e retorna erros por painel, com retry vis?vel; principal continua independente. N?o afirma que todos os pain?is t?m consultas otimizadas: wrappers ainda autenticam individualmente.

Analytics: 7 leituras brutas sequenciais antes, 8 consultas agregadas em paralelo depois (h?bitos requer count e datas). Retorna no m?ximo 90 grupos por cole??o. Teste compara contrato completo com implementa??o congelada da main, e verifica total acima de 5.000 registros. Mant?m sem?ntica de study_sessions do endpoint; foco j? ? inclu?do em relat?rios e dashboard.

Contexto do assistente: 9 consultas sequenciais antes; 7 ap?s corre??o, com duas dependentes para tarefas e demais paralelas. Relat?rios: 13 consultas agregadas/paralelas em lugar de 5 listas limitadas. Mais m?tricas, sem enviar documentos brutos para IA.

CI imprime PERFORMANCE_DISPOSABLE_MONGO com cinco amostras e mediana de analytics e contexto antes/depois. S?o medi??es de fixtures em Mongo descart?vel, n?o lat?ncia do Atlas/Render em produ??o. Compara??o antiga de analytics acima do limite processa menos dados e ? explicitamente marcada truncated.

Requests de Estudos/Treinos: cache em mem?ria 10s, limite 100 chaves, coalesc?ncia de GET, invalida??o antes/depois de muta??es e troca de conta; GET com signal respeita cancelamento e n?o compartilha cache. Retry autom?tico uma vez apenas em falhas transit?rias de leitura. Muta??es nunca repetidas automaticamente. Teste impede escrita tardia no cache de outra conta.
