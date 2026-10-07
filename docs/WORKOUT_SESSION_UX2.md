# Workout Session UX 2.0

Base: main `c5c3f2c` (PR #24). React/Vercel → FastAPI/Northflank → PostgreSQL/Neon permanece intacto. Esta fase não possui migration, dependência nova, alteração de regras financeiras/estudos ou nova chamada de IA.

## Fluxo

Na ficha, **Iniciar Treino com Timer** abre o modo treino. A sessão destaca um exercício por vez, com prescrição, séries registradas e entrada de carga/repetições/RPE. A fila mostra atual, concluído ou pendente e a quantidade de séries. Trocar visualmente não conclui exercícios nem envia uma request; rascunhos são separados por exercício.

Os campos começam com a última série registrada ou a prescrição numérica. Cargas textuais não viram números fictícios. Repetições são obrigatórias (1–999); carga e RPE são opcionais. Peso aceita vírgula decimal e até três casas; RPE aceita 1–10. A sugestão existente de próxima carga aparece somente no exercício correspondente, sem alterar a progressão do backend.

**Concluir série** envia o PATCH existente, com `sets_data`, `completed`, `current_exercise_idx`, `revision` e `Idempotency-Key`. A última série conclui o exercício automaticamente. O foco permanece nele e oferece **Ir para próximo**, sem avanço automático. A fila permite escolher outro exercício.

Por 20 segundos depois de uma confirmação, **Desfazer última série** restaura o conjunto anterior pelo mesmo PATCH, com a revisão retornada e uma nova chave. Não é uma remoção apenas visual: só atualiza após confirmação SQL. Se outra tela alterou o treino, o 409 impede sobrescrever seus registros. Trocar de exercício encerra a oferta de desfazer. Retry de desfazer reutiliza seu payload/chave.

## Descanso e persistência

O descanso inicia depois de cada série confirmada, inclusive a última do exercício, usando `rest_seconds` (zero é respeitado), com fallback no timer da sessão. Controles −15s / Pular / +15s e presets em uma expansão secundária. Deadline absoluto e relógio local evitam polling e corrigem o tempo após suspensão. No zero: aviso visual e uma vibração opcional, sem áudio repetitivo nem pedido de permissão.

GET `/workout-sessions/active` restaura sessão, séries, progresso e `current_exercise_idx` persistidos no backend. A seleção visual mais recente, rascunhos por exercício, deadline de descanso e request pendente ficam em localStorage com namespace **usuário + sessão**. Isso complementa o backend: em outro dispositivo, o foco começa no último índice salvo pelo PATCH, não na seleção exclusivamente visual do primeiro dispositivo. Reabrir a mesma aba/navegador recupera também a seleção visual e os rascunhos. O comando **Retomar treino** abre a sessão recuperada. Não há modo offline completo.

Antes da escrita, o cliente guarda payload/revisão/chave exatos. Timeout, perda de rede ou 5xx mantém os campos bloqueados para edição e oferece retry, evitando que uma série já salva seja adicionada novamente. GET de retomada pode confirmar o progresso antes do receipt; uma resposta antiga não substitui revisão mais nova já carregada. Erros definitivos 4xx (exceto 408/429) permitem editar; 409 reconsulta a sessão. Finalizar/abandonar/trocar ficam indisponíveis enquanto houver escrita incerta. Armazenamento local pode ser restringido pelo navegador; séries confirmadas continuam no PostgreSQL.

## Histórico e tutorial

Histórico: uma chamada sob demanda para o exercício escolhido, com cache por usuário/QueryClient. A prévia mostra até três séries do último treino; detalhes ficam em expansão e há somente uma comparação. Cada exercício tem seu próprio estado de erro/carregamento para impedir que uma resposta tardia afete outro foco. Falhas secundárias mostram retry sem impedir registro.

**Como executar** monta `WorkoutTutorial` existente. Texto disponível imediatamente; busca de até três vídeos apenas ao abrir. Cache de vídeos preservado; iframe somente após **Assistir aqui**, sem autoplay; chave YouTube permanece no backend. Abrir sessão e trocar exercícios não busca vídeos nem histórico/evolução de todos os exercícios.

## Conclusão, mobile e acessibilidade

Finalizar abre feedback com duração, exercícios e séries realmente registrados. Somente depois do POST confirmado aparece **Treino concluído**, com duração do servidor, contagens e XP real. Volume é a soma `carga × repetições`; só aparece se todas as séries consideradas tiverem carga/repetições conhecidas, incluindo zero explicitamente registrado. Não há calorias estimadas nem comparação de sessão inventada: o histórico parcial de um exercício não prova volume da sessão anterior inteira.

Abandonar é secundário, com confirmação e contagem do progresso, e erro inline se a escrita falhar. Ambos os encerramentos limpam o estado local desta sessão.

Desktop: foco dominante e fila lateral. Tablet: duas colunas ou uma conforme espaço disponível. Mobile: ação de série fixa acima da navegação, com `safe-area-inset-bottom` e espaço no fim do conteúdo; cabeçalho sticky abaixo da barra do aplicativo. Hero e estatísticas saem da área de execução. Labels, `aria-current`, progressbar, mensagens de status, botões nomeados, alvos de 44px e dialogs Radix com focus trap. O countdown não é anunciado a cada segundo.

Screen Wake Lock é opcional, com feature detection, falha silenciosa, liberação no unmount/encerramento e nova aquisição quando o documento volta a ficar visível. Aquisição tardia após unmount libera o sentinel recebido. Implementação segue o [contrato W3C](https://www.w3.org/TR/screen-wake-lock/); a disponibilidade depende do navegador/plataforma e não bloqueia o treino.

## Componentes e verificação

`WorkoutSession` isola foco, fila, formulário, descanso, desfazer, tutorial e abandono. `HistoryPreview` encapsula histórico compacto. `useWorkoutWakeLock` mantém o ciclo opcional. Funções puras em `lib/workout-session.js` validam entradas e calculam resumo. `Workouts.js` mantém contratos, ficha/estatísticas/evolução/histórico e dialogs de conclusão, com menos de 450 linhas de UI antiga removidas.

`npm run lint`, `npm run test:unit`, `npm run build`, `npm run test:smoke`. O novo `tests/workout-session-smoke.cjs` intercepta todas as APIs e usa 12 exercícios, nomes longos, tutorial extenso, 3/8 séries, carga decimal/vazia, RPE opcional e ausência/falha de histórico. Verifica cinco larguras (1440/1024/768/390/320), iniciar, séries, salvamento lento, resposta perdida depois de commit, replay após reload, conflito, desfazer, descanso, próxima/manual, vídeo on-demand, histórico, resumo e abandono. Wake Lock é simulado, inclusive negativa da plataforma. Redução da altura do viewport simula espaço de teclado; não substitui teste físico de teclado/Wake Lock em cada aparelho. Produção é verificada apenas por leituras.
