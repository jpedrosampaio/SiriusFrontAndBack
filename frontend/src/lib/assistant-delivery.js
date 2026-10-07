export function deliveryError(error) {
  const status = error?.response?.status;
  const messages = {
    401: 'Sua sessão expirou. Entre novamente para continuar.',
    409: 'Esta conversa está ocupada. Aguarde um momento e tente novamente.',
    429: 'O limite de uso foi atingido. Aguarde antes de tentar novamente.',
    503: 'O assistente está temporariamente indisponível. Tente novamente em instantes.',
    504: 'A resposta demorou mais que o esperado. Tente novamente; sua mensagem está preservada.',
  };
  if (messages[status]) return messages[status];
  if (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT') return messages[504];
  if (!error?.response) return 'Não foi possível conectar ao assistente. Confira sua conexão e tente novamente.';
  return 'Não foi possível responder. Sua mensagem foi preservada para tentar novamente.';
}
export function mergeReply(messages, reply, pendingId) {
  const ids = new Set([pendingId, reply.user_message.message_id, reply.ai_message.message_id]);
  return [...messages.filter(m => !ids.has(m.message_id)), reply.user_message, reply.ai_message].slice(-200);
}

export function mergeHistory(history, current = []) {
  const ids = new Set(history.map(m => m.message_id));
  const receipts = new Set(history.map(m => m.request_id).filter(Boolean));
  return [...history, ...current.filter(m => !ids.has(m.message_id) && !(m.message_id?.startsWith('pending-') && receipts.has(m.request_id)))].slice(-200);
}

export function mergeConversations(current = [], hydration = []) {
  const ids = new Set(current.map(c => c.conversation_id));
  const known = new Map(hydration.map(c => [c.conversation_id, c]));
  return [...current.map(c => ({ ...known.get(c.conversation_id), ...c, title: known.get(c.conversation_id)?.title || c.title })), ...hydration.filter(c => !ids.has(c.conversation_id))].slice(0, 30);
}
