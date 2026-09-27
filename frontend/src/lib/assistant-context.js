// In-memory only: compact and expanded surfaces share context, never across accounts.
const selections = new Map();
export const getAssistantContext = id => selections.get(id) || {};
export function setAssistantContext(id, patch) {
  selections.set(id, { ...getAssistantContext(id), ...patch });
  if (selections.size > 30) selections.delete(selections.keys().next().value);
  window.dispatchEvent(new Event('sirius-context-updated'));
}
const clear = () => { selections.clear(); window.dispatchEvent(new Event('sirius-context-updated')); };
window.addEventListener('sirius-auth-changed', clear);
window.addEventListener('storage', event => { if (!event.key || event.key === 'sirius_session_token') clear(); });
