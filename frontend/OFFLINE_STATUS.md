# Offline implementation status

The published entry point imports the shared HTTP client and App. Current pages
use HTTP requests directly. The SQLite hook/services are not imported by these
pages; the successful production build does not validate that unused code.

A review of the current source found these blockers before native offline sync
can be enabled:

- `@capacitor/network`, `@capacitor/core` and `@capacitor-community/sqlite` are
  imported by the native services but absent from frontend/package.json.
- `hooks/use-database.js` contains TypeScript syntax in a JavaScript file.
- Sync INSERT uses POST, but UPDATE and DELETE use PUT/DELETE routes that do not
  exist. The backend accepts all three operations through POST /api/sync/{table}.
- Merge SQL derives names such as tasks_id, while SQLite uses task_id,
  habit_id, transaction_id and goal_id.
- The queue is shared rather than tied to the authenticated account. Ownership,
  login changes, failed writes and dependent operations need explicit handling
  before pending changes can safely be acknowledged.
- Remote arrays/booleans and allowed columns need conversion for SQLite.
  Unsent local changes must not be overwritten by a pull.
- Local task completion writes the template through sync, while the online
  interface uses per-day task_instances and transactional XP. Offline completion
  must use the same replay-safe activity contract.
- Habit completion arrays written directly by sync bypass the transactional XP
  route. Reconnect behavior needs a defined event protocol as well.

This review does not enable or claim working offline synchronization. The service
worker currently caches the app shell/static assets, not private API responses.
Future offline work needs end-to-end tests for reconnect, retries, account
switches, ordering, deletion, conflict resolution and XP.
