# Treinos e estudos

## Treinos

- Geração mensal: quatro semanas de cinco dias; corrida respeita a frequência escolhida.
- Divisões de treino: duração e frequência escolhidas, com expansão no servidor. O ciclo genérico por período usa dez semanas (dentro do intervalo de 8–12 informado pela tela).
- Respostas incompletas ou semanas inconsistentes recebem uma tentativa corretiva; se persistirem, nada é salvo nem recompensado.
- Melhorar treino usa o cliente LLM com a configuração do usuário e preserva duração e alternância de cardio/descanso.
- A seleção é independente por ficha e deriva a semana do dia selecionado. Planos antigos com nomes `semN_diaN` ou `Semana N` são reconhecidos.
- Planos antigos incompletos não recebem exercícios inventados por migração: precisam ser gerados novamente ou evoluídos.

## Editais

- Novas análises preservam pesos decimais e solicitam trechos literais que sustentem pesos e quantidades de questões. Trechos ausentes do PDF não são apresentados como fonte.
- A correspondência do trecho confirma sua presença, não certifica a interpretação da IA. Conferir tabelas e retificações continua necessário.
- Prioridades são sugestões calculadas por peso × questões quando todas as disciplinas têm quantidade disponível; caso contrário, usa-se o peso para todas. Participações são relativas às disciplinas importadas, não uma garantia de pontuação da prova.
- Dados antigos ou sem fonte aparecem como provisórios. Valores iguais de questões não são descartados. Reanalisar o PDF cria dados com o novo formato; não altera programas antigos automaticamente.
- A análise original permanece disponível para o chat e comparação após a importação do cargo.
- “Estudar” no edital verticalizado abre cronômetro com a matéria selecionada, assunto nas notas da sessão e busca contextual de aulas. Fechar a janela encerra o cronômetro local sem registrar uma sessão concluída.

## YouTube no Render

1. No Google Cloud, habilitar **YouTube Data API v3** no projeto e criar uma chave restrita a essa API.
2. No serviço do backend no Render, cadastrar `YOUTUBE_API_KEY` e aplicar o redeploy. Nunca usar variável `REACT_APP_*` para essa chave.
3. Abrir Estudos → programa importado → Edital verticalizado → Estudar este assunto. Os resultados devem mostrar título, canal e link para assistir.

Sem chave ou durante indisponibilidade/cota esgotada, a interface oferece pesquisa contextual no YouTube. Os resultados vêm da API oficial, sem URLs inventadas pela IA. Cache em memória por uma hora, limitado a 128 consultas por processo. Apenas usuários autenticados com acesso à disciplina podem consultar o endpoint.

Documentação: [YouTube search.list](https://developers.google.com/youtube/v3/docs/search/list), [chave no cabeçalho da API Google](https://docs.cloud.google.com/apis/docs/system-parameters).

## Validação

Testes isolados de geração/evolução, duração, índices inválidos, prioridades, fontes, conteúdo legado, isolamento por usuário e respostas da API YouTube. Testes de navegação em semanas no Node; build de produção e suítes MongoDB no GitHub Actions. A busca real depende da chave configurada no Render; os testes não usam dados ou credenciais de produção.
