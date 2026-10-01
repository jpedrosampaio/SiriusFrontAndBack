# Modelo relacional — fundação em desenvolvimento

O schema atual da branch tem 62 tabelas. Não é ainda o schema completo de todos os módulos; o mapa de trabalho está em [DATABASE_REDESIGN_MAP.md](DATABASE_REDESIGN_MAP.md). O runtime de produção ainda não foi trocado.

```mermaid
erDiagram
    users ||--o{ user_sessions : autentica
    users ||--o{ activity_receipts : deduplica
    users ||--o{ tasks : possui
    tasks ||--o{ task_instances : ocorre
    users ||--o{ habits : possui
    habits ||--o{ habit_checks : registra
    users ||--o{ financial_transactions : registra
    finance_categories |o--o{ financial_transactions : classifica
    study_areas ||--o{ study_programs : organiza
    study_programs ||--o| study_targets : identifica
    study_programs |o--o{ study_notebooks : prepara
    study_notebooks ||--o{ study_topics : contem
    study_notebooks ||--o{ study_sessions : registra
    study_topics |o--o{ question_attempts : evidencia
    study_topics ||--o{ study_review_events : revisa
    questions |o--o{ question_attempts : responde
    exams ||--o{ exam_questions : organiza
    questions ||--o{ exam_questions : participa
    exams ||--o{ exam_attempts : realiza
    exam_attempts |o--o{ question_attempts : detalha
    flashcards ||--o{ flashcard_reviews : revisa
    workout_plans ||--o{ workout_plan_days : organiza
    workout_plan_days ||--o{ plan_exercises : prescreve
    workout_plans ||--o{ workout_sessions : executa
    workout_sessions ||--o{ session_exercises : registra
    session_exercises ||--o{ workout_sets : detalha
    workout_sessions |o--o| workout_logs : conclui
    meals ||--o{ meal_items : contem
    ai_conversations ||--o{ ai_messages : contem
    ai_actions ||--o{ ai_action_audit : audita
    files |o--o{ edital_analyses : origina
    rag_sources ||--o{ rag_chunks : indexa
```

Os vínculos entre entidades privadas incluem `user_id` na FK, além do ID da entidade. Uma FK simples para users também existe nas tabelas privadas. Consultas continuam filtrando propriedade; a FK é defesa adicional.

QuestionAttempt preserva total/correct para fatos agregados e resposta/duração para tentativas individuais. StudySession preserva minutos, origem, início/término quando conhecidos. ReviewEvent e FlashcardReview são eventos, não apenas próximas datas. Nenhuma coluna de mastery substitui esses fatos.

Plano de treino preserva dia/semana/ordem, exercícios prescritos e uma cópia relacional na sessão. Alterações futuras da prescrição não reescrevem os fatos da sessão. Sets executados têm linhas próprias. Refazer uma confirmação usa recibo e não duplica o log.

Dinheiro usa NUMERIC(18,2); relatórios somam no SQL. `budgets.limit` guarda limite, enquanto gasto deve ser calculado das transações. Calendário usa instantes UTC e aplica timezone do usuário ao converter dia/minuto da API.

JSONB contém estruturas variáveis (evidência, parâmetros de IA, análise de edital, preferências e resultados). Campos de proprietário, IDs, datas, status, valores, mensagens e tentativas são relacionais. Arquivos têm somente metadata/referências; bytes não estão no schema.

CASCADE é usado para sessões de autenticação e índices de conteúdo descartáveis. Relações de histórico usam RESTRICT. Exclusões visíveis ao usuário ainda precisam ser adaptadas para preservar histórico sem gerar erros de constraint no frontend.
## Integração financeira adicional

Revisão `0e61828b3519` acrescenta `card_purchases`, `card_invoices`,
`financial_projections` e `monthly_bills` (60 tabelas no total). São entidades
tipadas, com NUMERIC(18,2), datas civis e referências compostas por proprietário.
Transações referenciam compra ou conta quando aplicável; parcelas futuras referenciam
a compra mesmo quando ainda não existe uma transação paga. Contas importadas de
projeções têm unicidade por usuário/projeção; pagamentos têm unicidade por conta.
Categorias passam a preservar ícone e cor usados pela interface.

Tarefas/hábitos usam `archived_at`; `task_instances` exige coerência entre status e
completed. Essas alterações correspondem à migração anterior `d18c704a928e`.

## Análises e fila de editais

`edital_analyses` separa identidade, hash, nome do arquivo, texto, páginas, versão, revisão de conferência e expiração da análise estruturada. `edital_jobs` persiste status, lease, referência de storage e resultado; FK composta impede ligar análise de outro dono. Excluir a análise limpa a referência no job e revoga suas fontes RAG. Binários não ficam no banco.

`study_schedules` guarda blocos semanais com horários tipados e FK de caderno/dono. `study_programs.edital_data` é o snapshot estruturado de concurso/cargo/estratégia/fonte da importação, não armazenamento genérico de documentos; as disciplinas, tópicos, sessões e blocos ficam normalizados. Campos de fonte/status dos pesos e questões pertencem ao caderno.
