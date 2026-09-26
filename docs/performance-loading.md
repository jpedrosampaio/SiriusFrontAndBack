# Desempenho e carregamento

Base: PR 11, páginas de Estudos/Treinos ainda com os mesmos chunks da main. Baseline gzip: Estudos 50.757 bytes; Treinos 26.105 bytes (docs/performance-baseline.json). Gráficos, simulados, redação e evolução extraídos para abas lazy; comparação final registrada após build.

Dashboard: antes auth + stats + 7 painéis = 9 requests. Depois auth + stats (j? contém sugestões) + bundle de 5 painéis = 3 iniciais, mais analytics ao aproximar o gráfico = 4 no total. Bundle usa gather(return_exceptions=True) e retorna erros por painel, com retry visível; principal continua independente. Não afirma que todos os painéis têm consultas otimizadas: wrappers ainda autenticam individualmente.

Analytics: 7 leituras brutas sequenciais antes, 8 consultas agregadas em paralelo depois (hábitos requer count e datas). Retorna no máximo 90 grupos por coleção. Teste compara contrato completo com implementação congelada da main, e verifica total acima de 5.000 registros. Mantém semântica de study_sessions do endpoint; foco j? ? incluído em relatórios e dashboard.

Contexto do assistente: 9 consultas sequenciais antes; 7 após correção, com duas dependentes para tarefas e demais paralelas. Relatórios: 13 consultas agregadas/paralelas em lugar de 5 listas limitadas. Mais métricas, sem enviar documentos brutos para IA.

CI imprime PERFORMANCE_DISPOSABLE_MONGO com cinco amostras e mediana de analytics e contexto antes/depois. São medições de fixtures em Mongo descartável, não latência do Atlas/Render em produção. Comparação antiga de analytics acima do limite processa menos dados e ? explicitamente marcada truncated.

Requests de Estudos/Treinos: cache em memória 10s, limite 100 chaves, coalescência de GET, invalidação antes/depois de mutações e troca de conta; GET com signal respeita cancelamento e não compartilha cache. Retry automático uma vez apenas em falhas transitórias de leitura. Mutações nunca repetidas automaticamente. Teste impede escrita tardia no cache de outra conta.
