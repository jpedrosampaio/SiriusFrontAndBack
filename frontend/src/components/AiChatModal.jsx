import React, { useState, useRef, useEffect, useCallback } from 'react';
import { X, Send, User, Brain, Loader2, Sparkles } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      <span className="w-1.5 h-1.5 bg-[#FFD700] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
      <span className="w-1.5 h-1.5 bg-[#FFD700] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
      <span className="w-1.5 h-1.5 bg-[#FFD700] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
    </div>
  );
}

function MessageAvatar({ role }) {
  if (role === 'assistant') {
    return (
      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#FFD700] to-[#FF8C00] flex items-center justify-center shrink-0 mt-1 shadow-lg shadow-[#FFD700]/20">
        <Sparkles className="w-4 h-4 text-black" />
      </div>
    );
  }
  return (
    <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#007AFF] to-[#0055CC] flex items-center justify-center shrink-0 mt-1">
      <User className="w-4 h-4 text-white" />
    </div>
  );
}

export default function AiChatModal({ open, onClose }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const chatRef = useRef(null);

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
      <div
        className={`fixed bottom-24 right-4 z-50 w-[380px] max-w-[calc(100vw-32px)] transition-all duration-300 ${
          open ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-8 scale-95 pointer-events-none'
        }`}
      >
        <div
          ref={chatRef}
          className="bg-[#0A0A0A] border border-[#27272A] rounded-2xl shadow-2xl shadow-black/50 overflow-hidden flex flex-col"
          style={{ maxHeight: 'min(600px, calc(100vh - 140px))' }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="relative px-4 py-3.5 border-b border-[#27272A] shrink-0 bg-gradient-to-r from-[#0D0D0D] to-[#0A0A0A]">
            <div className="absolute inset-0 bg-gradient-to-r from-[#FFD700]/5 to-transparent pointer-events-none" />
            <div className="flex items-center justify-between relative">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#FFD700] to-[#FF8C00] flex items-center justify-center shadow-lg shadow-[#FFD700]/20">
                  <Brain className="w-5 h-5 text-black" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-white">IA Sirius</span>
                    <span className="px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider bg-blue-500/10 text-blue-400 rounded-md border border-blue-500/20">
                      Gemini
                    </span>
                  </div>
                  <p className="text-[10px] text-[#52525B]">Assistente pessoal de treinos</p>
                </div>
              </div>
              <button onClick={onClose} className="w-7 h-7 rounded-lg bg-[#1A1A1A] hover:bg-[#27272A] flex items-center justify-center transition-colors border border-[#27272A]">
                <X className="w-3.5 h-3.5 text-[#52525B]" />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center py-12 px-4">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#FFD700]/10 to-[#FF8C00]/5 flex items-center justify-center mb-5 border border-[#FFD700]/10">
                  <Sparkles className="w-8 h-8 text-[#FFD700]" />
                </div>
                <p className="text-base font-semibold text-white mb-1">IA Sirius</p>
                <p className="text-xs text-[#52525B] max-w-[240px] mb-6 leading-relaxed">
                  Pergunte sobre treinos, nutrição, lesões e evolução física. Uso do Gemini com sua chave.
                </p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {['Treino para iniciantes', 'Dieta para hipertrofia', 'Aquecimento ideal', 'Melhorar resistencia'].map((s) => (
                    <button
                      key={s}
                      onClick={() => { setInput(s); inputRef.current?.focus(); }}
                      className="group text-xs bg-[#1A1A1A] hover:bg-[#FFD700]/10 text-[#A1A1AA] hover:text-[#FFD700] px-3.5 py-2 rounded-xl border border-[#27272A] hover:border-[#FFD700]/30 transition-all duration-200"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex gap-3 items-start ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                style={{ animation: 'chatMessageIn 0.3s ease-out' }}
              >
                {msg.role === 'assistant' && <MessageAvatar role="assistant" />}
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-gradient-to-br from-[#007AFF] to-[#0055CC] text-white rounded-br-md shadow-lg shadow-[#007AFF]/10'
                      : msg.error
                      ? 'bg-[#2A0A0A] border border-[#4A1A1A] text-red-300 rounded-bl-md'
                      : 'bg-[#141414] border border-[#27272A] text-[#E4E4E7] rounded-bl-md shadow-sm'
                  }`}
                >
                  {msg.loading ? (
                    <div className="flex items-center gap-3">
                      <TypingDots />
                      <span className="text-[#52525B] text-xs">Gerando resposta...</span>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                  )}
                </div>
                {msg.role === 'user' && <MessageAvatar role="user" />}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="flex items-center gap-2 p-3 border-t border-[#27272A] shrink-0 bg-[#0D0D0D]">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Digite sua pergunta..."
              disabled={sending}
              className="flex-1 bg-[#1A1A1A] border border-[#27272A] rounded-xl px-4 py-2.5 text-sm text-white placeholder-[#52525B] outline-none focus:border-[#FFD700]/40 focus:ring-1 focus:ring-[#FFD700]/20 transition-all duration-200 disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#FFD700] to-[#FF8C00] hover:from-[#FFC300] hover:to-[#FF7000] disabled:from-[#27272A] disabled:to-[#27272A] flex items-center justify-center transition-all duration-200 disabled:text-[#52525B] text-black shrink-0 shadow-lg shadow-[#FFD700]/20 disabled:shadow-none"
            >
              {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
      <style>{`
        @keyframes chatMessageIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </>
  );
}
