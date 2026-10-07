# PostgreSQL — runtime da branch feat/postgres-neon

PR #21, base `e2b1bfd60c225d22329b9a28ac0daf3b4e8ee702`. O runtime agora funciona exclusivamente com PostgreSQL. O inventário passou de 669 chamadas Mongo diretas para zero, incluindo os acessos dinâmicos de sincronização móvel. Motor, PyMongo, GridFS, criação de collections/índices no startup e o snapshot legado server_partial.py foram removidos. Não há dual-write, emulação de collections ou importação de dados antigos.

Isso descreve o código da branch, não uma troca já realizada em produção. O merge e a publicação dependem da configuração e das migrations no Neon/Render. Sem essa verificação, a versão publicada permanece intacta.

## Persistência e transações

- SQLAlchemy 2 Async, psycopg, Alembic; 96 tabelas de domínio, head `126b856daebb`.
- Alembic é a autoridade do schema. Startup consulta a revisão existente e falha claramente se o banco estiver ausente ou desatualizado; nunca executa DDL ou migrations.
- Engine lazy por processo, pool 2 + overflow 1, timeout 15 s, reciclagem 240 s, pre-ping e prepare_threshold=None. URLs Neon exigem TLS. SQL e parâmetros não são impressos.
- Serviços controlam unit_of_work; repositories recebem a sessão e fazem flush, nunca commit. Uma sessão não é compartilhada entre tarefas concorrentes.
- Escritas de atividade bloqueiam o usuário com FOR UPDATE. Dados, delta efetivo de XP, eventos e recibo pertencem à mesma transação. Replay não repete a alteração. IA e chamadas externas ficam fora da transação.
- UUID nativo, FKs compostas por proprietário, timestamptz, dias civis date, dinheiro NUMERIC/Decimal. Exclusões lógicas preservam evidências quando necessário.
- JSONB guarda apenas estruturas variáveis: preferências, evidências, análises, parâmetros/resultados de IA. Mensagens, revisões, tentativas, itens e métricas são relacionais; não há tabela genérica de documentos.
- Senhas bcrypt, tokens de sessão SHA-256, credenciais de IA cifradas e códigos temporários do Telegram armazenados como hash. Ownership é conferido na leitura, na escrita e nas FKs.

## Domínios conectados

Autenticação/perfil, tarefas/hábitos/calendário, finanças, metas, estudos, treinos, nutrição, relatórios, dashboard/analytics, busca, Agent, notificações, concursos e Telegram usam SQL. Os testes exercitam as rotas reais, além dos serviços de domínio.

Estudos preservam áreas/programas/cadernos/tópicos, notas, sessões, tentativas, revisões, simulados/quizzes/flashcards, planos, verticalização, análises de edital e materiais. Importações e correções gravam evidências, XP e recibo atomicamente. Archive oculta o recurso sem apagar fatos históricos.

Treinos preservam plano/dias/exercícios e snapshots relacionais de sessões/séries. Logs manuais e sessões são origens mutuamente exclusivas para séries executadas. Conclusões e resets não duplicam XP. Nutrição normaliza refeições/itens, planos e compras; totais declarados em importações ficam separados dos totais calculados dos alimentos.

Dashboard e relatórios agregam fatos SQL, sem depender de limites de listagens. Snapshots de relatórios têm métricas tipadas. Não foi inferido ganho de latência a partir do tempo de execução dos testes.

Agent usa conversas/mensagens ordenadas, recibos, lease contra escritores atrasados, memórias, ações/auditoria, preferências, cotas, eventos e sugestões. Propostas confirmadas revalidam dono/política/versão antes de executar. O alias /chat/send compartilha esse fluxo. A antiga rota /chat/analyze-image, sem consumidor atual e que gravava despesas automaticamente, responde 410 indicando attachments/chat com confirmação.

Notificações reivindicam a ocorrência por data local dentro da transação; abas concorrentes não duplicam o aviso. Lembretes de cronograma são únicos por bloco/tipo. Telegram aceita mensagens privadas autenticadas pelo segredo do webhook, usa códigos descartáveis, leases e recibos; transações financeiras e resposta são concluídas juntas, com validação Decimal do lote inteiro. Reenvios não duplicam dinheiro e desvinculação durante a IA revoga a escrita.

Sincronização nativa tem contratos explícitos para tarefas, hábitos, metas e transações. O cliente gera UUID e envia todas as operações ao endpoint POST. Arrays SQLite são convertidos na fronteira; registros antigos com IDs prefixados não são migrados para o banco novo.

## Arquivos e RAG

Arquivos binários não ficam no PostgreSQL nem em disco efêmero de produção. A fila de editais e os uploads que exigem retenção devolvem 503 se não existir storage durável. LOCAL_DEVELOPMENT_STORAGE_DIR é opt-in local e recusado no Render/produção. Exportações e arquivos temporários de IA têm limpeza garantida.

Attachments do Agent retêm somente texto extraído e metadata (original_available=false, retention=extracted_text_only). Isso permite consulta sem prometer download do original. RAG usa chunks SQL, índice lexical GIN e filtro de dono/recurso ativo. pgvector/embeddings e busca semântica não estão ativos; não são exigidos para inicializar.

## Operação e validação

/health/live não consulta o banco; /health/ready verifica conectividade e revisão Alembic. Use liveness para sondagens frequentes do host. Readiness manual e startup identificam configuração/schema incompleto sem expor URLs ou senhas.

Automações ociosas consultam a fila a cada 900 s ou mais, acompanhando o intervalo de concursos; sugestões podem levar até 15 minutos. A fila de PDFs não inicia sem storage. Workers opcionais e tráfego real ainda podem consumir compute; não há garantia de consumo gratuito nem benchmark de produção.

Validação local: 179 testes PostgreSQL passaram; smoke adicional usa banco vazio e processo novo, remove MONGO_URL/DB_NAME, bloqueia imports Mongo e proíbe DDL no startup. Exercita signup/login, dashboard vazio, tarefas, dinheiro, estudos, treino, nutrição, chat, confirmação de ação e relatório. Provedores de IA são substituídos no smoke; não é uma validação de qualidade ou disponibilidade do provedor. Regressões de backend/navegador e build de produção do frontend também foram executados. Resultados finais do CI constam no PR.

Execução local: iniciar compose.postgres.yml, configurar DATABASE_URL, rodar python -m alembic upgrade head e python -m alembic check em backend. No Windows, psycopg async requer SelectorEventLoop; os testes configuram essa política. O runtime de destino é Render/Linux.

Produção: seguir [NEON_SETUP.md](NEON_SETUP.md). Nenhum dado/sessão Mongo será importado, e o Atlas não foi excluído.
