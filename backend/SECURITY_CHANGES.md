# Security corrections: sync and Telegram

## Scope

The sync API only exposes tasks, habits, transactions and goals, matching the
current mobile data service. Internal collections (including users, user_sessions,
and Telegram configuration) return 403. Every database write includes the
authenticated user_id; IDs and owners supplied in the payload cannot disagree.
Unknown fields and operations return 422. UPDATE requires an existing owned record;
INSERT remains retryable. Task XP rewards cannot be changed through sync.
Reads use an explicit field projection, excluding unexpected private fields.

The existing mobile client's PUT/DELETE transport and SQLite merge issues are
separate outstanding bugs; this patch does not claim complete offline sync support.
Other collections are deliberately unavailable until dedicated sync contracts exist.

## Telegram

The bot remains disabled as in the existing source. These changes do not enable it
or send messages during tests. If Telegram is enabled in a later change:

- Set BACKEND_PUBLIC_URL to the trusted HTTPS backend URL in Render.
- Set TELEGRAM_BOT_WEBHOOK_SECRET to a random 32-256 character value using
  letters, digits, underscore and hyphen. The existing .env.example already names it.
- Webhook registration happens only on server startup. It uses
  /api/telegram/webhook and Telegram's X-Telegram-Bot-Api-Secret-Token header.
- The old token-in-path callback is removed. Startup must successfully register
  the new callback before Telegram delivery resumes.
- Browser calls to /api/telegram/setup-webhook now return 403 after authentication.
  The frontend no longer attempts global bot configuration.
- Manual summary requests only address the authenticated user's links.
- If a bot token was previously exposed, rotate it in BotFather separately.
  Repository edits do not rotate deployed credentials.

Do not commit environment values. No database migration is required.

## Validation

Run:
python -m unittest discover -s backend/tests -p test_security_routes.py -v

The tests load the actual route/model definitions from server.py using AST to avoid
initializing MongoDB, AI providers or app startup. HTTP requests run through real
FastAPI/Pydantic with HTTPX ASGITransport; MongoDB and Telegram are test doubles.
The suite covers authorization, collection restrictions, payload validation,
ownership, projections, partial updates, deletes and webhook setup/authentication.

These tests do not replace MongoDB integration, complete frontend builds, native
mobile tests, or a deployment smoke test. GitHub Actions runs this focused suite
and checks backend Python syntax without production credentials.
