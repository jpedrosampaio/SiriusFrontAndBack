import { useNavigate, useLocation } from "react-router-dom";
import { Home, CheckSquare, TrendingUp, DollarSign, MessageSquare, MoreHorizontal } from "lucide-react";
import { useState, useEffect, memo } from "react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Target, Dumbbell, Apple, BookOpen, Bell, FileText, User, LogOut, Clock, Trophy, Calendar, Award } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import { clearToken } from "@/lib/api";
import { SiriusLogo } from "@/components/Sidebar";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function MobileNav({ user }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [moreOpen, setMoreOpen] = useState(false);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const brasiliaTime = now.toLocaleTimeString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  const brasiliaDate = now.toLocaleDateString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    weekday: "short",
    day: "2-digit",
    month: "short",
  });

  const handleLogout = async () => {
    try {
      await axios.post(`${API}/auth/logout`, {}, { withCredentials: true });
      clearToken();
      toast.success("Logout realizado");
      navigate('/login');
    } catch (error) {
      console.error('Logout error:', error);
      clearToken();
      navigate('/login');
    }
  };

  const mainItems = [
    { icon: Home, label: "Início", path: "/dashboard", color: "#007AFF" },
    { icon: CheckSquare, label: "Tarefas", path: "/tasks", color: "#007AFF" },
    { icon: TrendingUp, label: "Hábitos", path: "/habits", color: "#39FF14" },
    { icon: DollarSign, label: "Finanças", path: "/finance", color: "#FF9500" },
    { icon: MessageSquare, label: "IA", path: "/chat", color: "#00F0FF" },
  ];

  const moreItems = [
    { icon: Dumbbell, label: "Treinos", path: "/workouts", color: "#EF4444" },
    { icon: Apple, label: "Alimentação", path: "/nutrition", color: "#22C55E" },
    { icon: BookOpen, label: "Estudos", path: "/studies", color: "#A855F7" },
    { icon: Target, label: "Metas", path: "/goals", color: "#F59E0B" },
    { icon: Trophy, label: "Conquistas", path: "/achievements", color: "#FFD700" },
    { icon: Calendar, label: "Calendário", path: "/calendar", color: "#14B8A6" },
    { icon: Bell, label: "Notificações", path: "/notifications", color: "#EC4899" },
    { icon: FileText, label: "Relatórios", path: "/reports", color: "#8B5CF6" },
    { icon: User, label: "Perfil", path: "/profile", color: "#007AFF" },
  ];

  return (
    <>
      {/* Mobile Header */}
      <div className="md:hidden fixed top-0 left-0 right-0 bg-[#0A0A0A]/95 backdrop-blur-lg border-b border-[#1A1A1A] z-50 safe-area-inset-top">
        <div className="flex items-center justify-between px-4 h-14">
          <div className="flex items-center space-x-2">
            <SiriusLogo size="w-7 h-7" />
            <span className="font-heading text-base bg-gradient-to-r from-[#00F0FF] to-[#007AFF] bg-clip-text text-transparent">SIRIUS</span>
          </div>
          {user && (
            <div className="flex items-center space-x-2">
              <div className="flex items-center space-x-1.5 bg-[#121212] rounded-full px-2.5 py-1 border border-[#27272A]">
                <Award className="w-3 h-3 text-[#007AFF]" />
                <span className="text-[10px] font-medium text-[#A1A1AA]">{user.rank || 'Recruta'}</span>
                <span className="text-[10px] text-[#52525B]">{user.xp ?? 0} XP</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-[#0A0A0A]/95 backdrop-blur-lg border-t border-[#1A1A1A] z-50 safe-area-inset-bottom">
        <div className="flex items-center justify-around h-[60px] px-1">
          {mainItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`flex flex-col items-center justify-center py-1.5 px-3 rounded-xl transition-all duration-200 min-w-[56px] ${
                  isActive
                    ? "text-white"
                    : "text-[#71717A] active:scale-95"
                }`}
              >
                <div className={`relative p-1.5 rounded-lg transition-all duration-200 ${
                  isActive ? "bg-[#007AFF]/20" : ""
                }`}>
                  <Icon className={`w-[22px] h-[22px] transition-colors ${isActive ? 'text-[#007AFF]' : ''}`} />
                  {isActive && (
                    <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-[#007AFF]" />
                  )}
                </div>
                <span className={`text-[10px] mt-0.5 font-medium transition-colors ${isActive ? 'text-[#007AFF]' : ''}`}>{item.label}</span>
              </button>
            );
          })}
          
          <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
            <SheetTrigger asChild>
              <button className="flex flex-col items-center justify-center py-1.5 px-3 rounded-xl text-[#71717A] active:scale-95 min-w-[56px]">
                <div className="p-1.5">
                  <MoreHorizontal className="w-[22px] h-[22px]" />
                </div>
                <span className="text-[10px] mt-0.5 font-medium">Mais</span>
              </button>
            </SheetTrigger>
            <SheetContent side="bottom" className="bg-[#0A0A0A] border-t border-[#1A1A1A] rounded-t-3xl px-4 pb-8">
              <div className="w-10 h-1 bg-[#27272A] rounded-full mx-auto mb-5" />
              
              {/* User info */}
              {user && (
                <div className="flex items-center justify-between mb-5 px-1">
                  <div className="flex items-center space-x-3">
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-[#007AFF] to-[#00F0FF] flex items-center justify-center shadow-lg shadow-[#007AFF]/20">
                      <span className="font-bold text-white text-base">
                        {(user.name || 'U').charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <div>
                      <p className="font-medium text-sm text-white">{user.name || 'Usuário'}</p>
                      <div className="flex items-center space-x-2 mt-0.5">
                        <span className="bg-[#007AFF]/20 text-[#007AFF] px-2 py-0.5 rounded-md text-[10px] font-medium">
                          {user.rank || 'Recruta'}
                        </span>
                        <span className="text-xs text-[#52525B]">{user.xp ?? 0} XP</span>
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="p-2.5 text-[#52525B] hover:text-red-400 rounded-lg active:bg-[#121212] transition-colors"
                  >
                    <LogOut className="w-5 h-5" />
                  </button>
                </div>
              )}

              {/* Brasilia Clock */}
              <div className="mb-5 flex items-center justify-center space-x-2 px-3 py-2.5 rounded-xl bg-[#121212] border border-[#1A1A1A]">
                <Clock className="w-4 h-4 text-[#00F0FF] flex-shrink-0" />
                <span className="font-data text-sm text-[#00F0FF] tracking-wider tabular-nums">{brasiliaTime}</span>
                <span className="text-[10px] text-[#52525B] capitalize">{brasiliaDate} — Brasília</span>
              </div>
              
              {/* Menu grid */}
              <div className="grid grid-cols-3 gap-3">
                {moreItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.path;
                  return (
                    <button
                      key={item.path}
                      onClick={() => {
                        navigate(item.path);
                        setMoreOpen(false);
                      }}
                      className={`flex flex-col items-center justify-center py-3.5 rounded-xl transition-all active:scale-95 ${
                        isActive
                          ? "bg-[#007AFF]/15 border border-[#007AFF]/30"
                          : "bg-[#121212] border border-[#1A1A1A] active:bg-[#1A1A1A]"
                      }`}
                    >
                      <Icon className="w-6 h-6 mb-1.5" style={{ color: isActive ? item.color : '#71717A' }} />
                      <span className={`text-[11px] font-medium ${isActive ? 'text-white' : 'text-[#A1A1AA]'}`}>{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </nav>
    </>
  );
}

export default memo(MobileNav);
