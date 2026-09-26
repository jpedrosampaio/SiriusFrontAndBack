# Build reproduzível e CI

Manifesto e lock agora usam o mesmo mapa de dependências. npm ci foi executado com sucesso. Mantidos React 18.3.1 e Router 6; ESLint 8.57.1 escolhido por compatibilidade com CRA 5, sem migração major do runtime. Dependências transitivas antigas de CRA continuam gerando avisos de depreciação na instalação; não foram ocultadas nem resolvidas por uma migração arquitetural fora de escopo.

CI executa npm ci, lint com max-warnings 0, testes frontend, build com CI=true e smoke de navegador em 1440/390/320 px. Playwright intercepta APIs com fixtures, não acessa contas nem IA reais. Fluxos: Dashboard/assistente, análise e verticalizado, Pomodoro/rascunho, sessão de treino com série recuperada após reload. Capturas são artefatos do CI.

Lint cobre src js/jsx, inclusive regras de hooks. Imports/estados/funções sem consumidores foram retirados. Dois hooks nativos não alcançáveis (use-database.js e use-notifications.js) têm sintaxe TypeScript em .js e estão explicitamente fora do lint web; subsistema nativo será tratado em proposta separada, sem remoção silenciosa. Não há import deles a partir de index/App/páginas.

Referência npm ci: https://docs.npmjs.com/cli/v11/commands/npm-ci/
