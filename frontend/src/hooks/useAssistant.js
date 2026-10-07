import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { getApiErrorMessage } from '@/lib/api-errors';
import { getAssistantContext, setAssistantContext } from '@/lib/assistant-context';
import { cachedGet, queryClient, cacheKey, sessionVersion } from '@/lib/query-cache';
import { deliveryError, mergeReply } from '@/lib/assistant-delivery';

const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api`;

export function useAssistant(page, enabled = true, context = {}) {
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);
  const pending = useRef(null);
  const generation = useRef(0);
  const aborter = useRef(null);
  const [conversationId, setConversationId] = useState(() => sessionStorage.getItem('sirius-conversation') || 'primary');
  const [conversations, setConversations] = useState([]);
  const [selection, setSelection] = useState(() => getAssistantContext(conversationId));
  const attachment = selection.attachment;
  const setAttachment = useCallback(value => setAssistantContext(conversationId, { attachment: value }), [conversationId]);
  const contextKey = JSON.stringify(context);
  useEffect(() => {
    if (enabled && contextKey !== '{}') setAssistantContext(conversationId, { context: JSON.parse(contextKey) });
  }, [enabled, contextKey, conversationId]);
  useEffect(() => {
    const sync = () => setSelection(getAssistantContext(conversationId));
    sync(); window.addEventListener('sirius-context-updated', sync);
    return () => window.removeEventListener('sirius-context-updated', sync);
  }, [conversationId]);
  const refresh = useCallback(async event => {
    if (busy.current) return;
    if (event?.detail?.messages) {
      if (event.detail.conversationId === (sessionStorage.getItem('sirius-conversation') || 'primary')) setMessages(event.detail.messages);
      if (event.detail.conversations) setConversations(event.detail.conversations);
      return;
    }
    const version = ++generation.current;
    try {
      const selected = sessionStorage.getItem('sirius-conversation') || 'primary';
      setConversationId(selected);
      if (event?.type === 'click') {
        await queryClient.invalidateQueries({ queryKey: cacheKey(`/ai/conversation?conversation_id=${encodeURIComponent(selected)}`), refetchType: 'none' });
        await queryClient.invalidateQueries({ queryKey: cacheKey('/ai/conversations'), refetchType: 'none' });
      }
      const snapshot = queryClient.getQueryData(cacheKey(`/ai/conversation?conversation_id=${encodeURIComponent(selected)}`));
      if (snapshot && !pending.current) setMessages(snapshot.messages || []);
      const [data, recent] = await Promise.all([
        cachedGet(`/ai/conversation?conversation_id=${encodeURIComponent(selected)}`), cachedGet('/ai/conversations'),
      ]);
      if (version === generation.current && !busy.current) {
        const delivered = new Set((data.messages || []).map(m => m.request_id).filter(Boolean));
        if (pending.current && delivered.has(pending.current.request_id)) pending.current = null;
        setMessages(previous => [...(data.messages || []), ...previous.filter(m => m.delivery_error && !delivered.has(m.request_id))]);
        setConversations(recent); setError('');
      }
    } catch (err) {
      if (version === generation.current) setError(getApiErrorMessage(err, 'Não foi possível carregar a conversa.'));
    }
  }, []);
  useEffect(() => {
    if (!enabled) return;
    refresh();
    window.addEventListener('sirius-conversation-updated', refresh);
    return () => {
      const id = pending.current?.request_id;
      if (id) setMessages(previous => previous.map(m => m.message_id === `pending-${id}` ? { ...m, delivery_error: 'Resposta interrompida. Sua mensagem foi preservada.' } : m));
      generation.current += 1; aborter.current?.abort(); window.removeEventListener('sirius-conversation-updated', refresh);
    };
  }, [enabled, refresh]);
  useEffect(() => {
    const reset = () => { setAttachment(null); generation.current += 1; aborter.current?.abort(); window.speechSynthesis?.cancel(); setMessages([]); setConversations([]); pending.current = null; setError(''); sessionStorage.removeItem('sirius-conversation'); setConversationId('primary'); };
    window.addEventListener('sirius-auth-changed', reset);
    const storageReset = event => { if (!event.key || event.key === 'sirius_session_token') reset(); };
    window.addEventListener('storage', storageReset);
    return () => { window.removeEventListener('sirius-auth-changed', reset); window.removeEventListener('storage', storageReset); };
  }, [setAttachment]);
  const send = useCallback(async text => {
    if (busy.current || !text.trim()) return false;
    if (pending.current && pending.current.message !== text) { setError('Tente enviar novamente a mensagem pendente ou abra uma nova conversa.'); return false; }
    busy.current = true;
    const version = ++generation.current;
    setSending(true); setError('');
    aborter.current = new AbortController();
    if (!pending.current) pending.current = {
      message: text, request_id: crypto.randomUUID(), conversation_id: conversationId, page,
      page_context: JSON.stringify({ title: document.title, query: window.location.search.slice(0, 1000), ...(selection.context || context), attachment_id: attachment?.attachment_id || selection.context?.attachment_id || context.attachment_id, draft: undefined }),
    };
    const attempt = pending.current;
    const id = `pending-${attempt.request_id}`;
    const ownerVersion = sessionVersion();
    const userMessage = { message_id: id, request_id: attempt.request_id, role: 'user', content: text };
    setMessages(previous => [...previous.filter(m => m.message_id !== id), userMessage]);
    try {
      const { data } = await axios.post(`${API}/ai/chat`, attempt, { withCredentials: true, timeout: 160000, signal: aborter.current.signal });
      if (version !== generation.current || ownerVersion !== sessionVersion()) return false;
      const known = queryClient.getQueryData(cacheKey(`/ai/conversation?conversation_id=${encodeURIComponent(conversationId)}`));
      const updated = mergeReply(known?.messages || messages, data, id);
      setMessages(updated);
      queryClient.setQueryData(cacheKey(`/ai/conversation?conversation_id=${encodeURIComponent(conversationId)}`), { messages: updated });
      const recent = [{ conversation_id: conversationId, title: text.slice(0, 80) }, ...conversations.filter(c => c.conversation_id !== conversationId)];
      setConversations(recent); queryClient.setQueryData(cacheKey('/ai/conversations'), recent);
      pending.current = null;
      window.dispatchEvent(new CustomEvent('sirius-conversation-updated', { detail: { conversationId, messages: updated, conversations: recent } }));
      return true;
    } catch (err) {
      if (version !== generation.current || ownerVersion !== sessionVersion()) return false;
      const message = axios.isCancel(err) ? 'Resposta interrompida. Sua mensagem foi preservada.' : deliveryError(err);
      setError(message); setMessages(previous => previous.map(m => m.message_id === id ? { ...m, delivery_error: message } : m));
      return false;
    } finally { busy.current = false; setSending(false); }
  }, [page, conversationId, context, attachment, selection, messages, conversations]);
  const retry = useCallback(() => pending.current ? send(pending.current.message) : false, [send]);
  const cancel = useCallback(() => {
    const id = pending.current?.request_id;
    if (id) axios.post(`${API}/ai/cancel/${id}`, {}, { withCredentials: true }).catch(() => {});
    aborter.current?.abort();
  }, []);
  const selectConversation = useCallback(id => {
    if (busy.current) return;
    sessionStorage.setItem('sirius-conversation', id); setConversationId(id); setMessages([]); setError(''); pending.current = null;
    window.dispatchEvent(new Event('sirius-conversation-updated'));
  }, []);
  const newConversation = useCallback(() => selectConversation(crypto.randomUUID()), [selectConversation]);
  return { messages, sending, error, send, retry, refresh, cancel, conversations, conversationId, selectConversation, newConversation, attachment, setAttachment };
}
