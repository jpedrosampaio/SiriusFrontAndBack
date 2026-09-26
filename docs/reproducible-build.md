# Build reproduz?vel e CI

Manifesto e lock agora usam o mesmo mapa de depend?ncias. npm ci foi executado com sucesso. Mantidos React 18.3.1 e Router 6; ESLint 8.57.1 escolhido por compatibilidade com CRA 5, sem migra??o major do runtime. Depend?ncias transitivas antigas de CRA continuam gerando avisos de deprecia??o na instala??o; n?o foram ocultadas nem resolvidas por uma migra??o arquitetural fora de escopo.

CI executa npm ci, lint com max-warnings 0, testes frontend, build com CI=true e smoke de navegador em 1440/390/320 px. Playwright intercepta APIs com fixtures, n?o acessa contas nem IA reais. Fluxos: Dashboard/assistente, an?lise e verticalizado, Pomodoro/rascunho, sess?o de treino com s?rie recuperada ap?s reload. Capturas s?o artefatos do CI.

Lint cobre src js/jsx, inclusive regras de hooks. Imports/estados/fun??es sem consumidores foram retirados. Dois hooks nativos n?o alcan??veis (use-database.js e use-notifications.js) t?m sintaxe TypeScript em .js e est?o explicitamente fora do lint web; subsistema nativo ser? tratado em proposta separada, sem remo??o silenciosa. N?o h? import deles a partir de index/App/p?ginas.

Refer?ncia npm ci: https://docs.npmjs.com/cli/v11/commands/npm-ci/
