import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { getApiErrorMessage } from '@/lib/api-errors';

const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api`;

export function useAssistant(page, enabled = true) {
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);
  const pending = useRef(null);
  const generation = useRef(0);
  const aborter = useRef(null);
  const [conversationId, setConversationId] = useState(() => sessionStorage.getItem('sirius-conversation') || 'primary');
  const [conversations, setConversations] = useState([]);
  const refresh = useCallback(async () => {
    if (busy.current) return;
    const version = ++generation.current;
    try {
      const selected = sessionStorage.getItem('sirius-conversation') || 'primary';
      setConversationId(selected);
      const { data } = await axios.get(`${API}/ai/conversation`, { params: { conversation_id: selected }, withCredentials: true });
      if (version === generation.current && !busy.current) { setMessages(data.messages || []); setError(''); }
      const recent = await axios.get(`${API}/ai/conversations`, { withCredentials: true });
      if (version === generation.current) setConversations(recent.data);
    } catch (err) {
      if (version === generation.current) setError(getApiErrorMessage(err, 'Não foi possível carregar a conversa.'));
    }
  }, []);
  useEffect(() => {
    if (!enabled) return;
    refresh();
    window.addEventListener('sirius-conversation-updated', refresh);
    return () => { generation.current += 1; aborter.current?.abort(); window.removeEventListener('sirius-conversation-updated', refresh); };
  }, [enabled, refresh]);
  useEffect(() => {
    const reset = () => { generation.current += 1; aborter.current?.abort(); window.speechSynthesis?.cancel(); setMessages([]); setConversations([]); pending.current = null; sessionStorage.removeItem('sirius-conversation'); setConversationId('primary'); };
    window.addEventListener('sirius-auth-changed', reset);
    const storageReset = event => { if (!event.key || event.key === 'sirius_session_token') reset(); };
    window.addEventListener('storage', storageReset);
    return () => { window.removeEventListener('sirius-auth-changed', reset); window.removeEventListener('storage', storageReset); };
  }, []);
  const send = useCallback(async text => {
    if (busy.current || !text.trim()) return false;
    busy.current = true;
    const version = ++generation.current;
    setSending(true); setError('');
    aborter.current = new AbortController();
    if (!pending.current || pending.current.message !== text) pending.current = { message: text, request_id: crypto.randomUUID() };
    const userMessage = { message_id: 'pending', role: 'user', content: text };
    setMessages(previous => [...previous.filter(m => m.message_id !== 'pending'), userMessage]);
    try {
      const { data } = await axios.post(`${API}/ai/chat`, {
        ...pending.current, conversation_id: conversationId, page,
        page_context: JSON.stringify({ title: document.title, query: window.location.search.slice(0, 1000) }),
      }, { withCredentials: true, timeout: 160000, signal: aborter.current.signal });
      if (version !== generation.current) return false;
      setMessages(previous => [...previous.filter(m => m.message_id !== 'pending'), data.user_message, data.ai_message]);
      pending.current = null;
      window.dispatchEvent(new Event('sirius-conversation-updated'));
      return true;
    } catch (err) {
      if (version !== generation.current) return false;
      if (axios.isCancel(err)) { setError('Geração cancelada. Sua mensagem foi preservada.'); setMessages(previous => previous.filter(m => m.message_id !== 'pending')); return false; }
      const message = getApiErrorMessage(err, 'Não foi possível responder. Tente novamente; sua mensagem foi preservada.');
      setError(message); setMessages(previous => previous.filter(m => m.message_id !== 'pending'));
      if (message.includes('Configure sua chave')) window.dispatchEvent(new Event('open-gemini-key-modal'));
      return false;
    } finally { busy.current = false; setSending(false); }
  }, [page, conversationId]);
  const cancel = useCallback(() => {
    const id = pending.current?.request_id;
    if (id) axios.post(`${API}/ai/cancel/${id}`, {}, { withCredentials: true }).catch(() => {});
    aborter.current?.abort();
  }, []);
  const selectConversation = useCallback(id => {
    if (busy.current) return;
    sessionStorage.setItem('sirius-conversation', id); setConversationId(id); setMessages([]); pending.current = null;
    window.dispatchEvent(new Event('sirius-conversation-updated'));
  }, []);
  const newConversation = useCallback(() => selectConversation(crypto.randomUUID()), [selectConversation]);
  return { messages, sending, error, send, refresh, cancel, conversations, conversationId, selectConversation, newConversation };
}
