# Sirius Study App — PRD

## Sessão atual: features 3, 4, 5 e 6 do backlog

### 3) Dedup fuzzy de cargos
- Novo helper `dedup_cargos_fuzzy(cargos, threshold=0.90)` em `server.py`.
- Normaliza nome (sem acento, sem "junior/jr/pleno/i/ii/iii/etc"), compara com
  `difflib.SequenceMatcher.ratio`. Ao mesclar, unifica disciplinas por nome.
- Aplicado dentro de `analyze_edital_cargos` (threshold 0.92 em produção).
- Validado: 5 cargos duplicados → 3 únicos ("Advogado(a) Junior" ↔ "Advogado Junior";
  "Analista de Sistemas Jr Redes" ↔ "Analista de Sistemas Junior - Redes").

### 4) Comparador de editais
- `analysis_doc.expires_at` estendido de 1h → 90d para viabilizar histórico.
- Novo endpoint `GET /api/study/programs/editais` → lista resumida (com dedup por pdf_hash).
- Novo endpoint `POST /api/study/programs/editais/compare` com body
  `{analysis_id_a, analysis_id_b}` → retorna `cargos_added / removed / changed / unchanged`
  + diff de disciplinas por cargo comum.
- Frontend: novo botão **"Comparar Editais"** ao lado do "Importar Edital"; dialog completo
  com selects, contadores coloridos (verde/vermelho/âmbar/cinza) e grupos colapsáveis.

### 5) Estimativa de quota consumida
- Nova coleção `db.gemini_usage` `{user_id, date(UTC), model, count}`, upsert idempotente.
- Helpers `track_gemini_usage(user_id, model)` e `get_gemini_usage_today(user_id)`.
- `call_gemini` e `call_gemini_with_pdf` recebem `user_id` opcional e incrementam a métrica
  em cada chamada bem-sucedida.
- Endpoint `POST /auth/test-gemini-key` agora retorna `usage_today` (por modelo, com
  `used/limit/remaining` baseado em `GEMINI_FREE_TIER_RPD`).
- Frontend: `<GeminiStatusPill>` mostra barra de progresso por modelo (verde <70%,
  âmbar 70–90%, vermelho ≥90%) + texto "X/Y req (Z restantes)".

### 6) Modo Assistente rápido (chat sobre o edital)
- `analyze_edital_cargos` agora persiste `pdf_text[:200KB]` no doc (extraído com pypdf).
- Novo endpoint `POST /api/study/programs/edital-chat` com body
  `{analysis_id, question, history?}`. Usa cascata de modelos, `temperature=0.2`,
  `thinkingBudget=0`, `systemInstruction` contendo o texto do PDF como contexto → nunca
  precisa reuploadar o PDF a cada mensagem.
- Frontend: botão **"Perguntar sobre este edital"** aparece no dialog de resultado;
  novo Dialog `<EditalChat>` com sugestões pré-prontas ("Quais cargos exigem OAB?"),
  bolhas user/model, indicador `pensando...` e Enter-to-send.

## Validação E2E (chave real revogada pelo Google após vazamento)

| Cenário | Resultado |
|---|---|
| `GET /editais` (list) | ✅ 3 editais retornados, ordenados por data |
| `POST /editais/compare` (v1 vs v2 sintético) | ✅ Summary correto: +2 −1 △1 =11 |
| `POST /edital-chat` (chave revogada) | ✅ 500 com mensagem clara "Sua chave Gemini é inválida" |
| Chat sem `question` | ✅ 400 "Informe analysis_id e question" |
| Compare A=B | ✅ 400 "Selecione dois editais diferentes" |
| `dedup_cargos_fuzzy` (unitário) | ✅ 5 duplicados → 3 únicos, disciplinas unidas |
| Test key (usage_today no payload) | ✅ Campo presente (vazio até 1ª chamada OK) |

## ⚠️ Ação necessária do usuário

**A chave `AIzaSyDmzyx50uhS8GUaSIZc50KD2NnCuGATftc` foi revogada pelo Google** — chaves
compartilhadas em texto plano são detectadas em ~1 min e desativadas automaticamente.
1. Gere uma NOVA chave em <https://aistudio.google.com/apikey>.
2. Cole em Profile → **Configurar API Key** (nunca compartilhe fora do app).
3. Clique **"Testar Chave"** para validar antes de tentar analisar um edital.

## Next Action Items (deploy)
- Redeploy backend no Render (`sirius-backend-1hsi`) — só `server.py`.
- Frontend redeploy (Vercel) — `Profile.js`, `Studies.js`.

## Backlog / Backlog remanescente
- P1: Cache global de análise por hash (compartilhado entre usuários, zera quota redundante).
- P1: Análise assíncrona em fila (Celery/RQ) para editais >100 páginas + polling.
- P2: Índice sobre `edital_analyses.pdf_hash` no MongoDB para acelerar cache lookup.
