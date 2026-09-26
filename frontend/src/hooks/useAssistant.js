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
  const refresh = useCallback(async () => {
    if (busy.current) return;
    const version = ++generation.current;
    try {
      const { data } = await axios.get(`${API}/ai/conversation`, { withCredentials: true });
      if (version === generation.current && !busy.current) { setMessages(data.messages || []); setError(''); }
    } catch (err) {
      if (version === generation.current) setError(getApiErrorMessage(err, 'Não foi possível carregar a conversa.'));
    }
  }, []);
  useEffect(() => {
    if (!enabled) return;
    refresh();
    window.addEventListener('sirius-conversation-updated', refresh);
    const reset = () => { generation.current += 1; setMessages([]); pending.current = null; };
    window.addEventListener('sirius-auth-changed', reset);
    const storageReset = event => { if (!event.key || event.key === 'sirius_session_token') reset(); };
    window.addEventListener('storage', storageReset);
    return () => { generation.current += 1; window.removeEventListener('sirius-conversation-updated', refresh); window.removeEventListener('sirius-auth-changed', reset); window.removeEventListener('storage', storageReset); };
  }, [enabled, refresh]);
  const send = useCallback(async text => {
    if (busy.current || !text.trim()) return false;
    busy.current = true;
    const version = ++generation.current;
    setSending(true); setError('');
    if (!pending.current || pending.current.message !== text) pending.current = { message: text, request_id: crypto.randomUUID() };
    const userMessage = { message_id: 'pending', role: 'user', content: text };
    setMessages(previous => [...previous.filter(m => m.message_id !== 'pending'), userMessage]);
    try {
      const { data } = await axios.post(`${API}/ai/chat`, {
        ...pending.current, conversation_id: 'primary', page,
        page_context: JSON.stringify({ title: document.title, query: window.location.search.slice(0, 1000) }),
      }, { withCredentials: true, timeout: 300000 });
      if (version !== generation.current) return false;
      setMessages(previous => [...previous.filter(m => m.message_id !== 'pending'), data.user_message, data.ai_message]);
      pending.current = null;
      window.dispatchEvent(new Event('sirius-conversation-updated'));
      return true;
    } catch (err) {
      if (version !== generation.current) return false;
      const message = getApiErrorMessage(err, 'Não foi possível responder. Tente novamente; sua mensagem foi preservada.');
      setError(message); setMessages(previous => previous.filter(m => m.message_id !== 'pending'));
      if (message.includes('Configure sua chave')) window.dispatchEvent(new Event('open-gemini-key-modal'));
      return false;
    } finally { busy.current = false; setSending(false); }
  }, [page]);
  return { messages, sending, error, send, refresh };
}
