# Sirius Agent — handoff

Branch: `feat/sirius-agent`, criada da main `ce9103bd024a911a3ba5c1ae665d5f26535648ae`.

Implementação: roteador Gemini/Groq, ferramentas por usuário, propostas confirmadas transacionais, migração das chamadas antigas, credenciais mascaradas/criptografadas, conversas, memória, RAG, planejamento, sugestões, voz e configurações. Detalhes e limitações: [docs/SIRIUS_AGENT.md](docs/SIRIUS_AGENT.md), [docs/AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md).

PR: https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/19

CI validado no commit `1c12c1f`: backend/security, XP, transações Mongo e frontend/build/smoke. Confirmação concorrente do agente grava uma única despesa e auditoria; rollback e isolamento de proprietário passaram. Lint sem avisos, build com `CI=true` e smoke Chromium em 1440/390/320 px. Chamadas a provedores foram simuladas. O teste antigo de concorrência mista de XP revelou uma leitura desnecessária dentro da transação; a correção reutiliza o saldo já bloqueado, reinicializado em cada retry, e tem regressão dedicada.

Último ajuste antes de publicar: limitar a entrada da conferência independente sem truncar o JSON no meio; teste verifica tamanho, parsing e rejeição de evidência inventada. Merge e smoke de produção serão registrados após os checks desta revisão.

Configuração externa: `AI_KEY_ENCRYPTION_KEY` no Render para salvar novas chaves e migrar as antigas. Atlas Vector Search é opcional; exige índice e variável específicos. Nenhum faturamento deve ser ativado. Autoações e streaming permanecem sem implementação operacional, mesmo se suas flags reservadas forem alteradas.
