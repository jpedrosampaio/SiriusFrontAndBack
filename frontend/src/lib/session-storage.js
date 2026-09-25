// Private drafts are namespaced by the authenticated user. Storage can be
// unavailable (private browsing / quota); callers must show that state.
export function readSaved(key, fallback = null) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
export function writeSaved(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
}
export function remainingSeconds(state, now = Date.now()) {
  return state.isRunning && !state.isPaused && state.deadline
    ? Math.max(0, Math.ceil((state.deadline - now) / 1000)) : state.timeLeft;
}
export function newSessionId() { return crypto.randomUUID(); }
