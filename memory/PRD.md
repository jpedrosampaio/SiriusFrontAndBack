# Sirius Study App — PRD (bugfix: 500 após Gemini 200 + speed)

## Problema desta sessão
Análise de edital em produção retornava 500 **após** Gemini responder 200:
```
13:22:51  Gemini PDF call (model=gemini-2.5-flash, timeout=180s): status=200
13:22:51  POST /api/study/programs/analyze-edital  500 Internal Server Error
```
Além disso o request levou ~2m37s no total.

## Causa raiz (inferida dos logs)
- `maxOutputTokens=32000` era insuficiente para editais reais com 30+ cargos e conteúdo
  programático completo → resposta cortada em `finishReason: MAX_TOKENS`.
- `json.loads` explodia no JSON truncado, subia para o `except Exception` genérico
  que **não logava traceback** — 500 opaco.
- Etapa de upload separado (Gemini Files API) adicionava 20–30 s a cada request.

## Correções (`/app/backend/server.py`)

### Robustez / observabilidade
1. **`maxOutputTokens`** subiu de 32 000 → **65 536** (limite do 2.5-flash).
2. `call_gemini_with_pdf` agora loga `finishReason`, `text_len`, `parts` e, se `MAX_TOKENS`,
   tenta o próximo modelo (com fallback a devolver texto truncado + `error_type="truncated"`).
3. Novo helper **`_try_repair_json(s)`**: recupera JSON truncado mid-array cortando no
   último `}` de cargo bem-formado e fechando `]}`. Testes unitários confirmam recuperação
   com aspas escapadas, arrays aninhados e trailing garbage.
4. `analyze_edital_cargos` agora aplica o repair antes de desistir; se falhar, retorna
   HTTP 500 com **mensagem clara** (`"IA devolveu JSON incompleto..."`) em vez de opaca.
5. `except Exception as e:` no endpoint agora loga com `exc_info=True` e devolve
   `f"{type(e).__name__}: {str(e)[:200]}"` no detail — nunca mais 500 mudo.
6. Mensagens de erro específicas por tipo: `quota` / `invalid` / `timeout` / `truncated`,
   incluindo link https://aistudio.google.com/apikey quando aplicável.

### Performance
7. **PDF INLINE (base64) para arquivos ≤15 MB** — pula a Files API completamente.
   - Elimina o roundtrip de upload (~5–25 s dependendo do tamanho e latência).
   - Só usa Files API acima de 15 MB (nosso limite é 20 MB).
   - Log identifica qual modo foi usado: `sending INLINE (X KB)` vs `sending via FILE URI (Y MB)`.

## Validação
- Testes unitários do `_try_repair_json`: 4 cenários (válido / truncado mid-array /
  totalmente inválido / com aspas escapadas) — todos passam.
- Cache hit em PDF já analisado: **6 ms**, 13 cargos ✅.
- Backend reinicia limpo (`Application startup complete`).

## Next Action Items (deploy)
- Redeploy backend no Render (`sirius-backend-1hsi`). Nenhuma env-var nova.
- Reenvie o edital que estava falhando — agora se der problema teremos log detalhado.
- Ainda precisa cadastrar uma **nova chave Gemini** (a antiga foi revogada pelo Google).

## Backlog remanescente
- Cache global por hash de PDF (compartilhado entre usuários).
- Fila assíncrona (Celery/RQ) para editais >100 páginas.
- Índice `edital_analyses.pdf_hash` no MongoDB.
- Alertas de quota ≥80%.
- Export do comparativo em PDF.
