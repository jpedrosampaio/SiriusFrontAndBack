# Sirius Agent

> Registro histórico da implementação original do Agent. Mongo/Atlas, Render e partes do planejamento foram substituídos; não use estes detalhes como estado atual. Consulte [HANDOFF](../HANDOFF.md), [Life State/Global Planner](LIFE_STATE_GLOBAL_PLANNER.md) e o [mapa de contexto](DEVELOPMENT_CONTEXT.md); os fluxos antigos abaixo são preservados como referência.

O assistente flutuante e `/chat` usam o mesmo histórico no MongoDB e a mesma seleção de conversa na aba do navegador. `/assistant/settings` reúne provedores, memórias, perfil, sugestões, fontes, plano diário, revisão semanal e ações pendentes.

## Fluxos disponíveis

- Consulte tarefas, hábitos, finanças, orçamento, cadernos, revisões, treino, nutrição, agenda e metas. O contexto usa dados da conta autenticada e referências de página validadas no servidor.
- Peça criação de tarefa, registro de despesa, registro de estudo em caderno existente ou compromisso fixo. O assistente mostra argumentos, motivo e validade de 20 minutos. Confirme ou cancele cada proposta. Confirmação repetida não duplica o registro.
- Sem provedor, consultas continuam funcionando. Um interpretador restrito reconhece valores/durações explícitos em pedidos simples; por exemplo, `Registre um gasto de R$ 48 com alimentação e 50 minutos de estudo de Direito Constitucional` produz duas propostas se esse caderno existir sem ambiguidade.
- O plano diário é uma prévia determinística: prioridade, prazo, capacidade e intervalos ocupados. Duração não cadastrada usa estimativa visível de 30 minutos. Não remarca tarefas automaticamente. A revisão semanal compara os mesmos dias da semana anterior e oferece até cinco ajustes baseados em métricas.
- Memórias são explícitas: preferência, regra pessoal, objetivo ou contexto. Remover apaga o conteúdo e mantém apenas a impressão digital para impedir reintrodução idêntica. Não há captura automática de informações sensíveis.
- Editais novos são indexados por página. Fontes antigas e anotações podem ser incluídas/reindexadas nas configurações. Respostas apresentam referências recuperadas. Estado financeiro e tarefas nunca dependem do RAG.
- Microfone grava até 60 segundos/8 MB. A transcrição fica no campo para revisão, sem envio automático. Ouvir/parar resposta usa a síntese disponível no navegador; a rota TTS antiga passa pelo roteador e pode sinalizar fallback local.

## Segurança e configuração

Novas chaves exigem `AI_KEY_ENCRYPTION_KEY` (Fernet) no servidor. Gere uma chave uma única vez com `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`, guarde backup seguro e configure no Render. Nunca inclua o valor no Git. Trocar/perder essa variável exige recuperar a anterior ou cadastrar novamente as credenciais. Chaves antigas continuam legíveis e são migradas por comparação e atualização atômica quando a variável está presente. GET de perfil/status nunca devolve chaves completas.

O catálogo usa modelos com faixa gratuita, sem ativar faturamento. Uma conta com faturamento habilitado no provedor pode ter regras de cobrança próprias; o aplicativo não consegue comprovar o plano a partir da chave. Modelos e fontes oficiais: [AI_MODELS.md](AI_MODELS.md).

| Variável | Padrão | Efeito |
|---|---|---|
| `AI_AGENT_ENABLED` | true | Conversa operacional e confirmação |
| `AI_RAG_ENABLED` | true | Recuperação documental |
| `AI_VOICE_ENABLED` | true | Transcrição e TTS remoto |
| `AI_AUTOMATIONS_ENABLED` | true | Worker de sugestões |
| `AUTOMATION_DRY_RUN` | true | Sugestões marcadas como simulação |
| `AI_AUTO_ACTIONS_ENABLED` | false | Reservada; escritas automáticas não implementadas |
| `AI_STREAMING_ENABLED` | false | Reservada; resposta atual não usa SSE |
| `AI_PAID_MODELS_ENABLED` | false | Não inclui nenhum modelo pago adicional |
| `AI_INTERNAL_DAILY_LIMIT` | 200 | Limite interno por usuário/dia UTC, incluindo tentativas |
| `AI_ATLAS_VECTOR_INDEX` | vazio | Ativa embeddings e busca vetorial quando o índice existe |
| `RUN_AI_LIVE_TESTS` | false | Testes não chamam provedores reais |

## Limites explícitos desta entrega

- Conservador, equilibrado e proativo oferecem sugestões; **todos exigem confirmação para escrever**. Não há exclusões, pagamentos, remarcação autônoma, execução de código ou ferramentas arbitrárias. Flags de autoação/streaming são reservadas e `/ai/status` informa a capacidade efetiva.
- Conversas retêm as últimas 200 mensagens textuais por conversa e um contexto resumido/recente menor. O endpoint de histórico tem paginação; a interface mostra o trecho recente e conserva o arquivo legado separado. Não há promessa de retenção ilimitada.
- O planejador atual distribui tarefas e preserva compromissos fixos cadastrados pelo assistente. Não cria uma agenda global completa de refeições, treinos e estudos automaticamente. Datas e capacidade continuam sob controle do usuário.
- Eventos de criação/conclusão de tarefas, estudo, treino, despesa, compromisso e edital alimentam a infraestrutura. Regras iniciais cobrem orçamento, estudo e plano diário, por adesão do usuário, com silêncio, teto diário e deduplicação. Não há varredura periódica completa de atrasos de todos os módulos nem notificações externas.
- Verificação de edital usa Groq independentemente da extração Gemini quando há chave disponível. É uma revisão parcial, com trechos literais conferidos no PDF; não certifica todos os cargos, salários ou páginas. Validação determinística e edição humana permanecem.
- Busca cobre editais e anotações/cadernos explicitamente indexados. Atualizações de notas exigem reindexação; documentos arbitrários e comentários de outros módulos ainda não têm ingestão automática. Atlas indisponível/quota esgotada recuam para busca lexical, identificada na resposta.
- Cancelamento interrompe a tarefa no processo que atende a conversa. Com múltiplas réplicas, o cancelamento deve ser encaminhado à mesma instância; desconectar o navegador não desfaz propostas já persistidas, que continuam sem execução até confirmação.
- Mudanças de estado críticas exigem MongoDB replica set/Atlas. Não há fallback que permita escrita financeira parcial em Mongo standalone.
