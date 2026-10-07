# Tutoriais de treino / YouTube

O tutorial textual continua sendo a orientação principal. Vídeos são complemento externo, sem recomendação clínica. Ficha e sessão ativa usam o mesmo componente.

## Configuração externa

No Google Cloud, habilitar YouTube Data API v3 e criar uma API key restrita a essa API. Salvar **somente** `YOUTUBE_API_KEY` nas variáveis de runtime do backend Northflank e reiniciar o serviço. Não colocar no React, Git, logs ou chat. Não habilitar billing nem solicitar aumento pago de quota. A configuração de produção não foi acessada nesta implementação, portanto não está confirmada.

Sem chave, o backend retorna `status=not_configured`, com lista vazia. Sem quota/rede/provider, retorna `status=unavailable`. A ficha, o tutorial textual e a sessão continuam utilizáveis.

## Fluxo e contrato

`GET /api/workouts/tutorial-videos?exercise=Supino%20reto&muscle_group=Peito`, autenticado. Não é proxy genérico: valida nomes (100/60 caracteres), normaliza espaços e monta o termo de execução no servidor. Exercícios aeróbicos conhecidos omitem o termo musculação.

A chamada [search.list](https://developers.google.com/youtube/v3/docs/search/list) usa snippet, type video, até 3 resultados, relevância, português/BR, embeddable/syndicated e safeSearch moderate. Sem paginação, scraping, downloads ou armazenamento de vídeos. Retorna apenas status, exercício e ID/título/canal/thumbnail/link dos vídeos. Chave enviada no header `X-Goog-Api-Key`, evitando segredo em URL/logs conforme [orientação do Google](https://docs.cloud.google.com/docs/authentication/api-keys-best-practices).

O React só monta a busca quando o usuário abre o tutorial. Texto aparece imediatamente; vídeos têm loading e falha discreta. Inicialmente apenas thumbnails lazy, título, canal e links. Iframe `youtube-nocookie.com` é criado somente ao clicar Assistir aqui, sem autoplay, responsivo, com title e botão Fechar vídeo. Abrir no YouTube é alternativa.

## Cache e limites

Backend: TTL 24h para sucesso/resultado vazio, 60s para ausência de configuração ou falha; LRU máximo 256 nomes/grupos, normalizados por case/whitespace; no máximo 16 buscas simultâneas distintas; requests iguais compartilham a mesma tarefa. Limite conservador de 50 buscas externas por dia UTC por processo. Cache e contador reiniciam no restart; múltiplas instâncias têm contadores independentes, não constituem um limite global do Google. Configurar a quota no painel Google para proteção compartilhada.

Frontend: TanStack Query, 24h de staleTime e retenção em memória por 5min sem observadores; sem polling/refetch ao foco/retry automático. Reabrir tutorial enquanto cache existe não gera chamada adicional. Tentar buscar novamente é explícito. Cache cancelado e apagado na troca de sessão/logout. Sem migration e sem persistência em IndexedDB.

## Privacidade e testes

Google recebe apenas o exercício/grupo e parâmetros de pesquisa, sem token Sirius, IDs de usuário ou histórico. Thumbnails contatam YouTube ao aparecer; iframe só após clique. Nenhuma chamada real em CI/testes normais. `RUN_YOUTUBE_LIVE_TESTS=false` é documentado, mas nenhum teste live foi implementado ou executado.

Testes mockados cobrem normalização, caracteres inválidos, ausência de chave, timeout, 403/429/500, vazio, projeção, limite de 3, cache/expiração/coalescing/tamanho e ausência de segredo em resposta/URL. Browser smoke cobre cinco larguras, demanda/caching, iframe após clique e sessão ativa. Resultados não provam qualidade de vídeos de terceiros ou disponibilidade live da API.
