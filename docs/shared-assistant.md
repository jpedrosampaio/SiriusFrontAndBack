# Assistente compartilhado

Chat e bot?o flutuante usam /ai/chat e /ai/conversation com conversation_id primary. Os aliases antigos continuam respondendo com o contrato de mensagens. As ?ltimas 12 mensagens antigas s?o importadas na primeira escrita; arquivo antigo preservado e consult?vel por p?ginas, sem enviar tudo ao modelo.

Contexto: no m?ximo 12 mensagens e 18.000 caracteres recentes; resumo extrativo de at? 4.000 caracteres e mensagem nova de at? 6.000. O resumo ? um recorte, n?o mem?ria perfeita. Conversas antigas completas n?o s?o apagadas. Respostas novas retidas na janela e resumo, n?o em um arquivo ilimitado. Lease Mongo por usu?rio/conversa evita concorr?ncia e request_id recupera respostas recentes sem chamar IA duas vezes. Em falha, texto permanece no campo.

Snapshot: sete consultas Mongo, tarefas em duas consultas dependentes, demais em paralelo. Finan?as usa income/expense. Contexto m?nimo de tela inclui rota e consulta, sem copiar conte?do inteiro da p?gina. M?tricas assistant_context nos logs medem o custo sem registrar conte?do. N?o h? cache de dados de outra conta.

Mudan?a deliberada: chat n?o persiste automaticamente registros detectados por palavras-chave; fornece propostas e direciona ao m?dulo para revis?o. Nenhuma muta??o oculta na conversa. Componentes antigos preservados no hist?rico s?o somente consulta.

Valida??o: 37 testes frontend; 102 regress?es Python (30 dependentes de Mongo executadas no CI), incluindo limite de contexto, rotas e isolamento/replay de conversa. N?o foram feitas chamadas reais Gemini nem altera??es de contas de produ??o.
