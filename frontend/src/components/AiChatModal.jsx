import React, { useState, useRef, useEffect, useCallback } from 'react';
import { X, Send, User, Brain, Loader2 } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

export default function AiChatModal({ open, onClose }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const callCloud = useCallback(async (message) => {
    const res = await axios.post(`${BACKEND_URL}/api/ai/chat`, { message }, { withCredentials: true });
    return res.data.reply;
  }, []);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setSending(true);
    setMessages((prev) => [...prev, { role: 'assistant', content: '', loading: true }]);
    try {
      const reply = await callCloud(text);
      if (reply.includes("Configure sua chave") && reply.includes("Gemini")) {
        window.dispatchEvent(new CustomEvent("open-gemini-key-modal"));
      }
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: 'assistant', content: reply };
        return copy;
      });
    } catch (err) {
      const errMsg = err.response?.data?.reply || err.message || 'Erro ao gerar resposta.';
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: 'assistant', content: errMsg, error: true };
        return copy;
      });
    } finally {
      setSending(false);
    }
  }, [input, sending, callCloud]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {open && <div className="fixed inset-0 z-40" onClick={onClose} />}
      <div
        className={`fixed bottom-20 right-4 z-50 w-[360px] max-w-[calc(100vw-32px)] transition-all duration-300 ${
          open ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none'
        }`}
      >
        <div
          className="bg-[#0A0A0A] border border-[#27272A] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
          style={{ maxHeight: 'min(600px, calc(100vh - 120px))' }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#27272A] shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#FFD700] to-[#FF8C00] flex items-center justify-center">
                <Brain className="w-4 h-4 text-black" />
              </div>
              <span className="text-sm font-semibold text-white">IA Sirius</span>
              <span className="w-2 h-2 rounded-full bg-blue-500" title="Gemini" />
            </div>
            <button onClick={onClose} className="text-[#52525B] hover:text-white transition-colors p-1">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center py-8">
                <Brain className="w-10 h-10 text-[#27272A] mb-3" />
                <p className="text-sm text-[#52525B] max-w-[220px]">
                  Assistente IA com Gemini. Pergunte sobre treinos, nutrição e saúde.
                </p>
                <p className="text-[10px] text-[#52525B] mt-2">
                  Configure sua chave Gemini no Perfil se solicitado.
                </p>
                <div className="flex flex-wrap gap-2 mt-4 justify-center">
                  {['Melhor treino para peito', 'Dieta para ganho de massa', 'Aquecimento ideal'].map((s) => (
                    <button
                      key={s}
                      onClick={() => { setInput(s); inputRef.current?.focus(); }}
                      className="text-xs bg-[#1A1A1A] hover:bg-[#27272A] text-[#A1A1AA] px-3 py-1.5 rounded-full border border-[#27272A] transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'assistant' && (
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#FFD700] to-[#FF8C00] flex items-center justify-center shrink-0 mt-1">
                    <Brain className="w-4 h-4 text-black" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-[#007AFF] text-white rounded-br-md'
                      : msg.error
                      ? 'bg-[#2A0A0A] border border-[#4A1A1A] text-red-300 rounded-bl-md'
                      : 'bg-[#1A1A1A] text-[#E4E4E7] border border-[#27272A] rounded-bl-md'
                  }`}
                >
                  {msg.loading ? (
                    <div className="flex items-center gap-2">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-[#FFD700]" />
                      <span className="text-[#A1A1AA] text-xs italic">Gerando resposta...</span>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                  )}
                </div>
                {msg.role === 'user' && (
                  <div className="w-7 h-7 rounded-lg bg-[#27272A] flex items-center justify-center shrink-0 mt-1">
                    <User className="w-4 h-4 text-white" />
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="flex items-center gap-2 p-3 border-t border-[#27272A] shrink-0">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Pergunte sobre treinos..."
              disabled={sending}
              className="flex-1 bg-[#1A1A1A] border border-[#27272A] rounded-xl px-3.5 py-2 text-sm text-white placeholder-[#52525B] outline-none focus:border-[#FFD700]/50 transition-colors disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className="w-9 h-9 rounded-xl bg-[#FFD700] hover:bg-[#FFC300] disabled:bg-[#27272A] flex items-center justify-center transition-all disabled:text-[#52525B] text-black shrink-0"
            >
              {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
