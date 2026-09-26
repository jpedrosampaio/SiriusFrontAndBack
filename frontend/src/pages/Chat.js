import { useAssistant } from '@/hooks/useAssistant';
import { getCurrentUser } from "@/lib/api";
import { useEffect, useState, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, User, Bot, Loader2, Sparkles, ChefHat, Dumbbell, BookOpen, DollarSign, Save } from "lucide-react";
import MarkdownRenderer from "@/components/MarkdownRenderer";

import { motion } from "framer-motion";
import axios from "axios";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Chat() {
  const [user, setUser] = useState(null);
  const { messages, sending: loading, error, send, refresh } = useAssistant('/chat');
  const [content, setContent] = useState("");
  const [archive, setArchive] = useState(null);
  const [archiveCursor, setArchiveCursor] = useState(null);
  const loadArchive = async () => {
    try {
      const { data } = await axios.get(`${API}/chat/general/archive`, { params: { before: archiveCursor } });
      setArchive(previous => [...(previous || []), ...data.messages]); setArchiveCursor(data.next_cursor);
    } catch (err) { toast.error('Não foi possível carregar o histórico antigo.'); }
  };

  const scrollRef = useRef(null);

  useEffect(() => {
    const load = async () => {
      try {
        const userRes = await getCurrentUser();
        setUser(userRes.data);
      } catch (e) { console.error(e); }
    };
    load();
  }, []);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!content.trim()) return;

    if (await send(content.trim())) setContent("");
  };

  const intentIcons = { recipe: ChefHat, workout: Dumbbell, study: BookOpen, finance: DollarSign };
  const intentColors = { recipe: "text-green-400", workout: "text-orange-400", study: "text-purple-400", finance: "text-blue-400" };

  return (
    <div className="flex min-h-screen bg-[#050505]">
      <Sidebar user={user} />
      <div className="flex-1 ml-0 md:ml-64 flex flex-col h-screen">
        <div className="p-4 md:p-6 border-b border-[#27272A] pt-[72px] md:pt-6">
          <h1 className="font-heading text-xl md:text-3xl mb-1">Converse com o Sirius</h1>
          <p className="text-xs md:text-sm text-[#A1A1AA]">A mesma conversa do assistente flutuante. Revise as sugestões antes de aplicá-las nos módulos.</p>
        </div>

        {error && <div role="alert" className="px-4 text-amber-300">{error} <button className="underline" onClick={refresh}>Recarregar</button></div>}
        <div ref={scrollRef} className="flex-1 p-4 md:p-6 overflow-y-auto pb-36 md:pb-28">
          <div className="max-w-4xl mx-auto space-y-4">
            <details className="text-sm text-zinc-400"><summary>Histórico anterior à conversa unificada</summary>
              <p className="my-2">Arquivo somente para consulta; não é enviado inteiro à IA.</p>
              {archive?.map(message => <p key={message.message_id} className="p-2 whitespace-pre-wrap break-words">{message.role}: {message.content}</p>)}
              {(archive === null || archiveCursor) && <Button variant="outline" onClick={loadArchive}>Carregar mensagens antigas</Button>}
            </details>
            {messages.length === 0 ? (
              <Card className="bg-[#0A0A0A] border-[#27272A] p-6 md:p-8 text-center">
                <Sparkles className="w-10 h-10 md:w-12 md:h-12 text-[#00F0FF] mx-auto mb-4" />
                <p className="text-[#A1A1AA] text-sm md:text-base mb-3">Sou seu assistente integrado! Posso ajudar com:</p>
                <div className="grid grid-cols-2 gap-3 max-w-md mx-auto">
                  <div className="bg-[#121212] p-3 rounded-lg text-left">
                    <ChefHat className="w-5 h-5 text-green-400 mb-1" />
                    <p className="text-xs font-medium">Receitas</p>
                    <p className="text-[10px] text-[#52525B]">"Me dê uma receita de frango fitness"</p>
                  </div>
                  <div className="bg-[#121212] p-3 rounded-lg text-left">
                    <Dumbbell className="w-5 h-5 text-orange-400 mb-1" />
                    <p className="text-xs font-medium">Treinos</p>
                    <p className="text-[10px] text-[#52525B]">"Monte um treino de peito e tríceps"</p>
                  </div>
                  <div className="bg-[#121212] p-3 rounded-lg text-left">
                    <DollarSign className="w-5 h-5 text-blue-400 mb-1" />
                    <p className="text-xs font-medium">Finanças</p>
                    <p className="text-[10px] text-[#52525B]">"Como economizar R$ 500/mês?"</p>
                  </div>
                  <div className="bg-[#121212] p-3 rounded-lg text-left">
                    <BookOpen className="w-5 h-5 text-purple-400 mb-1" />
                    <p className="text-xs font-medium">Estudos</p>
                    <p className="text-[10px] text-[#52525B]">"Dicas para estudar direito constitucional"</p>
                  </div>
                </div>
                <p className="text-[10px] text-[#52525B] mt-3">💡 Receitas e treinos pedidos aqui são salvos automaticamente no app!</p>
              </Card>
            ) : (
              messages.map((msg, idx) => (
                <motion.div
                  key={msg.message_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, delay: idx > messages.length - 3 ? 0.05 : 0 }}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`flex items-start space-x-2 md:space-x-3 max-w-[90%] md:max-w-2xl ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
                    <div className={`w-7 h-7 md:w-8 md:h-8 rounded-sm flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-[#007AFF]' : 'bg-[#2C2C2E]'}`}>
                      {msg.role === 'user' ? <User className="w-4 h-4 md:w-5 md:h-5" /> : <Bot className="w-4 h-4 md:w-5 md:h-5" />}
                    </div>
                    <div className={`p-3 md:p-4 rounded-sm ${msg.role === 'user' ? 'bg-[#007AFF]/20 border border-[#007AFF]/30' : 'bg-[#0A0A0A] border border-[#27272A]'}`}>
                      {msg.role === 'user' ? (
                        <p className="text-xs md:text-sm whitespace-pre-wrap break-words">{msg.content}</p>
                      ) : (
                        <MarkdownRenderer content={msg.content} className="text-xs md:text-sm break-words" />
                      )}
                      {msg.saved_item && (
                        <div className="mt-2 pt-2 border-t border-[#27272A] flex items-center gap-2">
                          <Save className="w-3 h-3 text-green-400" />
                          <span className="text-xs text-green-400">
                            {msg.saved_item.type === 'recipe' ? '🍳 Receita' : msg.saved_item.type === 'workout' ? '💪 Treino' : '📚 Item'} "{msg.saved_item.name}" salvo!
                          </span>
                        </div>
                      )}
                      {msg.intent && msg.intent !== 'general' && (
                        <div className="mt-1">
                          {(() => { const Icon = intentIcons[msg.intent]; return Icon ? <Badge variant="outline" className={`text-[10px] ${intentColors[msg.intent]}`}><Icon className="w-3 h-3 mr-1" />{msg.intent}</Badge> : null; })()}
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))
            )}
            {loading && (
              <div className="flex justify-start">
                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 rounded-sm bg-[#2C2C2E] flex items-center justify-center"><Bot className="w-5 h-5" /></div>
                  <div className="bg-[#0A0A0A] border border-[#27272A] p-4 rounded-sm"><Loader2 className="w-4 h-4 animate-spin text-[#00F0FF]" /></div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="p-3 md:p-6 border-t border-[#27272A] bg-[#0A0A0A]/95 backdrop-blur-lg fixed bottom-[60px] md:bottom-0 left-0 right-0 md:left-64">
          <form onSubmit={handleSend} className="max-w-4xl mx-auto">
            <div className="flex items-center space-x-2 md:space-x-3">
              <Input value={content} onChange={(e) => setContent(e.target.value)} placeholder="Peça uma receita, treino, dica financeira ou qualquer coisa..." className="flex-1 bg-[#121212] border-[#27272A] text-white font-mono text-sm" disabled={loading} />
              <Button type="submit" disabled={loading || !content.trim()} className="bg-[#007AFF] hover:bg-[#0062CC] px-3 md:px-4">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </Button>
            </div>
          </form>
        </div>
      </div>
      <MobileNav user={user} />
    </div>
  );
}
