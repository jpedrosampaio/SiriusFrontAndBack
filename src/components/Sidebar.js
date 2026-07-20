import { useNavigate, useLocation } from "react-router-dom";
import { Home, CheckSquare, TrendingUp, DollarSign, Target, MessageSquare, FileText, User, LogOut, Menu, X, Dumbbell, Bell, Apple, BookOpen, Trophy, Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useState, useEffect, memo } from "react";
import axios from "axios";
import { toast } from "sonner";
import { clearToken } from "@/lib/api";
import { Clock } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// SVG Logo Component - Wolf/Sirius Star
const SiriusLogo = ({ size = "w-12 h-12" }) => (
  <svg viewBox="0 0 100 100" className={size}>
    <defs>
      <linearGradient id="sidebarWolfGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#00F0FF" />
        <stop offset="50%" stopColor="#007AFF" />
        <stop offset="100%" stopColor="#00F0FF" />
      </linearGradient>
      <filter id="sidebarGlow">
        <feGaussianBlur stdDeviation="1.5" result="blur"/>
        <feMerge>
          <feMergeNode in="blur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
      <filter id="sidebarStarGlow">
        <feGaussianBlur stdDeviation="2" result="blur"/>
        <feMerge>
          <feMergeNode in="blur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
    {/* Ears */}
    <polygon points="31,20 39,41 23,43" fill="url(#sidebarWolfGrad)" opacity="0.9"/>
    <polygon points="69,20 61,41 77,43" fill="url(#sidebarWolfGrad)" opacity="0.9"/>
    <polygon points="32,26 38,41 27,42" fill="#050505" opacity="0.5"/>
    <polygon points="68,26 62,41 73,42" fill="#050505" opacity="0.5"/>
    {/* Head */}
    <path d="M50,82 L35,66 L27,51 L28,41 L37,37 L43,43 L50,39 L57,43 L63,37 L72,41 L73,51 L65,66 Z"
          fill="url(#sidebarWolfGrad)" filter="url(#sidebarGlow)"/>
    {/* Forehead shadow */}
    <path d="M50,41 L44,47 L39,51 L43,55 L50,53 L57,55 L61,51 L56,47 Z" fill="#050505" opacity="0.35"/>
    {/* Eyes */}
    <ellipse cx="41" cy="53" rx="4.3" ry="2.8" fill="#050505"/>
    <ellipse cx="59" cy="53" rx="4.3" ry="2.8" fill="#050505"/>
    <ellipse cx="42" cy="53" rx="2" ry="1.6" fill="#00F0FF" opacity="0.9"/>
    <ellipse cx="60" cy="53" rx="2" ry="1.6" fill="#00F0FF" opacity="0.9"/>
    <ellipse cx="42.4" cy="53" rx="0.8" ry="1.2" fill="#050505"/>
    <ellipse cx="60.4" cy="53" rx="0.8" ry="1.2" fill="#050505"/>
    {/* Nose */}
    <path d="M50,63 L48,65 L50,67 L52,65 Z" fill="#050505"/>
    <line x1="50" y1="67" x2="50" y2="71" stroke="#050505" strokeWidth="0.6"/>
    <path d="M47,71 Q50,74 53,71" fill="none" stroke="#050505" strokeWidth="0.5"/>
    {/* Sirius Star */}
    <polygon points="50,8 51.5,13 56,13 52.5,16 54,21 50,18 46,21 47.5,16 44,13 48.5,13"
             fill="#00F0FF" filter="url(#sidebarStarGlow)"/>
    <circle cx="50" cy="14.5" r="1.2" fill="white" opacity="0.7"/>
    {/* Fur lines */}
    <line x1="22" y1="55" x2="36" y2="57" stroke="url(#sidebarWolfGrad)" strokeWidth="0.4" opacity="0.3"/>
    <line x1="21" y1="58" x2="35" y2="59" stroke="url(#sidebarWolfGrad)" strokeWidth="0.4" opacity="0.3"/>
    <line x1="78" y1="55" x2="64" y2="57" stroke="url(#sidebarWolfGrad)" strokeWidth="0.4" opacity="0.3"/>
    <line x1="79" y1="58" x2="65" y2="59" stroke="url(#sidebarWolfGrad)" strokeWidth="0.4" opacity="0.3"/>
  </svg>
);

export { SiriusLogo };

// Brasilia Clock Hook
function useBrasiliaTime() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const timeStr = now.toLocaleTimeString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  const dateStr = now.toLocaleDateString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    weekday: "short",
    day: "2-digit",
    month: "short",
  });

  return { timeStr, dateStr };
}

function Sidebar({ user }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  const { timeStr, dateStr } = useBrasiliaTime();

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

  const menuItems = [
    { icon: Home, label: "Dashboard", path: "/dashboard" },
    { icon: CheckSquare, label: "Tarefas", path: "/tasks" },
    { icon: TrendingUp, label: "Hábitos", path: "/habits" },
    { icon: Dumbbell, label: "Treinos", path: "/workouts" },
    { icon: Apple, label: "Alimentação", path: "/nutrition" },
    { icon: BookOpen, label: "Estudos", path: "/studies" },
    { icon: DollarSign, label: "Finanças", path: "/finance" },
    { icon: Target, label: "Metas", path: "/goals" },
    { icon: MessageSquare, label: "Assistente", path: "/chat" },
    { icon: Bell, label: "Notificações", path: "/notifications" },
    { icon: Trophy, label: "Conquistas", path: "/achievements" },
    { icon: Calendar, label: "Calendário", path: "/calendar" },
    { icon: FileText, label: "Relatórios", path: "/reports" },
    { icon: User, label: "Perfil", path: "/profile" }
  ];

  const handleNavigate = (path) => {
    navigate(path);
    setIsOpen(false);
  };

  return (
    <>
      {/* Sidebar - desktop only, no mobile hamburger needed (MobileNav handles it) */}
      <div className={`w-64 bg-[#0A0A0A] border-r border-[#27272A] flex flex-col h-screen fixed left-0 top-0 z-40 hidden md:flex`}>
        <div className="p-6 border-b border-[#27272A]">
          <div className="flex items-center space-x-3 mb-4">
            <SiriusLogo />
            <div>
              <span className="font-heading text-2xl bg-gradient-to-r from-[#00F0FF] to-[#007AFF] bg-clip-text text-transparent">SIRIUS</span>
              <p className="text-[8px] text-[#52525B] uppercase tracking-widest">Discipline System</p>
            </div>
          </div>
          {user && (
            <div className="flex items-center space-x-3">
              <Avatar className="w-10 h-10 border-2 border-[#007AFF]">
                <AvatarImage src={user.picture} />
                <AvatarFallback className="bg-[#007AFF] text-white font-heading text-sm">
                  {(user.name || 'U').charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate text-sm">{user.name || 'Usuário'}</p>
                <div className="flex items-center space-x-2">
                  <span className="rank-badge bg-[#007AFF] text-white px-1.5 py-0.5 rounded-sm text-[10px]">
                    {user.rank || 'Recruta'}
                  </span>
                  <span className="font-data text-xs text-[#A1A1AA]">{user.xp ?? 0} XP</span>
                </div>
              </div>
            </div>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto py-4">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <button
                key={item.path}
                data-testid={`sidebar-${item.label.toLowerCase()}-link`}
                onClick={() => handleNavigate(item.path)}
                className={`w-full flex items-center space-x-3 px-6 py-3 transition-colors ${
                  isActive
                    ? "bg-[#007AFF]/10 border-l-2 border-[#007AFF] text-[#007AFF]"
                    : "text-[#A1A1AA] hover:bg-[#121212] hover:text-white"
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="uppercase text-xs tracking-wider font-medium">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-[#27272A]">
          {/* Brasilia Clock */}
          <div className="mb-3 flex items-center space-x-2 px-2 py-2 rounded-md bg-[#121212] border border-[#27272A]">
            <Clock className="w-4 h-4 text-[#00F0FF] flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="font-data text-sm text-[#00F0FF] tracking-wider tabular-nums leading-none">{timeStr}</p>
              <p className="text-[10px] text-[#52525B] mt-0.5 capitalize">{dateStr} — Brasília</p>
            </div>
          </div>
          <Button
            data-testid="sidebar-logout-btn"
            variant="outline"
            onClick={handleLogout}
            className="w-full border-[#27272A] hover:bg-[#121212] uppercase text-xs tracking-wider"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Sair
          </Button>
        </div>
      </div>

    </>
  );
}

export default memo(Sidebar);
