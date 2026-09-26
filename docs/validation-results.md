# Resultado da rodada de confiabilidade

Base inspecionada antes das alterações: `main` em `8b9424d349b0a4db0f48af02f580c8eb6f6c6209`. Alterações em PRs encadeados, sem merge ou deploy:

| PR | Escopo | Base |
| --- | --- | --- |
| #10 | Cargos, recorrência, métricas, relatórios e sugestões | main |
| #11 | Conversa compartilhada, histórico limitado e contexto | #10 |
| #12 | Agregações, carregamento do Dashboard, extração de abas e requests | #11 |
| #13 | Dependências reproduzíveis, lint e E2E | #12 |
| #14 | Serviço Gemini assíncrono | #13 |
| #15 | Evidências de disciplinas, revisões e plano adaptativo | #14 |
| #16 | Histórico e comparação de treinos | #15 |
| #17 | Auditoria e proposta separada de remoção SQLite | #16 |
| #18 | Validação integrada, métricas e ajustes de atualização de tela | #17 |

## Medições

| Medida | Antes | Depois | Método / limite |
| --- | ---: | ---: | --- |
| Dashboard, requisições de dados iniciais | 9 | 3 | Antes: fluxo da main; depois: interceptação Playwright em 1440/390/320 px, com auth, stats e panels |
| Dashboard, após aproximar o gráfico | 9 | 4 | Analytics adiado via IntersectionObserver; abertura do assistente e buscas são interações adicionais |
| Analytics | 23,66 ms | 16,87 ms | Mediana de 5 amostras em Mongo descartável do CI, dataset acima do limite antigo |
| Contexto do assistente | 14,96 ms | 9,56 ms | Mediana de 5 amostras no mesmo CI, sem geração Gemini |
| Studies, chunk inicial bruto | 245.494 B | 149.466 B | Sourcemap identifica o chunk que contém pages/Studies.js |
| Studies, chunk inicial gzip | 50.757 B | 30.954 B | Artefatos baseline/final versionados |
| Workouts, chunk inicial bruto | 128.688 B | 117.501 B | Inclui as novas funcionalidades de comparação |
| Workouts, chunk inicial gzip | 26.105 B | 26.776 B | Aumento de 2,6%; não é alegada redução gzip nesta página |

As dependências foram corrigidas entre os builds, e funcionalidades foram acrescentadas. A comparação de chunks não isola exclusivamente o efeito de code splitting. Abas extraídas possuem chunks adicionais; abrir todas as abas transfere mais dados do que somente a entrada da página. Recharts é carregado pelas abas de gráficos.

CI usado para latências: workflow `36206444626`, job `108303890138`, marcador `PERFORMANCE_DISPOSABLE_MONGO`. Analytics antigo: `[23.15,22.90,23.66,23.84,24.18]`; novo: `[16.87,17.83,15.26,17.03,16.07]`. Contexto antigo: `[15.13,14.77,14.96,15.24,14.80]`; novo: `[20.52,9.56,8.98,9.49,9.86]` ms. O antigo analytics truncava dados; o novo inclui o conjunto completo.

No navegador local com APIs simuladas, o primeiro título do Dashboard apareceu em 381/325/364 ms para 1440/390/320 px. Essa medida inclui navegação e carregamento local, não o término de todos os painéis. Não há amostra equivalente de tempo de tela anterior, portanto não se calcula ganho percentual de carregamento. Não foram medidas latências de produção do Atlas/Render nem chamadas reais ao provedor Gemini.

## Consultas Mongo

Contagens excluem autenticação, comandos de cursor adicionais e controles internos do driver:

| Fluxo | Antes | Depois |
| --- | --- | --- |
| Analytics | 7 leituras sequenciais de documentos, com limites | 8 agregações/contagens paralelas, até 90 grupos por coleção |
| Contexto do assistente | 9 leituras sequenciais | 7 leituras/agregações; tarefas dependem de IDs, demais independentes em paralelo |
| Relatórios | 5 listas limitadas, sem respeitar todos os períodos | 13 agregações/contagens para o intervalo solicitado |
| Estatísticas do Dashboard | Consultas anteriores com contagem de metas inadequada | 18 operações: 16 métricas e duas de tarefas aplicáveis; sugestões derivadas sem consulta adicional |

O bundle de painéis reduz HTTP, mas mantém as consultas dos handlers existentes e sua autenticação individual. Não há alegação de redução equivalente em queries Mongo nesse bundle. Templates de recorrência continuam lidos para expansão correta; isso não é uma agregação de métricas truncada.

## Regressões e limitações

- Cargos semanticamente distintos; mudança de semana/mês, dias 29–31, limites de relatórios; progresso percentual e tarefas aplicáveis; datasets acima de 1.000/5.000 e isolamento por usuário.
- Conversa limitada, rotas reais, income/expense, replay e concorrência; Gemini timeout, quota, structured output, partes de imagem e arquivo não ACTIVE.
- Cache/invalidação e troca de conta, erros da API, quatro semanas e alternância de seleção, comparação de séries sem inventar dados.
- Edital: páginas/títulos TJCE e cargo correto, lista parcial bloqueada; revisão por assunto com replay transacional, validade dos índices e contadores; capacidade de agenda e histórico concluído preservados.
- Lint sem avisos; npm ci com React 18/Router 6; build com CI=true; 39 testes frontend. Os testes Mongo usam containers descartáveis no CI, não o banco do usuário.
- Smoke em 1440/390/320 px: Dashboard, análise, verticalizado, agenda, estudo/Pomodoro, rascunho, registro por assunto, treino e séries. Assistente: arrastar, persistir posição, fechar e viewport reduzido simulando teclado. São testes em Chromium, não homologação em dispositivos físicos iOS/Android.

Houve timeout de transação no teste existente de escritores simultâneos de XP em duas execuções; a repetição do job passou sem remover teste nem aumentar o limite de transação. Isso permanece uma observação de estabilidade do teste/concorrência, não uma falha silenciosamente ignorada.

Não foram certificados salários/vagas do edital; evidências automáticas não substituem conferência de todos os tópicos. As revisões usam questões explicitamente vinculadas a assunto, sem inferir vínculos de simulados antigos. O SQLite permanece uma proposta separada, não um cliente offline reativado.
