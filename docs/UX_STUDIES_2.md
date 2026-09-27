# Sirius UX 2.0 + Studies 2.0

## Escopo

Branch `feat/sirius-ux-studies-2`, baseada na main `883d790`. Evolução aditiva do Sirius Agent entregue no PR #19. O arquivo de requisitos recebido termina no título incompleto `67. IMPACT ANAL`; esta entrega usa as seções completas 1–66, sem presumir a continuação.

## Navegação e assistente

- `AppShell` mantém uma única sidebar, topbar, navegação móvel, busca, adição rápida e superfície compacta do Sirius. As rotas existentes continuam disponíveis.
- Sidebar: Hoje, Planejar, Estudos, Saúde, Finanças/Metas e Sirius. Recursos secundários permanecem acessíveis. Mobile: Hoje, Estudos, Sirius, Tarefas e Mais.
- Ctrl/Cmd+K abre ações e busca de registros do proprietário. Adição rápida reutiliza tarefa, transação, sessão e materiais; compromisso abre o Sirius com contexto, sujeito à confirmação normal do Agent.
- Planejamento diário, revisão semanal, propostas e insights saem das configurações e ficam em Hoje. Configurações mantêm credenciais, preferências, memória e fontes.
- Compacto, `/chat` e entradas contextuais usam as mesmas conversas, ferramentas, memória e seleção de documentos. Contexto fica em memória, limitado a 30 conversas, e é apagado na troca de conta. Uploads pendentes são cancelados ao sair da superfície ou trocar de conta.
- Chats legados de finanças, estudos e edital foram substituídos por entradas contextuais. Os endpoints textuais antigos delegam ao Agent; o antigo endpoint de arquivo retorna 410 e aponta para anexos do Agent.
- PDF até 8 MB/200 páginas com texto selecionável; imagem até 8 MB via provedor multimodal. Conteúdo de imagem é identificado como inferido. Arquivos brutos não são armazenados: ficam metadados e trechos indexados. Remover o anexo revoga sua recuperação.

## Estudos e dados existentes

Hoje / Preparações / Biblioteca / Desempenho são as quatro áreas principais. Cada preparação abre Visão geral / Edital / Plano / Questões / Provas / Atualizações / Desempenho. Estudar é uma ação contextual; o foco mantém timer persistente, retomada, notas, questões, aulas e Sirius.

`study_programs` continua canônico. `study_targets` acrescenta tipo (`contest`, `certification`, `academic`, `course`, `custom`), instituição, banca, edição, cargo e data. Programas antigos recebem identidade virtual na leitura, sem duplicar materiais ou fazer migração destrutiva. Criar uma preparação usa transação e chave de idempotência.

Visão geral separa cobertura marcada e domínio estimado, mostra questões, acertos, minutos reais, data/meta, próximo bloco e menor domínio com amostra. Edital verticalizado mantém fontes e pesos, busca por conteúdo e filtro de progresso. Marcação manual de domínio aparece como confiança pessoal.

## Evidências, erros e revisões

`study_attempts` registra resposta individual, matéria/tópico, programa, pergunta, resposta, acerto, tempo, origem e metadados opcionais de banca/prova/cargo/dificuldade. A ligação ao target é pelo programa canônico. Tentativa, agregado de questões, contadores da matéria e revisão são salvos na mesma transação. Reenvio com a mesma chave não duplica contadores.

`sirius-mastery-1` usa respostas booleanas, decaimento exponencial de 60 dias e prior Beta(2,2). Sem respostas o resultado é desconhecido, nunca 0% ou 100%. Exibe amostra, confiança e intervalo aproximado; não é uma previsão de aprovação. Checkboxes de exposição não aumentam arbitrariamente a nota. Evidências agregadas antigas permanecem nos totais, mas não são convertidas em respostas individuais fictícias.

Banco de erros permite classificar a causa, revisar o assunto e refazer questões. Desempenho exibe causas, evolução diária de acertos e estimativas por tópico. A fila combina assuntos vencidos, flashcards e perguntas cuja última resposta conhecida foi incorreta; uma nova tentativa atualiza a evidência. Revisões de tópicos usam intervalos determinísticos de 1/7/14–45 dias conforme erros, amostra e dificuldade. Flashcards preservam o algoritmo existente. FSRS não foi introduzido.

## Planejamento e simulados

- Sugestões por tópico explicam pesos registrados, incidência, domínio, erros, revisão vencida, conteúdo pendente e proximidade da prova.
- Recalcular exige ação do usuário. A distribuição adaptativa prefere evidência recente quando há amostra suficiente, preservando o peso original armazenado.
- Blocos concluídos, passados, manuais e fixos são mantidos; somente o futuro apropriado é reconstruído. Compromissos da agenda consomem a capacidade diária tanto na geração quanto na remarcação. O planejador distribui minutos por dia, sem inventar horários livres exatos.
- Simulado por assunto resolve o tópico no conteúdo pertencente ao usuário e vincula as respostas ao domínio. Questões geradas são inferidas, não oficiais; quantidade divergente da solicitada é rejeitada antes da gravação.
- Blueprint reproduz quantidades e pesos registrados por disciplina usando questões existentes com gabarito na preparação. Se faltam distribuição ou questões, explica a insuficiência em vez de completar silenciosamente. A duração é informada pelo usuário e identificada assim.
- Correção considera todas as questões no denominador, incluindo brancos, e aplica pesos. Exibe nota ponderada, acerto geral, duração, disciplina/tópico, diferença da tentativa anterior e quantidade de respostas vinculadas ao domínio. Evidência, XP e resultado são transacionais/idempotentes. Questões antigas sem vínculo estável não recebem associação inventada.

## Biblioteca

Centraliza notas, rascunhos de sessão, flashcards, links registrados, editais e anexos indexados, com busca textual e filtros de preparação, matéria, assunto e tipo. O conteúdo integral continua nas telas de origem; a biblioteca mostra prévias. Aulas por assunto na biblioteca e na sessão usam a integração YouTube existente e continuam identificadas como fontes externas. Sem chave configurada, há pesquisa contextual por link; nenhum resultado é apresentado como oficial.

## Fontes de concursos

`ContestSourceProvider` normaliza metadados, documentos, atualizações, provas, resultados e polling. `GenericOfficialConnector`, `FGVConnector` e `CebraspeConnector` usam extração de links públicos; não há regra de domínio específica para um concurso. Não executam JavaScript nem descobrem automaticamente todo o catálogo de uma banca.

O usuário cadastra uma página ou PDF público HTTPS e confirma que os termos permitem acompanhamento. O watcher verifica robots, recusa bloqueios/CAPTCHA, não usa login/cookies e não contorna restrições. DNS público é validado e a conexão TLS é fixada no IP validado. Redirecionamentos exigem cadastrar a URL final. Limites: 2 MB por resposta, 200 páginas por PDF, cinco fontes por preparação, seis horas por fonte, limite por domínio, ETag/Last-Modified e backoff persistente.

Confiança: domínio governamental/judiciário/legislativo ou banca reconhecida recebe `OFFICIAL`; outros links permanecem `USER_PROVIDED`. Não se afirma oficialidade apenas porque o usuário colou uma URL. O esquema comporta `SECONDARY` para futuros provedores verificados.

Linha do tempo separa detecção de publicação (não confirmada se ausente). Hash do texto detecta mudanças na página; hash URL+título deduplica links descobertos; PDF cadastrado diretamente usa hash dos bytes e detecta substituição na mesma URL. Links de PDFs não são baixados recursivamente: para acompanhar alterações internas de um arquivo, cadastre também sua URL. PDFs sem texto ainda têm hash, mas não comparação textual. Diferenças mostram adições/remoções, com limite explícito; comparação estruturada de duas análises de edital existente foi preservada. Nenhuma alteração externa modifica automaticamente a preparação.

Referências do desenho: [robots RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html), [FGV Conhecimento](https://conhecimento.fgv.br/concursos), [Cebraspe](https://www.cebraspe.org.br/o-que-fazemos/concurso/).

## Operação e validação

Novas coleções e índices são criados no startup; não há descarte ou reescrita em massa de dados existentes. MongoDB Atlas oferece as transações necessárias. Credenciais Gemini/Groq e `AI_KEY_ENCRYPTION_KEY` seguem a configuração da entrega anterior. O watcher não exige nova chave nem serviço pago.

Recompensas independentes de XP usam transações em replica sets para não disputar atualizações CAS externas com transações abertas de tarefas/hábitos. O modo standalone mantém CAS. A correção foi validada com o cenário real de escritores mistos e não reduz os testes de concorrência. Referência: [conflitos e transações MongoDB](https://www.mongodb.com/docs/manual/core/transactions-production-consideration/).

Testes cobrem domínio/amostras, revisões, capacidade, preservação de blocos, contagem/pesos, vínculo de questões e isolamento, URLs/robots/DNS/hash, replay concorrente com Mongo replica set e interfaces em 1440/1024/768/390/320 px. Provedores são simulados; sem chamadas pagas ou gravações em contas reais. Resultados finais de CI/deploy são registrados no HANDOFF.

Limites conhecidos: janela de 5.000 respostas no painel/recomendações, 500 por revisão individual, filas e bibliotecas paginadas por limites internos; não há catálogo universal de provas nem garantia de extração de sites dinâmicos. A revisão visual preserva interfaces especializadas existentes; não reescreve todos os formulários do produto. A continuação a partir da seção 67 ainda precisa ser fornecida para definir seu escopo.
