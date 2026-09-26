# Proposta separada: remover o subsistema SQLite órfão

## Resultado da auditoria

O frontend web ativo não importa `use-database.js`, `use-notifications.js` nem os serviços `database.ts`, `data.ts`, `sync.ts` e `notifications.ts`. As únicas referências formam um conjunto isolado entre esses próprios arquivos. O `package.json` não declara os pacotes Capacitor que eles importam. O build web passa sem esses pacotes. Há um diretório Android e `capacitor.config.json`, mas isso não demonstra que sincronização offline esteja disponível no produto atual.

Foram encontrados contratos incompatíveis:

- `data.ts`, `saveHabit`: 11 colunas/valores para 12 placeholders SQL.
- `sync.ts`, `mergeRecord`/`updateRecord`: `${tableName}_id` gera `tasks_id`, enquanto o identificador real é `task_id`; o mesmo ocorre em outras tabelas.
- `syncRecord`: usa DELETE e PUT em `/api/sync/{table}/{record}`, sem equivalência com o contrato POST de sincronização do backend.
- Os hooks `.js` contêm sintaxe TypeScript, fora do grafo compilado do produto.

## Mudança proposta para aprovação neste PR

Remover os dois hooks e os quatro serviços órfãos em uma alteração específica de limpeza, junto das exclusões correspondentes do lint. Antes de remover o projeto Android, confirmar se existe distribuição nativa externa a este repositório; este PR não afirma que ela inexiste e não propõe apagar bancos nos dispositivos. As rotas de sincronização do backend precisam de verificação de consumidores externos antes de remoção.

Esta proposta não remove arquivos de implementação, não altera a PWA, o service worker nem rascunhos locais usados pelo frontend atual. Não anuncia suporte SQLite/mobile offline como funcional. Se o produto escolher retomar um cliente nativo, ele precisará de dependências explícitas, schema/migrações, contrato de sincronização com isolamento de usuário e testes de build/emulador antes da ativação.

## Verificação

Busca de importações em `frontend/src`, inspeção de `package.json`, configuração Capacitor/Gradle e contraste dos métodos HTTP com as rotas do backend. O pipeline web valida apenas o produto conectado; não foi executado build Android, pois faltam dependências e um fluxo nativo suportado definido.
