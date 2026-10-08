# Migrations de produção pelo GitHub Actions

O Alembic deixa de ser executado no computador do mantenedor. A aplicação no Neon passa a ser uma ação manual no GitHub, com código aprovado, revisão atual conferida e execução serial. Instalar este workflow não executa nenhuma migration. O PR #30 permanece aberto até aplicar e verificar `a81c9d37e502`.

## Configuração inicial — apenas no GitHub

1. Abra **Settings → Environments → New environment**, no repositório `jpedrosampaio/SiriusFrontAndBack`. Nome exato: **production-migrations**.
2. Em **Deployment branches and tags**, escolha **Selected branches and tags** e adicione somente a **branch `main`**. Não autorize tags, `*`, branches de features ou refs de PR. Essa restrição é obrigatória: impede que outro workflow em uma branch receba o secret. Se essa opção não estiver disponível no plano/repositório, não configure o secret nem execute a migration; não é necessário contratar serviço nesta etapa.
3. Em **Environment secrets → Add secret**, salve **DATABASE_URL_DIRECT** com a conexão **direta** do Neon, usando TLS (`sslmode=require` ou `verify-full`). Não use o hostname `-pooler`. Não coloque a URL em repository secrets, variables, arquivos ou comentários. Não envie a credencial pelo chat.
4. Se **Required reviewers** estiver disponível, adicione um mantenedor para aprovar cada execução e desative bypass administrativo quando possível. **Prevent self-review** exige outro revisor disponível; não o habilite se houver somente um mantenedor que dispara e aprova o job. A segurança básica não depende desse recurso: depende da restrição externa à branch `main` e do registro imutável de aprovação.
5. Confirme que o Environment, a restrição a `main` e o secret foram configurados. **Não disparar produção antes dessa confirmação do proprietário.**

Documentação oficial das [regras de Environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments) e da [proteção de deployments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments). A disponibilidade de revisores obrigatórios depende do plano e da visibilidade; este projeto não requer contratar um plano.

## Aplicar a migration do PR #30

Após confirmar a configuração acima:

1. Abra **Actions → Production migrations → Run workflow**.
2. Em **Use workflow from**, selecione **main**. Em **pr_number**, informe **30**. Não há campo para branch, SHA, SQL ou URL arbitrários.
3. O preflight, sem acesso ao banco, confere a aprovação publicada na `main`, o SHA exato, a revisão Codex limpa, a ausência de changes requested e os três workflows originais de CI completos no mesmo SHA. A última execução deve passar: sucesso antigo não esconde falha ou execução ainda em andamento.
4. Se houver aprovação de Environment, examine PR/SHA/revisões nos logs do preflight e aprove o job. O gate é repetido depois dessa espera, antes de liberar a etapa com a conexão.
5. O executor obtém o lock, verifica **b73a16ce9024**, aplica exclusivamente **a81c9d37e502** e verifica o resultado. Se já estiver exatamente em `a81c9d37e502`, retorna **already_applied** sem reexecutar DDL. Qualquer outra revisão, banco sem versão ou múltiplos heads interrompem a execução.
6. Aguarde o resultado **applied** ou **already_applied**. Só então concluir o merge do PR #30 com o SHA aprovado, aguardar Vercel/Northflank e verificar `/health/live`, `/health/ready` e frontend. O workflow não faz merge, deploy ou downgrade automaticamente.

SHA aprovado do PR #30: `c8659194c40571b2450ec40704bd12fe4f2c0797`. Parent: `b73a16ce9024`. Hash SHA-256 da migration: `1922856f70973908dbdc1a37c44908da1b3c811a9bd444fd69279cc105fcc519`. Se a PR receber outro commit, o gate recusará execução até nova revisão e nova aprovação.

## Como aprovar próximas migrations

O registro `.github/production-migrations.json` é a autorização explícita de código na `main`, não um secret. Após terminar o CI e obter revisão limpa no SHA final de uma PR, uma PR separada de configuração deve adicionar sua entrada ao registro: número, SHA de 40 caracteres, revision, down_revision, caminho, hash SHA-256 dos bytes do blob Git e ID do comentário Codex de revisão limpa. Essa atualização também deve passar por CI/revisão antes de entrar na `main`. Não basta um label, nome de branch ou comentário livre para executar código no Neon.

A entrada do PR #30 é pré-cadastrada nesta instalação com o SHA já revisado. Isso autoriza apenas esses bytes quando houver dispatch e acesso ao Environment; não dispara produção e não substitui a confirmação solicitada ao proprietário.

Cada execução aceita uma única migration linear nova, cujo parent seja o head da `main`. Migrations históricas e os três workflows usados como gate devem continuar byte a byte iguais à `main`. Mudanças legítimas nesses workflows devem ser integradas primeiro por uma PR de configuração separada. Migrations devem ser autocontidas em Alembic/SQLAlchemy: o executor não carrega `env.py`, models, requirements, hooks ou outros arquivos da aplicação candidata. Branches de Alembic, merges de revisão, mudanças históricas e dependências de helpers de PR não são executadas por este fluxo.

## Proteções e comportamento em falha

- Somente `workflow_dispatch` de `main`; sem `pull_request_target`, execução automática, downgrade ou URL de banco como input. Actions fixadas por SHA e permissões somente de leitura. O token nativo do GitHub é usado em etapas sem banco para consultar/fazer fetch; nenhum PAT ou outro secret customizado é necessário.
- O único secret customizado referenciado é `DATABASE_URL_DIRECT`, apenas na etapa final do job com Environment. Checkout não persiste token; fetch usa autenticação efêmera. Nenhum código da aplicação candidata nem suas dependências são instalados. Apenas o blob da migration aprovada é executado pelo Alembic confiável da `main`.
- Grupo de concurrency único com `cancel-in-progress: false` e lock de sessão PostgreSQL `731030001`. Uma segunda execução do executor não modifica o banco enquanto o lock estiver ocupado. Operadores externos precisam respeitar esse mesmo lock; ele não impede SQL manual de alguém com credenciais.
- Parent conferido sob o lock. DDL e versão dentro da mesma transação; `lock_timeout=10s`, `statement_timeout=120s`, conexão com timeout e job de 10 minutos. Falhas transacionais revertem DDL e versão. Migrations com operações não transacionais/autocommit não são suportadas; exigem outro procedimento revisado, nunca bypass do gate.
- Credencial não é impressa; parâmetros SQL ficam ocultos e exceções de serviços não são incluídas nos logs. Logs mostram apenas PR, SHA, revisões, status e mensagens controladas. Não habilitar debug/trace de shell ou SQL.
- Se a `main` mudar enquanto o workflow espera aprovação, iniciar um novo dispatch da `main` atual. Se o resultado for incerto, repetir com o mesmo PR é seguro: a revisão final já aplicada vira no-op.
- Readiness exige a revisão de schema do código publicado. Entre aplicar a migration e publicar o PR correspondente, `/health/ready` pode retornar 503; coordenar execução e merge/deploy na mesma janela.

## Testes sem Neon

`Production migration safety tests` roda em PostgreSQL 17 descartável e usa URL sintética de loopback, sem Environment ou secrets de produção. Verifica PR/SHA/revisão/checks falsos, alterações de migrations/workflows, leitura AST sem executar código, lock ocupado, versão divergente, retry, rollback e o blob real do PR #30 com preservação de histórico protegido e FK por proprietário. O fixture em `tests/fixtures` não é uma nova migration da aplicação. O head da `main` permanece `b73a16ce9024` nesta PR de configuração.
