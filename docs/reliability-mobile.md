# Continuidade, estudos e mobile

## Comportamento entregue

- Assistente em portal no `body`, botão arrastável com posição persistente, movimento por setas e painel com fechamento explícito, Escape e controle de foco. A altura acompanha o viewport visual do celular.
- Navegação mobile com Hoje, Estudos, Treinos, Tarefas e Mais. Controles de sessão maiores, campos que não provocam zoom automático e respeito a movimento reduzido.
- Pomodoro por horário de término, retomada por usuário/assunto e confirmação pendente recuperável. A mesma chave registra tempo, XP e sessão uma única vez em transação MongoDB.
- Rascunhos de estudo salvos no dispositivo e na conta. Revisões detectam concorrência entre abas. Um rascunho divergente não substitui silenciosamente uma edição remota.
- Treinos com retomada explícita, relógios por timestamp, rascunho da série e gravações serializadas. Versões detectam telas desatualizadas; conclusão grava histórico e XP atomicamente.
- Editais enviados para fila persistente no MongoDB; inputs em GridFS, sem novos serviços. Cada processo executa uma análise de cada vez. Análises interrompidas falham explicitamente, sem repetir chamadas de IA automaticamente. O usuário pode navegar e consultar o resultado depois.
- Extrações novas preservam os números reais das páginas. A correspondência por nome de disciplina é uma indicação de onde conferir, não uma certificação de que toda interpretação está correta. Análises antigas precisam ser reenviadas para obter essas fontes.
- Disciplinas, pesos, número de questões e conteúdo podem ser revisados antes da importação. Pesos alterados pelo usuário continuam identificados como tal; prioridades provisórias não são apresentadas como oficiais.
- Agenda com datas, orçamento por dia da semana, blocos de 15–120 min, distribuição por peso e sugestões de revisão em 7/21 dias conforme disponibilidade. Replanejamento mantém concluídos; remarcação respeita capacidade. Os blocos aparecem no calendário existente. A frequência de revisão é uma sugestão fixa, não um modelo adaptativo de aprendizagem.
- A página de estudo une notas, foco, aulas, desempenho em questões da disciplina e próximo assunto. A taxa de acertos não é inferida dos checkboxes.

## Operação

Continua sendo necessário MongoDB Atlas/replica set para transações. Nenhuma coleção existente é apagada. Índices de leitura são criados de forma aditiva; conflitos de opções/privilégios geram `index_check` nos logs, sem remover índices do Atlas.

O cache de autenticação é apenas em memória, por 30 segundos, invalidado em mutações e mudanças de credencial. Exportação de PDF/imagem e assistente carregam sob demanda. Painéis secundários não bloqueiam o conteúdo principal.

Totais do dashboard e foco usam agregações sobre o histórico inteiro, sem os limites antigos de 100/1.000/5.000 registros. As demais listagens legadas continuam tendo seus próprios limites e devem ser paginadas conforme o volume real exigir.

Logs `request` incluem método, rota parametrizada, status, duração e ID de correlação; não incluem token, consulta ou conteúdo. `Server-Timing` permite inspecionar o tempo do servidor. Uso Gemini registra contagem e tokens quando fornecidos pelo provedor; isso não é uma fatura. O YouTube continua dependendo de `YOUTUBE_API_KEY`; sem chave, o atalho de pesquisa permanece disponível.

## Validação

- `node --test frontend/tests/*.test.cjs`
- `python -m unittest discover -s backend/tests -p 'test_*regression.py' -v`
- `python -m unittest discover -s backend/tests -p test_security_routes.py -v`
- `npm run build` em `frontend`.
- CI executa as transações e concorrência em MongoDB descartável com replica set, incluindo duplicidade de foco/treino, rollback e totais além dos limites antigos.

Testes visuais usam dados simulados e interceptam as chamadas de API; não geram treinos/editais nem alteram contas de produção. Avaliação de latência em produção e certificação manual de um edital completo continuam dependendo dos dados reais.
