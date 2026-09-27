// Context is a navigation hint. The server must validate all referenced records.
export function openSirius(context = {}) {
  window.dispatchEvent(new CustomEvent('sirius-open', { detail: context }));
}
