PROJETO: Sirius
REPOSITÓRIO: jpedrosampaio/SiriusFrontAndBack

PROGRAMA:
Sirius Personal Operating System 3.0

MISSÃO:
Transformar o Sirius em um assistente pessoal completo, inteligente,
proativo e integrado, mantendo e evoluindo TODAS as áreas existentes:

- preparação para concursos;
- estudos;
- tarefas;
- calendário;
- hábitos;
- metas;
- financeiro;
- treinos;
- alimentação/nutrição;
- relatórios;
- automações;
- Telegram;
- Sirius Agent;
- memória;
- busca;
- RAG;
- notificações.

A preparação para concursos será inicialmente o vertical mais sofisticado,
mas NÃO deve transformar o Sirius em um aplicativo exclusivamente de
concursos.

O objetivo final é:

Sirius = Personal Operating System

com vários motores especializados compartilhando:

- contexto;
- calendário;
- prioridades;
- eventos;
- memória;
- Agent;
- planejamento;
- automações;
- busca;
- auditoria.

======================================================================
0. ESTADO ATUAL
======================================================================

Antes de alterar qualquer arquivo:

1. atualizar localmente a main;
2. ler HANDOFF e documentação atual;
3. inspecionar models, repositories, routes, Agent, frontend e testes;
4. NÃO assumir que prompts antigos representam o código atual.

Estado confirmado antes deste programa:

main contém PRs:

#19 Sirius Agent
#20 Sirius UX / Studies 2.0
#21 PostgreSQL / Neon
#22 Northflank runtime
#23 Stability / Performance 2.0 / YouTube Workout
#24 Task scheduling / planner / briefing / races
#25 Workout Session UX 2.0

Arquitetura:

React
Vercel
   ↓
FastAPI
Northflank
   ↓
PostgreSQL
Neon

Runtime normal:
PostgreSQL somente.

Não reintroduzir MongoDB.

======================================================================
1. PRINCÍPIO CENTRAL DE PRODUTO
======================================================================

O Sirius NÃO deve parecer:

- ERP pessoal;
- coleção de dashboards;
- dez aplicativos colados;
- chatbot em cima de CRUD.

O usuário deve perceber:

"Existe um assistente que entende minha situação e coordena minhas áreas."

A inteligência aumenta por trás.

A interface principal deve ficar SIMPLES.

Perguntas fundamentais que o Sirius deve conseguir responder:

1. O que preciso fazer agora?
2. Por que isso é prioridade?
3. Estou no ritmo?
4. O que mudou?
5. O que está em risco?
6. O que acontece se eu mudar meu plano?
7. O Sirius pode fazer alguma coisa para me ajudar?

======================================================================
2. ARQUITETURA ALVO
======================================================================

Estrutura conceitual:

                         SIRIUS
                            │
                      SIRIUS CORE
                            │
        ┌───────────────────┼────────────────────┐
        │                   │                    │
      Memory             Event Bus           Agent
      Search             Automation          RAG
      Audit              Planner             Notifications
      Context            Goals               Calendar
        │                   │                    │
        └───────────────────┼────────────────────┘
                            │
        ┌───────────────────┼─────────────────────────────┐
        │                   │              │              │
  PreparationEngine    FinanceEngine   TrainingEngine NutritionEngine
        │                   │              │              │
        └───────────────────┼──────────────┼──────────────┘
                            │
                        Life State
                            │
                     Global Planner
                            │
                        Sirius Agent

Não criar dependências circulares entre módulos.

Finance não deve importar internals de Studies.

Studies não deve manipular tabelas internas de Workouts.

Cada domínio deve fornecer contratos estruturados.

======================================================================
3. CONTRATO DOS ENGINES
======================================================================

Quando apropriado, os motores especializados devem convergir para
interfaces conceituais semelhantes:

get_state(user_id)

get_recommendations(user_id)

get_events(user_id)

get_actions(user_id)

simulate(user_id, scenario)

Não é obrigatório criar uma classe abstrata artificial se isso piorar
o código.

Mas o Sirius Core deve consumir contratos claros.

Objetivo:

PreparationEngine
FinanceEngine
TrainingEngine
NutritionEngine

podem alimentar o Core sem conhecer internals uns dos outros.

======================================================================
4. FONTE DA VERDADE
======================================================================

REGRA CRÍTICA:

LLM NÃO É FONTE DE VERDADE PARA MÉTRICAS.

Não deixar Gemini/Groq decidir arbitrariamente:

- domínio;
- cobertura;
- score;
- risco;
- saldo;
- orçamento;
- volume;
- progresso;
- tempo disponível;
- vencimento;
- domínio de estudo;
- número de erros;
- prioridade-base;
- carga executada.

Esses dados devem vir de:

- fatos;
- eventos;
- cálculos;
- regras;
- dados externos verificados.

A IA pode:

- interpretar;
- explicar;
- ensinar;
- resumir;
- conversar;
- classificar com confiança explícita;
- sugerir;
- propor ações.

======================================================================
5. EXPLAINABILITY
======================================================================

Toda recomendação importante deve poder fornecer:

"Por quê?"

Isso NÃO significa chain-of-thought.

Nunca expor raciocínio interno do modelo.

Gerar explicação a partir de reasons estruturados.

Exemplo:

{
  action: "review_topic",
  topic: "...",
  reasons: [
    "accuracy_low",
    "review_overdue",
    "exam_weight_high",
    "fits_available_slot"
  ]
}

Frontend:

Por que isso?

- precisão recente: 51%;
- duas revisões vencidas;
- relevância alta no edital;
- cabe no bloco livre atual.

======================================================================
6. PROVENIÊNCIA
======================================================================

Informações importantes devem distinguir:

OFICIAL
EXTRAÍDO COM EVIDÊNCIA
INFERIDO
SUGERIDO

Especialmente:

- edital;
- retificação;
- pesos;
- número de questões;
- datas;
- regras de banca;
- requisitos.

Nunca transformar inferência em informação oficial.

======================================================================
7. MODELO DE AUTONOMIA
======================================================================

Preservar perfis:

conservador
balanceado
proativo

Inicialmente:

ações significativas são propostas.

Ações de alto impacto sempre exigem confirmação.

Especialmente:

- dinheiro;
- exclusões;
- envio externo;
- mudanças irreversíveis;
- alterações sensíveis.

Não implementar autonomia irrestrita.

======================================================================
8. IA
======================================================================

Manter:

Gemini
Groq

free-tier-first.

Nunca:

- ativar modelo pago automaticamente;
- cadastrar billing;
- usar fallback pago sem autorização;
- vazar API key;
- colocar API key no frontend.

IA deve degradar graciosamente.

Se modelo estiver indisponível:

funções determinísticas continuam funcionando.

======================================================================
9. RAG
======================================================================

Preservar RAG lexical SQL atual.

pgvector/embeddings continuam opcionais.

Não ativar infraestrutura adicional só porque parece tecnicamente elegante.

Se busca lexical + estrutura relacional resolver a necessidade atual,
usar isso.

======================================================================
10. VOZ
======================================================================

Voice é interface.

Não é arquitetura central.

Preservar push-to-talk / fluxo atual.

No futuro poderá ser usado para:

- revisão oral;
- quiz;
- comandos;
- consulta rápida.

Não bloquear nenhuma fase por Voice.

======================================================================
11. ESTRATÉGIA DE ENTREGA
======================================================================

NÃO implementar tudo em uma PR gigante.

Executar este programa por fases sequenciais.

Depois de cada PR:

1. CI completo;
2. Codex review;
3. corrigir P1/P2 válidos;
4. CI novamente;
5. merge;
6. esperar deploy;
7. smoke read-only;
8. somente então iniciar próxima fase.

Se PR não tiver migration:

merge automático permitido após tudo verde.

Se PR tiver migration:

NÃO mergear automaticamente.

Parar e informar:

- revision;
- down_revision;
- comando Alembic;
- ordem de deploy.

Esperar confirmação humana de que migration foi aplicada ao Neon.

======================================================================
12. MIGRATIONS
======================================================================

Somente Alembic.

Nunca:

create_all
DDL no startup
ALTER TABLE manual em produção

Migration sempre:

- aditiva quando possível;
- empty DB test;
- upgrade test;
- alembic check.

======================================================================
13. PR SEQUENCE
======================================================================

Sequência alvo:

FASE 1
Edital Reliability

FASE 2
Preparation Core 3.0

FASE 3
Edital Intelligence & Radar

FASE 4
Questions Intelligence

FASE 5
Adaptive Strategy Engine

FASE 6
Exams, Simulations & Final Sprint

FASE 7
Sirius Tutor & Knowledge

FASE 8
Unified Life State + Global Planner

FASE 9
Finance Intelligence 2.0

FASE 10
Training Intelligence 2.0

FASE 11
Nutrition Intelligence 2.0

FASE 12
Event & Automation Engine 2.0

FASE 13
Sirius Command Center

FASE 14
Integrated Hardening

Números reais das PRs podem variar.

Não depender do número da PR no código.

======================================================================
FASE 1 — EDITAL RELIABILITY
======================================================================

Branch:

fix/studies-edital-resilience

Objetivo:

corrigir produção sem durable object storage.

Atualmente:

POST /study/edital-jobs

depende de object storage.

Quando não configurado:

503 durable_storage_unavailable.

Existe:

POST /study/programs/analyze-edital

e ambos convergem para:

process_edital_analysis(...)

Implementar:

storage disponível
→ background job.

storage indisponível
→ análise direta.

Utilizar:

GET /study/edital-jobs

upload_available.

Adicionar fallback defensivo apenas para erro estruturado:

durable_storage_unavailable.

Não usar qualquer 503 como fallback.

Não duplicar pipeline.

Não salvar PDF no PostgreSQL.

Não salvar Base64.

Não usar filesystem efêmero como storage durável.

Não contratar storage.

======================================================================
FASE 1 — UX DO EDITAL
======================================================================

Separar corretamente:

ETAPA 1
Analisar edital.

Campos:

PDF
Reanalisar/ignorar cache em opção avançada.

CTA:

Analisar edital.

ETAPA 2

Escolher cargo.

Depois:

Data da prova
Horas/dia
Dias/semana

CTA:

Gerar programa.

Hoje esses conceitos estão misturados.

Corrigir.

Preservar:

- multi-cargo;
- cache SHA-256;
- audit;
- evidence;
- disciplina incompleta;
- seleção do cargo.

======================================================================
FASE 1 — FILE AUDIT
======================================================================

Auditar também:

- mapa mental;
- materiais;
- Agent attachments;
- treino;
- outros PDFs/imagens.

Classificar:

A funciona sem storage;
B possui fallback;
C requer storage mas comunica corretamente;
D broken/dead-end.

Corrigir apenas D simples.

Documentar demais.

Criar:

docs/FILE_UPLOAD_AUDIT.md
docs/EDITAL_ANALYSIS_MODES.md

======================================================================
FASE 2 — PREPARATION CORE 3.0
======================================================================

Branch sugerida:

feat/preparation-core-3

Objetivo:

criar o núcleo do assistente de preparação para concurso.

IMPORTANTE:

AUDITAR PRIMEIRO modelos existentes:

StudyProgram
StudyTarget
Notebook
StudyTopic
StudySession
StudyPlan
StudyPlanEntry
QuestionAttempt
ReviewEvent
StudyEvidence
e relacionados.

EVITAR duplicar conceitos já existentes.

Evoluir schema existente quando correto.

======================================================================
15. PREPARATION
======================================================================

Uma preparação representa:

- concurso;
- cargo;
- banca;
- prova;
- objetivo;
- edital;
- disponibilidade;
- estratégia;
- matérias;
- histórico.

Suportar:

mais de uma preparação.

Permitir:

preparação principal.

Não obrigar concurso.

Preparações genéricas continuam válidas.

Exemplos:

TJ-PI Analista
TRT Técnico
OAB
Faculdade
Certificação

======================================================================
16. PREPARATION STATE
======================================================================

Criar serviço determinístico:

PreparationState.

Deve conseguir responder:

- preparation_id;
- target;
- exam_date;
- days_remaining;
- syllabus coverage;
- mastery;
- study debt;
- reviews due;
- performance;
- recent trend;
- required pace;
- current pace;
- risk areas;
- next candidates;
- source freshness.

Não persistir snapshots como única fonte da verdade.

Pode materializar/cachear se necessário.

Fatos permanecem fonte.

======================================================================
17. SYLLABUS GRAPH
======================================================================

Representar hierarquia:

preparation
  → discipline
    → topic
      → subtopic

Quando houver:

- legislation;
- materials;
- questions;
- reviews;
- errors;
- exam items.

Usar IDs estáveis.

Não depender apenas do texto do nome.

Preservar topic_key quando já existente.

======================================================================
18. COVERAGE VS MASTERY
======================================================================

Separar claramente:

COBERTURA

"Já tive contato com este conteúdo?"

de:

DOMÍNIO

"Há evidência de que consigo recuperar/aplicar esse conteúdo?"

Nunca usar porcentagem única para ambos.

Exemplo:

Cobertura:
62%

Domínio do conteúdo estudado:
71%

======================================================================
19. EVIDENCE LEDGER
======================================================================

Criar visão unificada das evidências de aprendizagem.

Fontes existentes podem incluir:

- sessão;
- questão;
- revisão;
- flashcard;
- simulado;
- redação;
- prática.

Evitar copiar todos os fatos para nova tabela sem necessidade.

Pode existir serviço/projeção:

EvidenceLedger.

Cada alteração de mastery precisa ser auditável.

Nunca:

"IA decidiu que mastery = 82%."

======================================================================
20. LEARNING STAGES
======================================================================

Permitir classificação derivada como:

not_started
exposed
practicing
consolidating
mastered
maintenance

Não substituir os fatos.

É uma projeção.

======================================================================
21. CANDIDATE MODEL / DIGITAL TWIN
======================================================================

Criar modelo operacional da preparação do usuário.

Dados possíveis:

- ritmo médio;
- disponibilidade;
- sessões concluídas;
- média de duração;
- desempenho por período;
- horário preferido;
- matérias mais difíceis;
- confiança;
- tipos de erro;
- consistência.

Não inferir:

- diagnóstico;
- transtorno;
- doença;
- capacidade intelectual.

É um perfil operacional de estudo.

======================================================================
22. PREPARATION HEALTH
======================================================================

Criar diagnóstico composto explicável.

Exemplo:

Cobertura       61%
Domínio         72%
Revisões        83%
Ritmo           94%
Questões        68%
Consistência    79%

Risco geral:
Moderado

NÃO chamar:

"chance de aprovação".

Cada componente deve ser abrível e explicável.

======================================================================
FASE 3 — EDITAL INTELLIGENCE & RADAR
======================================================================

Branch:

feat/edital-intelligence-radar

======================================================================
23. SOURCE REGISTRY
======================================================================

Criar fontes acompanháveis por preparação.

Tipos:

- página oficial;
- banca;
- PDF oficial;
- retificação;
- comunicado;
- resultado;
- cronograma.

Opt-in.

Respeitar:

- robots;
- limites;
- domínio;
- HTTP;
- políticas;
- sem CAPTCHA bypass.

======================================================================
24. RADAR
======================================================================

Detectar mudanças por:

- hash;
- metadata;
- conteúdo;
- versão.

Não chamar LLM se nada mudou.

Fluxo:

fetch
→ hash/diff determinístico
→ mudou?
→ sim
→ análise de impacto.

======================================================================
25. IMPACT ANALYSIS
======================================================================

Quando surgir retificação:

comparar:

- cargos;
- disciplinas;
- tópicos;
- datas;
- pesos;
- questões;
- regras;
- cronograma.

Produzir:

o que mudou;
fonte;
nível de confiança;
impacto no syllabus;
impacto no plano.

Exemplo:

"Direito Administrativo recebeu dois novos tópicos.

Impacto estimado:
+95 minutos de cobertura inicial.

Seu plano atual precisará ser recalculado."

======================================================================
26. TIMELINE DO CONCURSO
======================================================================

Extrair/manter quando oficial:

- inscrição;
- isenção;
- pagamento;
- prova;
- local;
- recurso;
- resultado;
- outras datas relevantes.

Pode gerar eventos/lembretes.

Somente dados com proveniência adequada.

======================================================================
27. TEC / QCONCURSOS
======================================================================

Criar arquitetura compatível com providers.

NÃO fazer scraping de:

Tec Concursos
QConcursos
ou serviços similares.

Utilizar apenas:

- API oficial;
- exportação permitida;
- importação do usuário;
- integrações autorizadas.

======================================================================
FASE 4 — QUESTIONS INTELLIGENCE
======================================================================

Branch:

feat/questions-intelligence

======================================================================
28. QUESTION PROVIDER
======================================================================

Criar abstração:

QuestionProvider.

Providers possíveis:

manual
import
official
generated
future_external_provider

Não acoplar UI a uma empresa.

======================================================================
29. QUESTION PROVENANCE
======================================================================

Cada questão precisa saber se é:

official
imported
user_created
ai_generated

Questão IA nunca pode parecer questão oficial.

Mostrar claramente:

"Gerada pelo Sirius".

======================================================================
30. ATTEMPT MODEL
======================================================================

Além de:

correct

registrar quando disponível:

- selected answer;
- time spent;
- confidence;
- skipped;
- changed answer;
- topic;
- preparation;
- difficulty;
- attempt date.

Confidence:

exemplo:

guess
uncertain
confident

ou escala simples.

Não obrigar em todos os fluxos.

======================================================================
31. ERROR TAXONOMY
======================================================================

Permitir erro classificado como:

knowledge_gap
concept_confusion
interpretation
attention
calculation
memory
time_management
other

A IA pode SUGERIR classificação.

Usuário pode corrigir.

======================================================================
32. ERROR FORENSICS
======================================================================

Detectar padrões como:

"três questões diferentes foram perdidas pelo mesmo conceito."

LLM pode ajudar na análise semântica.

Resultado precisa ser persistido como:

suggestion / cluster

e não alterar fatos originais.

======================================================================
33. SMART ERROR BANK
======================================================================

Banco de erros deve responder:

- erros mais recorrentes;
- conceitos associados;
- última ocorrência;
- taxa de recuperação;
- revisão relacionada;
- evidência posterior.

======================================================================
34. AI QUESTION LAB
======================================================================

Permitir gerar questões a partir de:

- syllabus;
- materiais próprios;
- tópicos;
- erros.

Questão gerada deve incluir:

- topic;
- difficulty;
- answer;
- explanation;
- source context;
- generated_by_ai=true.

======================================================================
35. AI QUESTION VALIDATION
======================================================================

Antes de mostrar questão sintética:

realizar validação separada quando possível:

- resposta coerente;
- alternativas não ambíguas;
- aderência ao material;
- apenas uma correta quando aplicável.

Questão de baixa confiança:

descartar.

Não gastar chamadas excessivas.

======================================================================
FASE 5 — ADAPTIVE STRATEGY ENGINE
======================================================================

Branch:

feat/adaptive-strategy-engine

======================================================================
36. SEPARAR STRATEGY DE PLANNER
======================================================================

Strategy Engine responde:

"O que deveria ser estudado?"

Planner responde:

"Quando isso cabe?"

Não misturar.

Fluxo:

Preparation State
     ↓
Strategy Engine
     ↓
Priority Candidates
     ↓
Global/Study Planner
     ↓
horários

======================================================================
37. RISK ENGINE
======================================================================

Risco por tópico pode considerar:

- importância/peso;
- cobertura;
- domínio;
- questões;
- erros;
- review due;
- tempo restante;
- tendência;
- evidência insuficiente.

Fórmula deve ser:

- determinística;
- documentada;
- testada;
- explicável.

Não chamar LLM para produzir risk score.

======================================================================
38. STUDY DEBT
======================================================================

Calcular dívida de preparação:

- revisão vencida;
- conteúdo crítico não iniciado;
- sessão planejada não cumprida;
- tópico ficando para trás;
- metas intermediárias atrasadas.

Dívida não precisa ser um número único.

Pode existir por categoria/tópico.

======================================================================
39. EXPECTED RETURN
======================================================================

Criar heurística explicável para retorno esperado de estudo.

Conceito:

impacto provável
× necessidade
÷ custo temporal

Não apresentar como ciência exata.

Usar como ranking operacional.

======================================================================
40. REVIEW ENGINE
======================================================================

Não limitar a revisão fixa:

1d / 7d / 30d.

Permitir ajuste baseado em:

- domínio;
- erro recente;
- confiança;
- importância;
- histórico.

Manter limites seguros.

======================================================================
41. KNOWLEDGE DECAY
======================================================================

Risco de retenção pode aumentar com o tempo.

Não dizer:

"você esqueceu".

Dizer:

"há pouca evidência recente deste tópico."

Decay deve ser:

- suave;
- explicável;
- limitado.

======================================================================
42. RECOVERY MODE
======================================================================

Se usuário perder dias:

NÃO empilhar tudo.

Replanejar:

- manter críticos;
- reagendar;
- reduzir baixa prioridade;
- recalcular ritmo.

Exemplo:

"Você ficou três dias sem estudar.

Em vez de adicionar 6 horas extras amanhã,
o plano foi redistribuído pelos próximos cinco dias."

======================================================================
43. PLAN A / B / C
======================================================================

Permitir:

Plano ideal
Plano mínimo
Plano emergencial

Exemplo:

Hoje tenho 30 min.

Sirius escolhe atividade de maior retorno compatível.

======================================================================
44. WHAT-IF STUDY
======================================================================

Simulação sem alterar estado real.

Perguntas:

"Se estudar 2h/dia consigo cobrir o edital?"

"E se estudar 4h no sábado?"

"E se perder uma semana?"

Retornar:

- cobertura projetada;
- carga;
- dívida;
- riscos.

Não retornar probabilidade falsa de aprovação.

======================================================================
45. LOAD GUARD
======================================================================

Detectar carga operacional excessiva:

- muitas horas programadas;
- sequência grande sem descanso;
- baixa aderência recorrente.

Não diagnosticar burnout.

Usar linguagem:

"carga planejada acima do seu padrão recente."

======================================================================
FASE 6 — EXAMS, SIMULATIONS & FINAL SPRINT
======================================================================

Branch:

feat/exam-intelligence

======================================================================
46. EXAM BLUEPRINT
======================================================================

Usar quando conhecidos:

- número de questões;
- disciplinas;
- pesos;
- distribuição;
- duração;
- regras da banca.

Distinguir:

oficial
estimado
não informado.

======================================================================
47. SIMULADO FIEL
======================================================================

Permitir:

- distribuição do edital;
- pontos fracos;
- uma matéria;
- vários tópicos;
- prova completa;
- revisão rápida.

Synthetic questions sempre identificadas.

======================================================================
48. EXAM SESSION
======================================================================

Registrar:

- tempo;
- resposta;
- troca de resposta quando suportado;
- confiança;
- branco;
- acerto;
- tópico.

======================================================================
49. POST-MORTEM
======================================================================

Depois do simulado:

diagnosticar:

- onde perdeu pontos;
- erro de conteúdo;
- erro de tempo;
- matérias lentas;
- confiança mal calibrada;
- erros repetidos.

Transformar em recomendações.

======================================================================
50. SPEED PROFILE
======================================================================

Medir:

tempo médio por:

- disciplina;
- tópico;
- tipo de questão.

Exemplo:

"Seu desempenho está bom, mas Português consome 1,8× seu tempo médio."

======================================================================
51. CONFIDENCE CALIBRATION
======================================================================

Comparar:

confiança
vs
resultado.

Acerto em chute não deve pesar como evidência igual a acerto confiante.

Implementar cuidadosamente e documentar.

======================================================================
52. FINAL SPRINT
======================================================================

Strategy Engine muda comportamento conforme a prova se aproxima.

Exemplos:

90 dias
30 dias
14 dias
7 dias
2 dias

Aumentar progressivamente:

- questões;
- revisão;
- error bank;
- simulados.

Reduzir conteúdo novo quando apropriado.

Não tomar decisão irreversível sem explicar.

======================================================================
53. EXAM STRATEGY
======================================================================

Permitir estratégia:

- ordem;
- tempo;
- matérias;
- revisão final;
- reserva para gabarito;
- regras de penalização.

Somente usar características da banca se sustentadas por fonte.

======================================================================
54. REDAÇÃO / DISCURSIVA
======================================================================

Evoluir correção.

Critérios:

- estrutura;
- argumentação;
- aderência;
- gramática;
- conteúdo;
- critérios específicos disponíveis.

Não apresentar:

"nota oficial".

Mostrar:

"avaliação estimada pelo Sirius".

Histórico e evolução.

======================================================================
FASE 7 — SIRIUS TUTOR & KNOWLEDGE
======================================================================

Branch:

feat/sirius-tutor

======================================================================
55. TUTOR MODES
======================================================================

Adicionar modos:

Explicar
Socrático
Revisão rápida
Me testar
Questões
Flashcards
Aprofundar
Pré-prova

Contextualizar com preparation_id/topic_id.

======================================================================
56. SOCRATIC MODE
======================================================================

Fluxo:

pergunta
→ usuário responde
→ Sirius avalia
→ nova pergunta
→ explicação somente quando necessário.

Não transformar tudo em palestra.

======================================================================
57. EXAMINER MODE
======================================================================

Exemplo:

"Me cobre como examinador."

Questionamento progressivo.

Pode usar banca como contexto quando há evidência suficiente.

======================================================================
58. HIERARCHICAL RAG
======================================================================

Ordem preferencial:

1. material do usuário/preparação;
2. edital/fontes oficiais;
3. dados estruturados do Sirius;
4. conhecimento geral do modelo.

Resposta deve distinguir quando estiver usando conhecimento geral.

======================================================================
59. MATERIAL INTELLIGENCE
======================================================================

Vincular materiais a:

preparation
discipline
topic

Permitir:

"onde estudei isso?"

"quais materiais tenho sobre licitações?"

"quais erros estão relacionados a este PDF?"

======================================================================
60. FILES
======================================================================

Respeitar limitações de storage descobertas na Fase 1.

Se não houver durable storage:

permitir processamento em memória quando seguro.

Persistir:

texto extraído / metadata / hashes

quando suficiente.

Não fingir retenção do original.

======================================================================
61. SMART HIGHLIGHTS
======================================================================

Trecho marcado pode sugerir:

- flashcard;
- pergunta;
- revisão;
- nota.

Sempre como proposta.

======================================================================
62. SESSION COPILOT
======================================================================

Durante estudo:

- objetivo da sessão;
- timer;
- conteúdo;
- recall;
- questões;
- encerramento.

Ao terminar:

resumo factual.

Exemplo:

52 min
18 questões
72% precisão
2 tópicos revisados

Depois:

recomendação.

======================================================================
63. VOICE STUDY
======================================================================

Se fluxo atual permitir sem grande regressão:

permitir quiz oral / revisão oral.

Não bloquear a Fase 7 por Voice.

======================================================================
FASE 8 — UNIFIED LIFE STATE + GLOBAL PLANNER
======================================================================

Branch:

feat/sirius-life-state

======================================================================
64. LIFE STATE
======================================================================

Criar agregador:

LifeState.

Não precisa ser tabela.

Debe incluir snapshots estruturados de:

Tempo
Preparação
Financeiro
Treino
Nutrição
Rotina
Metas

Exemplo:

{
  "time": {...},
  "preparation": {...},
  "finance": {...},
  "training": {...},
  "nutrition": {...},
  "routine": {...}
}

Bounded.

Não carregar banco inteiro.

======================================================================
65. PRIORITY CANDIDATE
======================================================================

Os engines podem emitir candidatos.

Conceito:

{
 domain,
 action_type,
 title,
 duration,
 earliest,
 latest,
 fixed_time,
 urgency,
 importance,
 reasons
}

Valores internos não precisam aparecer na UI.

======================================================================
66. GLOBAL PLANNER
======================================================================

Unificar calendário operacional.

Não existir:

planner de estudo
versus
planner de treino
versus
planner geral

competindo.

Motores dizem:

O QUE precisa acontecer.

Global Planner decide:

QUANDO cabe.

Respeitar:

- eventos;
- tarefas fixas;
- trabalho;
- estudo;
- treino;
- preferências;
- prazo;
- horário atual.

======================================================================
67. NÃO MOVER FIXOS
======================================================================

Nunca mover automaticamente:

- compromisso;
- tarefa fixed-time;
- sessão explicitamente travada.

Detectar conflito.

======================================================================
68. CROSS-DOMAIN PLANNING
======================================================================

Exemplo:

Trabalho 08–18
Treino 19h
Revisão crítica
Conta vence hoje

Sirius pode priorizar:

5 min pagar conta
45 min revisão
treino fixo

e mover atividade flexível menos crítica.

======================================================================
69. UNIFIED WHAT-IF
======================================================================

Permitir simulação cross-domain.

Exemplo:

"E se eu estudar 3h e treinar 5x por semana?"

Impacto:

- agenda;
- estudo;
- treino;
- carga total.

Nenhuma alteração real até confirmação.

======================================================================
FASE 9 — FINANCE INTELLIGENCE 2.0
======================================================================

Branch:

feat/finance-intelligence-2

======================================================================
70. FINANCE STATE
======================================================================

FinanceEngine.get_state():

- balance;
- income;
- expense;
- upcoming bills;
- budgets;
- recurring commitments;
- debts;
- goals;
- forecast.

Decimal sempre.

======================================================================
71. CASH FLOW FORECAST
======================================================================

Projeção determinística.

Considerar:

- recorrências;
- parcelas;
- vencimentos;
- renda conhecida;
- despesas previstas.

Não inventar renda futura.

Distinguir:

confirmed
estimated.

======================================================================
72. FINANCE WHAT-IF
======================================================================

Exemplos:

"Se eu antecipar esta dívida?"

"Se assumir R$500/mês?"

"Quanto sobra até dezembro?"

Simulação.

Nunca alterar transações reais durante cenário.

======================================================================
73. DEBT STRATEGY
======================================================================

Permitir comparar:

avalanche
snowball
custom

Mostrar:

- juros quando conhecidos;
- tempo;
- fluxo de caixa.

Não inventar taxas.

======================================================================
74. SPENDING INSIGHTS
======================================================================

Detectar deterministicamente:

- categoria crescendo;
- desvio do orçamento;
- recorrência;
- aumento incomum.

IA escreve explicação.

======================================================================
75. FINANCE SAFETY
======================================================================

Agent não:

- transfere dinheiro;
- contrata crédito;
- faz compra;
- paga conta

sem integração específica e consentimento explícito.

Nesta fase:

planejar/analisar/propor.

======================================================================
FASE 10 — TRAINING INTELLIGENCE 2.0
======================================================================

Branch:

feat/training-intelligence-2

======================================================================
76. PRESERVAR UX2
======================================================================

Não destruir Workout Session UX 2.0.

Construir inteligência por trás.

======================================================================
77. TRAINING STATE
======================================================================

Tracking:

- frequência;
- volume;
- séries;
- peso;
- reps;
- RPE;
- progressão;
- aderência;
- PRs;
- grupos musculares.

======================================================================
78. PROGRESSION ENGINE
======================================================================

Sugestão baseada em dados.

Exemplo:

últimas sessões
+ reps
+ RPE
+ carga

→ sugestão.

Não mudar carga automaticamente.

======================================================================
79. PERSONAL RECORDS
======================================================================

Registrar quando calculável:

- maior carga;
- maior volume;
- melhor performance equivalente.

Definir regras claras.

======================================================================
80. EXERCISE SUBSTITUTION
======================================================================

Exemplo:

"Academia cheia."

Sirius pode sugerir exercício substituto com:

- mesmo objetivo;
- grupo;
- padrão de movimento quando disponível.

Proposta, não substituição silenciosa.

======================================================================
81. TRAINING LOAD
======================================================================

Detectar:

- aumento brusco de volume;
- queda recorrente;
- baixa aderência.

Não diagnosticar lesão/fadiga clínica.

Usar linguagem operacional.

======================================================================
82. YOUTUBE
======================================================================

Preservar:

- API oficial;
- backend;
- max 3;
- on demand;
- cache;
- sem autoplay.

======================================================================
FASE 11 — NUTRITION INTELLIGENCE 2.0
======================================================================

Branch:

feat/nutrition-intelligence-2

======================================================================
83. NUTRITION STATE
======================================================================

Considerar dados já existentes:

- metas;
- refeições;
- macros;
- consumo;
- templates.

Não reescrever módulo sem necessidade.

======================================================================
84. REMAINING DAY
======================================================================

Responder:

"O que falta hoje?"

Exemplo:

proteína restante
carboidrato
energia

somente se metas existirem.

======================================================================
85. MEAL SUGGESTION
======================================================================

Sugestões com base em:

- objetivo configurado;
- refeições anteriores;
- alimentos/templates;
- restante do dia;
- preferências.

Não fazer prescrição médica.

======================================================================
86. MEAL TEMPLATES
======================================================================

Permitir refeições recorrentes/favoritas.

Registro rápido.

======================================================================
87. BUDGET-AWARE FOOD
======================================================================

Integração cross-domain opcional:

"Monte opções da semana respeitando um orçamento."

Finance fornece limite.

Nutrition fornece composição.

Não gerar compra automática.

======================================================================
88. FOOD IMAGE
======================================================================

Se reconhecimento por imagem já existir:

evoluir de forma conservadora.

Toda estimativa por imagem deve ser marcada como estimativa.

Usuário pode corrigir.

======================================================================
FASE 12 — EVENT & AUTOMATION ENGINE 2.0
======================================================================

Branch:

feat/event-automation-engine-2

======================================================================
89. DOMAIN EVENTS
======================================================================

Criar ou consolidar eventos tipados.

Exemplos:

task.completed

task.overdue

study.session.completed

study.review.overdue

question.failed

exam.approaching

edital.updated

workout.completed

expense.created

budget.exceeded

bill.due

goal.off_track

nutrition.target_remaining

======================================================================
90. EVENT ARCHITECTURE
======================================================================

Não exigir Kafka.

PostgreSQL pode ser suficiente.

Priorizar:

- durabilidade;
- idempotência;
- bounded processing;
- ownership.

Não adicionar infraestrutura gratuitamente.

======================================================================
91. EVENT RULES
======================================================================

Regras são determinísticas.

Exemplo:

question.failed
3 vezes
mesmo semantic cluster
→ suggestion.revision

LLM é chamado somente depois do trigger quando necessário.

======================================================================
92. AUTOMATIONS
======================================================================

Exemplos:

revisão vencida
→ lembrar.

conta próxima
→ lembrar.

edital alterado
→ Impact Analysis.

plano perdido
→ propor replanejamento.

workout completed
→ atualizar recommendation state.

======================================================================
93. QUIET HOURS
======================================================================

Notificações devem respeitar:

- preferência;
- prioridade;
- quiet hours.

Não spam.

======================================================================
94. DAILY BRIEF
======================================================================

Evoluir briefing.

Deve combinar:

- tempo;
- preparação;
- treino;
- financeiro;
- rotina.

Dados estruturados primeiro.

LLM transforma em linguagem natural.

======================================================================
95. NIGHT REVIEW
======================================================================

Resumo:

- executado;
- pendente;
- alterações;
- amanhã.

Não modificar amanhã silenciosamente salvo autonomia previamente permitida.

======================================================================
96. WEEKLY COACH
======================================================================

Toda semana:

planejado vs executado.

Analisar:

- preparação;
- rotina;
- treino;
- finanças quando relevante.

Propor ajustes.

======================================================================
97. TELEGRAM
======================================================================

Aproveitar integração existente.

Possibilidades:

"O que faço hoje?"

"Terminei Administrativo."

"Quanto gastei esta semana?"

"Qual meu treino?"

Alertas importantes.

Nunca expor informações além do usuário autenticado/pareado.

======================================================================
FASE 13 — SIRIUS COMMAND CENTER
======================================================================

Branch:

feat/sirius-command-center

======================================================================
98. HOME
======================================================================

A home NÃO deve virar grid infinito.

Prioridade:

PRÓXIMA AÇÃO

HOJE

ATENÇÃO

ÁREAS

Exemplo:

Boa tarde.

PRÓXIMA AÇÃO

Revisar Licitações
35 min

[Começar]

HOJE

18:30 Estudo
19:30 Treino

ATENÇÃO

• revisão vencida
• fatura amanhã
• atualização no edital

Preparação | No ritmo
Financeiro | Estável
Treino     | 3/4 semana

======================================================================
99. CONTEXTUAL SIRIUS
======================================================================

Agent deve receber:

page context
selected entity
LifeState relevante

Exemplos:

Finance:
"Por que gastei mais?"

Workout:
"Como evoluí no supino?"

Question:
"Por que errei?"

Edital:
"O que mudou?"

Não obrigar usuário a repetir contexto.

======================================================================
100. UNIVERSAL SEARCH
======================================================================

Busca:

edital
materiais
tópicos
questões
erros
tarefas
finanças
treinos
conversas

Respeitar ownership.

Resultados agrupados.

Não carregar tudo em memória.

======================================================================
101. MEMORY
======================================================================

Memória explícita do Sirius pode representar:

Fact
Preference
Decision

Exemplos:

"Prefere estudar teoria pela manhã."

"Evitar duas matérias pesadas seguidas."

"Domingo reservado para descanso."

Usuário deve conseguir visualizar/corrigir quando aplicável.

Não criar "memória mágica".

======================================================================
102. WHY ENGINE
======================================================================

Padronizar UI:

Por quê?

para:

- prioridade;
- plano;
- recomendação;
- mudança;
- alerta.

Sem revelar CoT.

======================================================================
103. AUDIT LOG
======================================================================

Usuário deve poder responder:

"Por que meu plano mudou ontem?"

Registrar:

- ator;
- evento;
- ação;
- timestamp;
- motivo estruturado;
- antes/depois quando útil.

Não duplicar logs técnicos.

======================================================================
104. UNDO
======================================================================

Quando ação for reversível:

oferecer undo.

Especialmente:

- reorganização;
- marcações;
- mudanças leves.

Não prometer undo onde o domínio não suporta.

======================================================================
105. SCENARIO CENTER
======================================================================

Interface para what-if.

Exemplos:

- estudo;
- finanças;
- rotina;
- cross-domain.

Scenario nunca grava fatos reais até confirmação.

======================================================================
106. DATA EXPORT
======================================================================

Permitir portabilidade progressivamente.

Formatos:

JSON
CSV
relatórios PDF onde fizer sentido.

Nunca bloquear usuário dentro do Sirius.

======================================================================
FASE 14 — INTEGRATED HARDENING
======================================================================

Branch:

chore/sirius-3-integrated-hardening

======================================================================
107. END-TO-END FLOWS
======================================================================

Testar cenários completos.

Exemplo 1:

importar edital
→ escolher cargo
→ preparação
→ syllabus
→ estudar
→ questão
→ erro
→ revisão
→ Strategy Engine
→ plano atualizado.

Exemplo 2:

criar tarefa
→ horário
→ Global Planner
→ Dashboard
→ conclusão.

Exemplo 3:

treino
→ sets
→ progressão
→ Training State
→ LifeState.

Exemplo 4:

gasto
→ budget
→ Finance State
→ alert.

======================================================================
108. CROSS-DOMAIN TEST
======================================================================

Cenário:

dia possui:

- trabalho;
- estudo;
- treino;
- conta;
- tarefa.

Global Planner deve respeitar:

fixos
deadlines
tempo atual

e não mover compromisso arbitrariamente.

======================================================================
109. MULTI-USER SECURITY
======================================================================

Para TODAS as novas estruturas:

teste Alice/Bob.

Usuário B nunca pode:

- ler;
- alterar;
- buscar;
- simular;
- receber cache;
- receber recommendation

do usuário A.

======================================================================
110. CACHE SECURITY
======================================================================

TanStack/query cache:

namespace por sessão.

Backend cache:

key inclui owner quando necessário.

Logout:

limpar dados pessoais cacheados.

Troca de conta:

zero vazamento.

======================================================================
111. SQL
======================================================================

Auditar:

- N+1;
- missing index;
- unbounded query;
- ORDER BY;
- pagination;
- owner filter.

Novos índices só com justificativa.

======================================================================
112. PERFORMANCE
======================================================================

Não regredir:

Dashboard
Chat
Workouts
Studies

Medir:

- requests;
- SQL;
- payload;
- bundle;
- timing quando comparável.

Não inventar ganhos.

======================================================================
113. EXTERNAL APIS
======================================================================

CI sempre mockado.

Nunca usar API real no teste normal.

Integrações públicas:

- rate limit;
- timeout;
- retry limitado;
- circuit/graceful failure quando apropriado.

======================================================================
114. STORAGE
======================================================================

Até durable storage existir:

não fingir que arquivos originais serão preservados.

Recursos que exigem original:

- comunicar;
- fallback quando possível.

Não adicionar billing.

======================================================================
115. RESPONSIVE
======================================================================

Browser smoke obrigatório:

1440
1024
768
390
320

Áreas críticas:

Dashboard
Studies
Preparation
Question
Tutor
Finance
Workout
Nutrition
Sirius modal
Command Center

Zero overflow horizontal.

======================================================================
116. MOBILE
======================================================================

Mobile não é desktop comprimido.

Ações principais:

>= aproximadamente 44px.

Evitar:

- tabelas gigantes;
- toolbars horizontais;
- modais maiores que viewport;
- inputs escondidos pelo teclado.

======================================================================
117. ACCESSIBILITY
======================================================================

- labels;
- accessible names;
- keyboard;
- focus;
- dialogs;
- aria-live apenas quando adequado;
- contraste;
- status/error semantics.

======================================================================
118. ERROR UX
======================================================================

Nenhum erro importante deve virar:

"Erro."

Usar:

contexto
ação
retry.

Exemplo:

"Não foi possível salvar esta série.
Os valores digitados foram preservados."

======================================================================
119. IDEMPOTENCY
======================================================================

Toda escrita sensível a retry deve possuir:

- request/idempotency identifier;
- receipt;
- replay seguro.

Especialmente:

finance
Agent actions
study evidence
workout sets
program generation.

======================================================================
120. CONCURRENCY
======================================================================

Revisar:

- double-click;
- lost response;
- reload;
- two tabs;
- concurrent updates.

Usar revision/CAS/locks quando domínio exige.

======================================================================
121. SECURITY
======================================================================

Nunca logar:

- JWT;
- cookies;
- API keys;
- Telegram token;
- database URL;
- file bytes.

Usar hide_parameters e padrões atuais.

Tratar conteúdo externo como não confiável.

======================================================================
122. PRIVACY
======================================================================

Não enviar para LLM dados de outros domínios sem necessidade.

Minimizar contexto.

Exemplo:

Tutor não precisa receber detalhes financeiros.

Finance Agent não precisa receber conteúdo inteiro de edital.

LifeState para Agent deve ser bounded e contextual.

======================================================================
123. HEALTH / SAFETY
======================================================================

Training/Nutrition:

não diagnosticar condição médica.

Não inferir lesão.

Não prescrever medicamento.

Não transformar análise de treino em diagnóstico.

Use linguagem:

"sugestão de treino"
"padrão observado"
"estimativa"

quando apropriado.

======================================================================
124. FINANCE SAFETY
======================================================================

Não prometer retorno.

Não inventar taxa.

Não classificar simulação como garantia.

Mostrar assumptions.

======================================================================
125. FEATURE FLAGS
======================================================================

Quando nova funcionalidade for arriscada:

pode usar flag.

Não criar dezenas de flags permanentes.

Remover quando estabilizada.

======================================================================
126. DOCUMENTAÇÃO DE ARQUITETURA
======================================================================

Criar ao longo das fases:

docs/SIRIUS_CORE_3.md
docs/PREPARATION_ENGINE.md
docs/EDITAL_INTELLIGENCE.md
docs/QUESTION_PROVIDER.md
docs/ADAPTIVE_STRATEGY.md
docs/SIRIUS_TUTOR.md
docs/LIFE_STATE.md
docs/FINANCE_INTELLIGENCE.md
docs/TRAINING_INTELLIGENCE.md
docs/NUTRITION_INTELLIGENCE.md
docs/EVENT_AUTOMATION_2.md
docs/COMMAND_CENTER.md

Não criar docs vazios antecipadamente.

Cada fase cria seu documento quando implementada.

======================================================================
127. TEST STRATEGY
======================================================================

Em toda fase:

Backend:
- domain tests;
- PostgreSQL integration;
- ownership;
- idempotency;
- concurrency;
- regressions.

Frontend:
- unit;
- lint;
- build;
- interaction tests.

Browser:
- smoke;
- mobile;
- failure flows.

External:
mock.

======================================================================
128. PRODUCTION TESTING
======================================================================

CI nunca deve:

- criar dados na produção;
- registrar usuário real;
- criar gastos;
- enviar Telegram;
- mandar PDF;
- chamar Gemini real;
- chamar YouTube real.

Live smoke:

GET/read-only apenas.

======================================================================
129. CI
======================================================================

Antes de qualquer merge:

todos os workflows obrigatórios verdes.

Se flaky:

corrigir causa.

Não remover teste apenas para ficar verde.

======================================================================
130. CODE REVIEW
======================================================================

Abrir PR.

Executar Codex review.

P1/P2 válido:

corrigir.

Depois pedir novo review quando necessário.

Não mergear com achado relevante pendente.

======================================================================
131. COMMITS
======================================================================

Commits pequenos e temáticos.

Não:

"big update"
"final fixes"

Preferir:

feat(preparation): add deterministic preparation state

feat(strategy): rank study candidates by structured risk

fix(edital): fall back to direct analysis without durable storage

test(questions): cover confidence-aware evidence

======================================================================
132. COMPATIBILIDADE
======================================================================

Preservar dados existentes.

Não resetar PostgreSQL.

Não apagar informações atuais.

Migrations aditivas quando possível.

Se mudança exigir backfill:

fazer explicitamente e testar.

======================================================================
133. EXISTING FEATURES
======================================================================

NÃO deixar de lado:

- tarefas;
- hábitos;
- metas;
- calendário;
- finanças;
- treinos;
- alimentação;
- relatórios;
- Telegram;
- Sirius chat;
- voz existente;
- estudos genéricos.

Novos trabalhos devem preservá-los.

======================================================================
134. UI PRINCIPLE
======================================================================

Mais inteligência NÃO significa mais cards.

Sempre perguntar:

"Isso precisa aparecer permanentemente?"

Se não:

- details;
- modal;
- contextual action;
- secondary screen;
- Sirius Agent.

Home deve permanecer enxuta.

======================================================================
135. AI PRINCIPLE
======================================================================

O usuário deve perceber inteligência em:

- recomendação;
- adaptação;
- contexto;
- explicação;
- antecipação;
- integração.

Não apenas em textos gerados.

======================================================================
136. EVENTUAL EXPERIENCE TARGET
======================================================================

Exemplo de manhã:

"Bom dia.

Hoje você tem cerca de 3h15 livres.

Prioridade:
Revisar Licitações · 35 min

Por quê:
revisão vencida, precisão baixa e alta relevância no concurso.

Depois:
• trabalho até 18h;
• estudo 18:30;
• treino 19:30;
• fatura vence amanhã.

Sua preparação segue no ritmo."

======================================================================
137. EVENTUAL STUDY EXPERIENCE
======================================================================

"Estudar agora"

→ abre próxima atividade
→ timer
→ material
→ recall
→ questões
→ feedback
→ evidence
→ mastery
→ Strategy Engine
→ próxima recomendação.

Usuário não precisa manualmente atualizar cinco telas.

======================================================================
138. EVENTUAL FINANCE EXPERIENCE
======================================================================

Pergunta:

"Posso assumir R$ 500 por mês?"

Sirius:

simula cenário
→ fluxo
→ compromissos
→ metas

e explica assumptions.

Não cria dívida.

======================================================================
139. EVENTUAL TRAINING EXPERIENCE
======================================================================

Pergunta:

"O que faço hoje?"

Sirius considera:

- plano;
- sessão anterior;
- progressão;
- agenda.

Abre Workout UX 2.0 diretamente na sessão.

======================================================================
140. EVENTUAL CROSS-DOMAIN EXPERIENCE
======================================================================

Pergunta:

"Hoje só tenho 1 hora livre."

LifeState
     ↓
engines
     ↓
Global Planner

responde com priorização real.

Não apenas lista tarefas.

======================================================================
141. DEFINITION OF DONE — SIRIUS 3
======================================================================

O programa só pode ser considerado completo quando:

1. concursos possui Preparation Engine real;
2. syllabus possui evidências;
3. mastery é auditável;
4. Radar/Impact Analysis funcionam;
5. questions intelligence funciona;
6. Strategy Engine existe;
7. exam/simulado alimenta estratégia;
8. Tutor utiliza contexto real;
9. LifeState agrega módulos;
10. Global Planner arbitra prioridades;
11. Finance possui forecasting;
12. Training possui intelligence;
13. Nutrition possui intelligence;
14. eventos alimentam automações;
15. briefing é cross-domain;
16. Command Center apresenta próxima ação;
17. Agent é contextual;
18. Why funciona;
19. Audit funciona;
20. todos os módulos continuam operacionais.

======================================================================
142. O QUE NÃO IMPLEMENTAR AGORA
======================================================================

Não adicionar por conta própria:

- pagamento;
- marketplace;
- rede social;
- gamificação pública;
- ranking entre usuários;
- corretora;
- banking;
- smartwatch;
- Apple Health;
- Google Fit;
- Health Connect;
- novos provedores pagos;
- infraestrutura paga;
- scraping de sites protegidos;
- pgvector apenas por hype.

Podem ser futuros projetos.

======================================================================
143. ORQUESTRAÇÃO DAS FASES
======================================================================

Começar AGORA pela FASE 1.

Depois de cada fase:

Se NÃO houver migration ou configuração externa bloqueante:

- review;
- CI;
- merge;
- deploy;
- smoke;
- iniciar próxima fase automaticamente.

Se houver migration:

PARAR antes do merge.

Responder com:

MIGRATION REQUIRED

revision:
...

down_revision:
...

comando:
python -m alembic upgrade head

working directory:
backend

database:
Neon via DATABASE_URL_DIRECT

Esperar confirmação humana.

Depois continuar.

======================================================================
144. NÃO PERGUNTAR DESNECESSARIAMENTE
======================================================================

Este prompt contém decisões de produto suficientes.

Não interromper implementação para perguntar sobre:

- nomes triviais;
- cor;
- posição exata;
- nomes internos;
- pequenas decisões técnicas.

Tomar decisão coerente com arquitetura existente.

Perguntar somente quando houver:

- custo;
- billing;
- credencial;
- operação destrutiva;
- migration de produção;
- decisão realmente irreversível.

======================================================================
145. ENTREGA APÓS CADA PR
======================================================================

Responder com:

FASE:
PR:
branch:
head SHA:
merge SHA:
migration:
tests:
CI:
review:
deploy Vercel:
deploy Northflank:
health/live:
health/ready:

Implementado:
...

Métricas:
...

Limitações reais:
...

Configuração manual necessária:
...

Próxima fase:
...

======================================================================
146. HANDOFF
======================================================================

Manter HANDOFF.md atualizado.

Precisa registrar:

- última fase concluída;
- branch;
- merge;
- migrations;
- arquitetura;
- decisões;
- dívida técnica;
- próxima fase.

O próximo agente deve conseguir continuar sem reconstruir contexto.

======================================================================
147. REGRA FINAL
======================================================================

Não otimizar o Sirius para possuir mais funcionalidades.

Otimizar para:

entender
→ decidir
→ explicar
→ ajudar
→ aprender com os resultados
→ adaptar

enquanto mantém o usuário no controle.

COMECE AGORA:

1. sincronize com main;
2. confirme head;
3. audite o fluxo de edital;
4. execute FASE 1;
5. abra PR;
6. valide;
7. siga o protocolo acima;
8. continue pelas fases seguintes conforme as regras de migration.