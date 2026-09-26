# Assistente compartilhado

Chat e botão flutuante usam /ai/chat e /ai/conversation com conversation_id primary. Os aliases antigos continuam respondendo com o contrato de mensagens. As últimas 12 mensagens antigas são importadas na primeira escrita; arquivo antigo preservado e consultável por páginas, sem enviar tudo ao modelo.

Contexto: no máximo 12 mensagens e 18.000 caracteres recentes; resumo extrativo de até 4.000 caracteres e mensagem nova de até 6.000. O resumo ? um recorte, não memória perfeita. Conversas antigas completas não são apagadas. Respostas novas retidas na janela e resumo, não em um arquivo ilimitado. Lease Mongo por usuário/conversa evita concorrência e request_id recupera respostas recentes sem chamar IA duas vezes. Em falha, texto permanece no campo.

Snapshot: sete consultas Mongo, tarefas em duas consultas dependentes, demais em paralelo. Finanças usa income/expense. Contexto mínimo de tela inclui rota e consulta, sem copiar conteúdo inteiro da página. Métricas assistant_context nos logs medem o custo sem registrar conteúdo. Não há cache de dados de outra conta.

Mudança deliberada: chat não persiste automaticamente registros detectados por palavras-chave; fornece propostas e direciona ao módulo para revisão. Nenhuma mutação oculta na conversa. Componentes antigos preservados no histórico são somente consulta.

Validação: 37 testes frontend; 102 regressões Python (30 dependentes de Mongo executadas no CI), incluindo limite de contexto, rotas e isolamento/replay de conversa. Não foram feitas chamadas reais Gemini nem alterações de contas de produção.
