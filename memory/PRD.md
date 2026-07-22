# Sirius Study App — PRD (Bug Fix Session)

## Problem statement (user, PT-BR)
> Nesta aplicação, a funcionalidade de analisar edital não está funcionando. Antes funcionava normalmente. Mas agora, além de demorar, não funciona.
> Deploy backend: https://sirius-backend-1hsi.onrender.com

## Root cause
Endpoint `POST /api/study/programs/analyze-edital` (`server.py :10173`) dependia da função `call_gemini_with_pdf` que tentava modelos Gemini nesta ordem:
`gemini-1.5-flash` → `gemini-2.0-flash` → `gemini-2.5-flash`.

Estado atual dos modelos (Jan/2026) na API gratuita Gemini:
- `gemini-1.5-flash` foi **descontinuado** pelo Google → responde **404**.
- `gemini-2.0-flash` está com **quota diária esgotada** para essa chave → **429**.
- `gemini-2.5-flash` funciona, mas era o último a ser tentado e recebia apenas ~180s de timeout residual, então o request estourava antes de responder.

Log típico:
```
Gemini PDF call (model=gemini-1.5-flash, timeout=300s): status=404
Gemini PDF call (model=gemini-2.0-flash, timeout=240s): status=429
Gemini PDF timeout for all models   → HTTP 500
```

## Fix applied (`/app/backend/server.py`)
1. `call_gemini_with_pdf` — nova cascata: `gemini-2.5-flash` → `gemini-flash-latest` → `gemini-flash-lite-latest` (aliases “latest” são mantidos automaticamente pelo Google e `flash-lite-latest` tem a maior quota diária free-tier).
2. Timeout uniforme de 120s por modelo (antes: 300/240/180 gerando ~9min de espera antes de falhar).
3. `call_gemini` (texto puro) — mesma cascata `2.5-flash / flash-latest / flash-lite-latest`.
4. `GEMINI_FALLBACK_MODEL` atualizado para `gemini-flash-latest`.

## Verification (E2E, chave real do usuário)
- `POST /api/study/programs/analyze-edital` com PDF de edital sintético → **200 OK**, JSON com concurso, banca, cargos e disciplinas corretos.
- Log: `Gemini PDF call (model=gemini-2.5-flash, timeout=120s): status=200` em ~9s.

## Next Action Items (deploy)
- Fazer redeploy do backend no Render (o arquivo alterado é `/app/backend/server.py`) para aplicar a correção em produção.
- Nenhuma variável de ambiente nova é necessária.

## Backlog / Enhancements
- P1: cache de análise de editais reprocessados (mesmo hash de PDF) para evitar reconsumo de quota Gemini.
- P2: opção “analisar em segundo plano” + notificação, para PDFs muito grandes (>50 páginas).
