# Neon Free — configuração de produção

Documentação oficial consultada em 2026-09-30/2026-10-01. Não foi criado projeto, habilitado billing ou contratado recurso.

Estado verificado em 2026-10-07: PR21 e PR22 incorporadas à main; backend Northflank e frontend Vercel publicados. `/health/live` e `/health/ready` retornam HTTP200, confirmando conexão e revisão do schema. Schema até `126b856daebb`, 96 tabelas, runtime PostgreSQL e zero chamadas/imports Mongo. As credenciais de produção não foram acessadas; o usuário corrigiu DATABASE_URL no painel. Nenhuma migration nova é necessária na fase Stability/Performance2.

## Limites consultados

O [plano Free atual](https://neon.com/docs/introduction/plans) informa 100 projetos, 10 branches por projeto, 0,5 GB de armazenamento por projeto, 100 CU-horas por projeto/mês, até 2 CU e 5 GB de transferência pública por projeto. Scale-to-zero após cinco minutos de inatividade, sem opção de desabilitar no Free. Esses limites podem mudar; conferir o painel antes do cutover. Não selecionar Launch/Scale para contornar limites.

[Pooling](https://neon.com/docs/connect/connection-pooling) usa PgBouncer em modo transaction. A capacidade de clientes pooled não corresponde ao número de queries simultâneas que um compute pequeno suporta. O Sirius mantém apenas três conexões locais por processo no máximo. Não usar sessões SQL persistentes, temporary tables entre transações ou locks de sessão.

[pgvector](https://neon.com/docs/extensions/pgvector) é uma extensão suportada. Não exige índice HNSW: começar com busca exata, filtro de proprietário e limites de tamanho. Vetores e índices consomem os mesmos 0,5 GB disponíveis. A implementação vetorial ainda está pendente nesta branch.

## Passos externos

1. Criar projeto **Free** no Neon, na região apropriada para o Northflank. Manter limites gratuitos e scale-to-zero.
2. Em Connect, copiar conexão pooled para `DATABASE_URL` no Northflank e direct para `DATABASE_URL_DIRECT`. Guardar somente nas variáveis secretas, nunca no Git ou chat. Preservar `sslmode=require` ou mais forte.
3. Antes de trocar produção, executar `python -m alembic upgrade head` com a conexão direct em ambiente administrativo. Não executar migrations em cada boot/request.
4. Somente após migrations, CI e todos os domínios estarem prontos, fazer o cutover. Sem DATABASE_URL, manter a versão publicada atual e a PR aberta.
5. Validar readiness, cadastro novo, login, criação de registros e Agent. Não importar dados Mongo. Sessões antigas são inválidas.
6. Remover variáveis Mongo quando o runtime PostgreSQL estiver ativo. O usuário excluirá manualmente o Atlas após confirmar Neon.

Workers podem impedir scale-to-zero. Automações agora aguardam pelo menos 900 s quando ociosas; concursos consultam a cada 900 s; a fila de PDF não inicia sem storage. Configurar a sondagem frequente do host em `/health/live`, que não acessa SQL. `/health/ready` e startup verificam a revisão Alembic. Consumo real no Neon ainda precisa ser observado após o cutover.

## Arquivos

PostgreSQL guarda metadata, hashes e referências. Não há object storage configurado nesta execução. O futuro adaptador deve verificar autenticação/propriedade antes de disponibilizar objetos e funcionar sem plano pago obrigatório. Disco efêmero do Northflank não será tratado como armazenamento durável.

A fila de editais retorna 503 sem storage configurado; não aceita uploads que desapareceriam no restart. `LOCAL_DEVELOPMENT_STORAGE_DIR` é exclusivo para testes/desenvolvimento e recusado em Northflank/produção. A análise direta extrai conteúdo em memória e salva somente análise/texto no SQL, sem prometer retenção do PDF original.
