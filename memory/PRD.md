# Sirius Study App — PRD (bugfix Gemini payload / 400+404)

## Problema desta iteração
Logs do usuário (chave nova):
```
Gemini PDF: sending INLINE (1109 KB) — sem upload API
Gemini PDF call (model=gemini-2.5-flash,      status=404      (chave sem acesso)
Gemini PDF call (model=gemini-flash-latest,   status=400 INVALID_ARGUMENT
POST /api/study/programs/analyze-edital  500 Internal Server Error
```

## Causa raiz
1. **404 no gemini-2.5-flash**: chave nova (recém-criada) não tem acesso a esse modelo específico. Google só libera após alguns minutos ou dependendo da região/projeto.
2. **400 INVALID_ARGUMENT no flash-latest**: o campo `thinkingConfig` só é aceito por modelos da família 2.5. Ao mandar para `flash-latest`, Google devolve 400.

## Correção (`/app/backend/server.py` → `call_gemini_with_pdf`)
Payload agora é montado **por modelo**, com fallback progressivo em 2 tentativas por modelo:

| Modelo | Tentativa 1 (qualidade) | Tentativa 2 (fallback) |
|---|---|---|
| `gemini-2.5-flash`      | `thinkingConfig` + `responseSchema` | sem ambos |
| `gemini-flash-latest`   | apenas `responseSchema` (sem thinking) | sem schema também |
| `gemini-flash-lite-latest` | apenas `responseSchema` | sem schema |

Fluxo de status codes:
- **404** → modelo indisponível → próximo modelo (não retenta).
- **400** → retry no mesmo modelo sem `thinkingConfig`/`responseSchema`; se ainda 400 → próximo modelo.
- **429** → cota esgotada → próximo modelo.
- **200 MAX_TOKENS** → resposta truncada → próximo modelo (ou aplica `_try_repair_json` se for a última).
- **200 empty** → safety filter → próximo modelo.

Logs agora incluem `attempt`, `schema`, `thinking` para facilitar debug.

## Priorização qualidade > velocidade
- `gemini-2.5-flash` continua sendo o **primário** (melhor qualidade + `responseSchema`).
- `thinkingBudget=0` ainda aplicado ao 2.5-flash → rápido sem perder qualidade.
- `maxOutputTokens=65536` (limite do modelo) → suporta editais gigantes.
- Se 2.5-flash não estiver disponível, cai para `flash-latest` (mesma qualidade geral, sem thinking).
- Como último recurso `flash-lite-latest` (mais rápido, um pouco menos preciso).

## Validação
- Payload builder unitário: 4/4 cenários corretos (thinking só em 2.5, retry limpa ambos).
- Cache hit: 5ms, 13 cargos ✅.
- Backend reinicia limpo.

## Sobre o "gemini-2.5 timeou mas latest foi rápido"
Isso acontece porque `2.5-flash` executa "thinking" por padrão (nós desligamos), então quando `responseSchema` é enviado sem `thinkingBudget=0` explícito, ele pode gastar minutos internamente. Já `flash-latest` não faz thinking — é imediato. Nossa lógica atual força `thinkingBudget=0` no 2.5, o que resolve isso.

## Next Action Items
- **Redeploy backend no Render**.
- Reenvie o edital. Se der erro, os novos logs vão indicar exatamente o modelo/attempt que falhou.
- Se persistir 404 no 2.5-flash na sua chave: aguarde ~15 min após criar a chave OU crie no Google AI Studio direto (não em Cloud Console).

## Backlog
- Cache global entre usuários por hash de PDF.
- Fila assíncrona para editais >100 páginas.
- Alertas de quota ≥80%.
- Export do diff em PDF.
