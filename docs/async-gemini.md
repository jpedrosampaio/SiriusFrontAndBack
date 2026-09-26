# Serviço assíncrono Gemini

As rotas que referenciavam `gemini_client = None` passam a usar a chave do usuário e o mesmo transporte HTTP assíncrono das análises de edital. Não há cliente SDK paralelo. Texto, structured output, imagens e arquivos usam `gemini_service.py`, com pool `httpx.AsyncClient` fechado no shutdown.

Preservados fallback de modelos, retry de schema rejeitado, classificação de quota/chave inválida/timeout/truncamento e contagem de uso. Upload não libera URI enquanto o arquivo não estiver ACTIVE. O adaptador dos endpoints antigos mantém o acesso `response.text`, sem bloquear o event loop. A ausência de chave permanece um erro explícito, não um cliente global permanentemente indisponível.

Não há chamadas reais de IA nos testes. Regressões verificam multipart, imagem/JSON, timeout, quota, yield do event loop, uso por usuário e ausência de SDK morto. As rotas mantêm suas validações e contratos de domínio; a extração é incremental, sem reescrever o servidor inteiro.

Referências oficiais do contrato REST: [generateContent](https://ai.google.dev/api/generate-content) e [Files](https://ai.google.dev/api/files).
