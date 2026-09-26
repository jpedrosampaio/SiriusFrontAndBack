# Sirius Agent — handoff

Branch: `feat/sirius-agent`, criada da main `ce9103bd024a911a3ba5c1ae665d5f26535648ae`.

Implementação: roteador Gemini/Groq, ferramentas por usuário, propostas confirmadas transacionais, migração das chamadas antigas, credenciais mascaradas/criptografadas, conversas, memória, RAG, planejamento, sugestões, voz e configurações. Detalhes e limitações: [docs/SIRIUS_AGENT.md](docs/SIRIUS_AGENT.md), [docs/AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md).

Validação e publicação em andamento. Não interpretar este arquivo como confirmação de deploy até o registro final de PR/SHA/checks abaixo.

Configuração externa: `AI_KEY_ENCRYPTION_KEY` no Render para salvar novas chaves e migrar as antigas. Atlas Vector Search é opcional; exige índice e variável específicos. Nenhum faturamento deve ser ativado. Autoações e streaming permanecem sem implementação operacional, mesmo se suas flags reservadas forem alteradas.
