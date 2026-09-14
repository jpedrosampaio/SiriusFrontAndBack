# Reliability corrections: private cache, Kanban and Gemini

This PR follows the sync/Telegram security PR.

- The service worker no longer stores or serves API responses, including auth/me.
  Requests to /api and requests carrying Authorization bypass both CacheStorage
  and the browser HTTP cache. Activation removes old Sirius API/static caches.
  Static app assets remain available offline; personal API data requires a network
  connection. Account-isolated offline storage is not implemented by this patch.
- Navigations try fresh HTML first, with an offline shell fallback.
- Task listings return the daily instance status (todo, in_progress, done).
  Checkbox completion also persists status. Legacy completion-only records work.
  Task instances are loaded in one user/date-scoped batch instead of one query per task.
- Gemini HTTP operations (text, PDFs, upload/polling, key validation and edital chat)
  run via asyncio.to_thread. Existing requests payloads, retries and timeout/error
  semantics remain in place. call_llm now forwards user_id for successful-call tracking.

The worker pool is bounded by Python's default executor. Cancelling a coroutine
does not stop a requests call already running in a worker; its existing timeout
still applies. This is not an async job queue or a complete conversion of all
external services. Other synchronous I/O and CPU-heavy PDF work remain outside scope.

Validation uses real selected Python route/helper definitions, simulated services,
and Node's built-in test runner executing the service worker in a VM with browser
API doubles. No production data or paid AI calls are used. Real-browser/mobile
offline behavior and full MongoDB concurrency are not covered.

No database migration or new environment variable is required. Existing cached
personal responses are discarded when the updated service worker activates.
