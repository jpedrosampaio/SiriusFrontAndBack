# Sirius Study App — PRD (Análise de Edital — Precisão + UX)

## Problem statement (user, PT-BR)
> Funcionou, porém ainda está demorando bastante. A aplicação retornou dados errados,
> trouxe 2 cargos em um edital que na verdade tem 13 perfis. Eu preciso de uma análise
> perfeita, sem margem de erros, e que se adapte aos diferentes tipos de editais.
> Além disso, aplique as melhorias que você sugeriu. Também, verifique a barrinha que
> informa "Analisando Edital", ela meio que fica travada, seria interessante que a
> bolinha ficasse rodando.

## Sessão anterior (Bug Fix Gemini)
- Corrigidos modelos Gemini descontinuados/quotados. Cascata atual:
  `gemini-2.5-flash → gemini-flash-latest → gemini-flash-lite-latest`.

## Melhorias desta sessão

### Backend (`/app/backend/server.py`)
1. **Structured Output (Gemini JSON Schema)** em `call_gemini_with_pdf`
   → JSON válido garantido pelo Google antes de emitir, sem mais parse errors.
2. **`thinkingConfig.thinkingBudget = 0`** e **`temperature = 0`** no `gemini-2.5-flash`
   → 3–5× mais rápido (~12 s para edital de 13 perfis) e resultado determinístico.
3. **Prompt reforçado + pré-scan** de linhas do PDF contendo "cargo/perfil/especialização/
   área de atuação/vagas" — injetadas como pistas, obriga a IA a **enumerar TODOS**.
4. **Cache por hash SHA-256 do PDF** por usuário → re-upload do mesmo edital retorna em
   ~6 ms sem consumir quota Gemini.
5. **Novo endpoint** `POST /api/auth/test-gemini-key`
   - Testa a chave salva (ou uma nova) contra Google Gemini em ~500 ms
   - Retorna: `valid`, `status` (ok / quota_exceeded / invalid / timeout / network),
     `latency_ms`, `model`, mensagem legível.
6. **`multiple_cargos`** agora derivado do tamanho de `cargos[]` (evita bug do modelo
   marcar `false` mesmo com múltiplos cargos).
7. Timeout unificado a 180s por modelo (era 300/240/180).

### Frontend
- **`/app/frontend/src/pages/Profile.js`**
  - Botão **"Testar Chave"** (com e sem edição) + estado `geminiKeyStatus`.
  - Novo componente `<GeminiStatusPill>` com ícone/cor por status (ok/quota/inválida/etc.)
    e exibe latência do teste.
- **`/app/frontend/src/pages/Studies.js`**
  - Novo componente `<EditalAnalyzeProgress>`:
    - Anel CSS animado (`animate-spin`) que **nunca trava** durante espera.
    - Barra indeterminada com keyframe `editalSlide` (independente do render React).
    - Fases visíveis: `upload → extract → cargos` (dots iluminam progressivamente).
    - Contador de segundos decorridos (atualizado via `setInterval` a cada 250ms).
  - `handleAnalyzeEdital` atualiza fase e captura `res.data.cached` para toast.

## Validação E2E (backend, chave real do usuário)

| Cenário | Resultado |
|---|---|
| Edital 13 perfis (Petrobras sintético) | ✅ **13 de 13** cargos extraídos em **12.5 s** |
| Re-upload mesmo PDF | ✅ **6 ms** (cache) |
| Chave Gemini válida (`test-gemini-key`) | ✅ 552 ms |
| Chave Gemini inválida | ✅ Detectada em 46 ms com mensagem clara |

## Next Action Items
- **Redeploy backend no Render** (`sirius-backend-1hsi`) — só arquivos alterados: `server.py`.
- Frontend será redeployado automaticamente via Vercel/Netlify pipeline do usuário.

## Backlog / Próximas melhorias
- P1: **Persistir cache global** (por hash de PDF, sem `user_id`) → dois usuários
  enviando o mesmo edital compartilham o resultado, economizando quota Gemini.
- P1: **Análise assíncrona em fila (Celery/RQ)** para editais >100 páginas: retorna
  imediatamente com `analysis_id` e front faz polling em `/analyze-status/{id}`.
- P2: **Dedup automático de cargos** por similaridade de nome (fuzzy match) — protege
  contra o caso raro de o modelo listar o mesmo cargo com grafias ligeiramente diferentes.
- P2: **Diff visual** entre 2 editais (útil para comparar edital atual vs anterior).
