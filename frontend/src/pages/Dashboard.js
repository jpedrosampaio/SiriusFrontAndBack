import { useEffect, useState, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import PullToRefresh from "@/components/PullToRefresh";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  CheckSquare, TrendingUp, DollarSign, Target, Award, Zap,
  Dumbbell, Utensils, BookOpen, Droplets, Flame, Clock, Brain,
  ClipboardList, BarChart3, Trophy, ListChecks, Hash, Percent,
  Search, AlertTriangle, ChevronRight, Bell, Sparkles, X,
  Activity, Calendar, Play
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import Onboarding from "@/components/Onboarding";
import { LoadingSkeleton } from "@/components/XpAnimation";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend
} from "recharts";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Dashboard() {
  const [user, setUser] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [weeklySummary, setWeeklySummary] = useState(null);
  const [reminders, setReminders] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [showSearch, setShowSearch] = useState(false);
  const [crossSuggestions, setCrossSuggestions] = useState([]);
  const [xpAnimation, setXpAnimation] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [analyticsDays, setAnalyticsDays] = useState(7);
  const [dailySummary, setDailySummary] = useState(null);
  const [globalStreaks, setGlobalStreaks] = useState(null);
  const [todayWorkout, setTodayWorkout] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [userRes, statsRes] = await Promise.all([
        axios.get(`${API}/auth/me`, { withCredentials: true }),
        axios.get(`${API}/stats/dashboard`, { withCredentials: true })
      ]);
      setUser(userRes.data);
      setStats(statsRes.data);
      
      // Fetch additional data in background
      try {
        const [weeklyRes, remindersRes, suggestionsRes, analyticsRes, streaksRes, dailyRes] = await Promise.all([
          axios.get(`${API}/dashboard/weekly-summary`, { withCredentials: true }),
          axios.get(`${API}/reminders/smart`, { withCredentials: true }),
          axios.get(`${API}/suggestions/cross-module`, { withCredentials: true }),
          axios.get(`${API}/stats/analytics?days=7`, { withCredentials: true }),
          axios.get(`${API}/streaks/global`, { withCredentials: true }),
          axios.get(`${API}/dashboard/daily-summary`, { withCredentials: true })
        ]);
        setWeeklySummary(weeklyRes.data);
        setReminders(remindersRes.data.reminders || []);
        setCrossSuggestions(suggestionsRes.data.suggestions || []);
        setAnalytics(analyticsRes.data);
        setGlobalStreaks(streaksRes.data);
        setDailySummary(dailyRes.data);
      } catch {}
      
      // Fetch today's workout schedule
      try {
        const workoutRes = await axios.get(`${API}/workouts/today-schedule`, { withCredentials: true });
        if (workoutRes.data.scheduled) setTodayWorkout(workoutRes.data);
      } catch {}
    } catch (error) {
      toast.error("Erro ao carregar dados");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (query) => {
    setSearchQuery(query);
    if (query.length < 2) { setSearchResults([]); return; }
    try {
      const res = await axios.get(`${API}/search/global?q=${encodeURIComponent(query)}`, { withCredentials: true });
      setSearchResults(res.data.results || []);
    } catch {}
  };

  const dismissReminder = (idx) => {
    setReminders(prev => prev.filter((_, i) => i !== idx));
  };

  const fetchAnalytics = async (d) => {
    setAnalyticsDays(d);
    try {
      const res = await axios.get(`${API}/stats/analytics?days=${d}`, { withCredentials: true });
      setAnalytics(res.data);
    } catch {}
  };

  const getNextRank = () => {
    const ranks = [
      { name: "Recruta", xp: 0 },
      { name: "Soldado", xp: 100 },
      { name: "Cabo", xp: 300 },
      { name: "Sargento", xp: 600 },
      { name: "Tenente", xp: 1000 },
      { name: "Capitão", xp: 1500 },
      { name: "Major", xp: 2200 },
      { name: "Coronel", xp: 3000 },
      { name: "General", xp: 4000 }
    ];
    
    if (!user) return { name: "Soldado", xp: 100, progress: 0 };
    
    for (let i = 0; i < ranks.length; i++) {
      if ((user.rank || 'Recruta') === ranks[i].name) {
        if (i === ranks.length - 1) return { name: "Máximo", xp: ranks[i].xp, progress: 100 };
        const next = ranks[i + 1];
        const current = ranks[i];
        const progress = (((user.xp ?? 0) - current.xp) / (next.xp - current.xp)) * 100;
        return { name: next.name, xp: next.xp, progress };
      }
    }
    return { name: "Soldado", xp: 100, progress: 0 };
  };

  if (loading) {
    return (
      <div className="flex min-h-screen bg-[#050505]">
        <Sidebar user={user} />
        <div className="flex-1 page-container md:ml-64 pt-[72px] md:pt-0">
          <div className="mb-8 pt-8 md:pt-0">
            <div className="skeleton h-8 w-64 mb-4" />
            <div className="skeleton h-4 w-40" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {[...Array(4)].map((_, i) => <div key={i} className="skeleton-card h-24" />)}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {[...Array(2)].map((_, i) => <div key={i} className="skeleton-card h-48" />)}
          </div>
        </div>
      </div>
    );
  }

  const nextRank = getNextRank();
  const simStats = stats?.simulado_stats || {};
  const qOverview = stats?.question_overview || {};

  return (
    <div className="flex min-h-screen bg-[#050505]">
      <Onboarding />
      <Sidebar user={user} />
      <PullToRefresh onRefresh={fetchData}>
      <div className="flex-1 ml-0 md:ml-64 pt-[72px] md:pt-0 pb-24 md:pb-8 page-enter">
        <div className="page-container">
          <div className="mb-6 md:mb-8 pt-12 md:pt-0">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <h1 className="font-heading text-2xl md:text-4xl mb-2" data-testid="dashboard-title">CENTRO DE COMANDO</h1>
                <p className="text-[#A1A1AA] text-sm md:text-base">Visão geral das operações</p>
              </div>
              {/* Global Search */}
              <div className="relative w-full md:w-80">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525B]" />
                <Input 
                  value={searchQuery}
                  onChange={(e) => handleSearch(e.target.value)}
                  onFocus={() => setShowSearch(true)}
                  placeholder="Buscar em tudo..."
                  className="bg-[#0A0A0A] border-[#27272A] text-white pl-10 pr-8"
                />
                {searchQuery && (
                  <button onClick={() => { setSearchQuery(""); setSearchResults([]); }} className="absolute right-3 top-1/2 -translate-y-1/2">
                    <X className="w-4 h-4 text-[#52525B]" />
                  </button>
                )}
                {showSearch && searchResults.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-2 bg-[#0A0A0A] border border-[#27272A] rounded-lg shadow-2xl z-50 max-h-80 overflow-y-auto">
                    {searchResults.map((r, i) => (
                      <button
                        key={i}
                        onClick={() => { navigate(r.link); setShowSearch(false); setSearchQuery(""); }}
                        className="w-full flex items-center gap-3 p-3 hover:bg-[#121212] transition-colors text-left border-b border-[#27272A] last:border-0"
                      >
                        <span className="text-lg">{r.icon}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white truncate">{r.title}</p>
                          <p className="text-xs text-[#52525B]">{r.subtitle}</p>
                        </div>
                        <ChevronRight className="w-4 h-4 text-[#52525B]" />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Smart Reminders */}
          {reminders.length > 0 && (
            <div className="mb-6 space-y-2">
              {reminders.slice(0, 3).map((r, idx) => (
                <div key={idx} className={`flex items-center gap-3 p-3 rounded-lg border ${
                  r.priority === 'high' ? 'bg-red-500/5 border-red-900/50' : 'bg-[#0A0A0A] border-[#27272A]'
                }`}>
                  <span className="text-lg">{r.icon}</span>
                  <p className="text-sm text-[#A1A1AA] flex-1">{r.message}</p>
                  <button onClick={() => navigate(r.action_link)} className="text-xs text-[#007AFF] hover:underline whitespace-nowrap">
                    Ver
                  </button>
                  <button onClick={() => dismissReminder(idx)} className="text-[#52525B] hover:text-white">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Cross-Module Suggestions */}
          {crossSuggestions.length > 0 && (
            <div className="mb-6">
              <div className="flex gap-3 overflow-x-auto pb-2">
                {crossSuggestions.map((s, idx) => (
                  <Card key={idx} className="bg-gradient-to-r from-[#0A0A0A] to-[#0a0a1a] border-[#27272A] p-4 min-w-[280px] flex-shrink-0">
                    <div className="flex items-start gap-3">
                      <span className="text-2xl">{s.icon}</span>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-white">{s.title}</p>
                        <p className="text-xs text-[#A1A1AA] mt-1">{s.message}</p>
                        <button onClick={() => navigate(s.action_link)} className="text-xs text-[#007AFF] hover:underline mt-2 flex items-center gap-1">
                          {s.action} <ChevronRight className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {stats && (
            <>
              {/* Daily Summary + Streaks Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6 md:mb-8">
                {/* AI Daily Summary Widget */}
                {dailySummary && dailySummary.summary && (
                  <Card className="bg-gradient-to-br from-[#0A0A0A] to-[#121212] border-[#27272A] p-4 md:p-5 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-40 h-40 bg-[#007AFF]/5 rounded-full blur-[60px] pointer-events-none" />
                    <div className="relative z-10">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#007AFF] to-[#A855F7] flex items-center justify-center">
                          <Sparkles className="w-4 h-4 text-white" />
                        </div>
                        <div>
                          <h3 className="font-heading text-sm">BRIEFING DIÁRIO</h3>
                          <p className="text-[10px] text-[#52525B]">Gerado por IA</p>
                        </div>
                        {dailySummary.summary.score !== undefined && (
                          <div className="ml-auto flex items-center gap-1.5">
                            <div className="w-10 h-10 rounded-full border-2 flex items-center justify-center" style={{ borderColor: dailySummary.summary.score >= 70 ? '#39FF14' : dailySummary.summary.score >= 40 ? '#FF9500' : '#FF3B30' }}>
                              <span className="font-data text-xs" style={{ color: dailySummary.summary.score >= 70 ? '#39FF14' : dailySummary.summary.score >= 40 ? '#FF9500' : '#FF3B30' }}>{dailySummary.summary.score}</span>
                            </div>
                          </div>
                        )}
                      </div>
                      <p className="text-sm text-[#D4D4D8] mb-2">{dailySummary.summary.greeting}</p>
                      <p className="text-xs text-[#A1A1AA] mb-3">{dailySummary.summary.progress_summary}</p>
                      {dailySummary.summary.pending_items && dailySummary.summary.pending_items.length > 0 && (
                        <div className="mb-3">
                          <p className="text-[10px] text-[#52525B] uppercase tracking-wider mb-1.5">Pendente</p>
                          <div className="flex flex-wrap gap-1.5">
                            {dailySummary.summary.pending_items.slice(0, 5).map((item, i) => (
                              <span key={i} className="text-[10px] bg-[#1A1A1A] text-[#A1A1AA] px-2 py-0.5 rounded-full">{item}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {dailySummary.summary.priority_action && (
                        <div className="bg-[#007AFF]/10 border border-[#007AFF]/20 rounded-lg px-3 py-2">
                          <p className="text-[10px] text-[#007AFF] uppercase tracking-wider mb-0.5">Ação Prioritária</p>
                          <p className="text-xs text-white">{dailySummary.summary.priority_action}</p>
                        </div>
                      )}
                      {dailySummary.summary.motivation && (
                        <p className="text-[10px] text-[#52525B] italic mt-2">"{dailySummary.summary.motivation}"</p>
                      )}
                    </div>
                  </Card>
                )}

                {/* Today's Workout Widget */}
                {todayWorkout && (
                  <Card className="bg-gradient-to-br from-[#0A2A0A] to-[#0A0A0A] border border-green-900/50 p-4 md:p-5 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-green-500/5 rounded-full -translate-y-1/2 translate-x-1/2" />
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Dumbbell className="w-5 h-5 text-green-400" />
                        <h3 className="font-heading text-sm">TREINO DE HOJE</h3>
                      </div>
                      {todayWorkout.already_completed ? (
                        <Badge className="bg-green-500/20 text-green-400 border-green-500/30">Concluído ✅</Badge>
                      ) : (
                        <Badge className="bg-[#00F0FF]/10 text-[#00F0FF] border-[#00F0FF]/30">Pendente</Badge>
                      )}
                    </div>
                    <p className="text-xs text-[#A1A1AA] mb-1">{todayWorkout.plan_name}</p>
                    <p className="font-medium text-sm text-white mb-3">
                      {todayWorkout.day_label || `Treino ${todayWorkout.split_label || ""}`}
                    </p>
                    {todayWorkout.exercise_count > 0 && (
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-xs text-[#A1A1AA]">{todayWorkout.exercise_count} exercícios</span>
                        <span className="text-[#27272A]">·</span>
                        <span className="text-xs text-[#A1A1AA]">Semana {todayWorkout.week}</span>
                      </div>
                    )}
                    <div className="flex gap-2">
                      {!todayWorkout.already_completed && (
                        <Button size="sm" onClick={() => navigate("/workouts")} className="bg-green-600 hover:bg-green-700 text-white text-xs h-8">
                          <Play className="w-3 h-3 mr-1" /> Iniciar
                        </Button>
                      )}
                      <Button variant="outline" size="sm" onClick={() => navigate("/workouts")} className="border-[#27272A] text-xs h-8">
                        Ver ficha
                      </Button>
                    </div>
                  </Card>
                )}

                {/* Global Streaks Widget */}
                {globalStreaks && (
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-5">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <Flame className="w-6 h-6 text-[#FF9500]" />
                        <h3 className="font-heading text-sm">STREAK GLOBAL</h3>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <p className="font-data text-2xl text-[#FF9500]">{globalStreaks.current_streak}</p>
                          <p className="text-[10px] text-[#52525B] uppercase">Dias</p>
                        </div>
                        {globalStreaks.longest_streak > 0 && (
                          <div className="text-right border-l border-[#27272A] pl-3">
                            <p className="font-data text-lg text-[#FFD700]">{globalStreaks.longest_streak}</p>
                            <p className="text-[10px] text-[#52525B] uppercase">Recorde</p>
                          </div>
                        )}
                      </div>
                    </div>
                    {/* Weekly Heatmap */}
                    <div className="flex gap-1.5 mb-4">
                      {(globalStreaks.heatmap || []).map((day, i) => (
                        <div key={i} className="flex-1 text-center">
                          <div className={"w-full aspect-square rounded-md flex items-center justify-center text-[10px] font-data transition-colors " + (day.active ? "text-white" : "text-[#3F3F46]")} style={{ backgroundColor: day.active ? (day.count >= 3 ? '#FF9500' : day.count >= 2 ? '#FF9500AA' : '#FF950066') : '#1A1A1A' }}>
                            {day.count || '-'}
                          </div>
                          <p className="text-[8px] text-[#3F3F46] mt-1">{day.date.slice(8)}</p>
                        </div>
                      ))}
                    </div>
                    {/* Module Streaks */}
                    <div className="grid grid-cols-5 gap-1.5">
                      {[
                        { key: "tasks", label: "Tarefas", icon: CheckSquare, color: "#007AFF" },
                        { key: "habits", label: "Hábitos", icon: TrendingUp, color: "#39FF14" },
                        { key: "study", label: "Estudos", icon: BookOpen, color: "#A855F7" },
                        { key: "workouts", label: "Treinos", icon: Dumbbell, color: "#EF4444" },
                        { key: "nutrition", label: "Nutrição", icon: Utensils, color: "#22C55E" },
                      ].map(m => {
                        const ModIcon = m.icon;
                        const streak = (globalStreaks.module_streaks || {})[m.key] || 0;
                        return (
                          <div key={m.key} className="text-center bg-[#121212] rounded-lg p-2">
                            <ModIcon className="w-3.5 h-3.5 mx-auto mb-1" style={{ color: streak > 0 ? m.color : '#3F3F46' }} />
                            <p className="font-data text-sm" style={{ color: streak > 0 ? m.color : '#3F3F46' }}>{streak}</p>
                            <p className="text-[7px] text-[#3F3F46] uppercase">{m.label}</p>
                          </div>
                        );
                      })}
                    </div>
                    {/* Combo bonus */}
                    {globalStreaks.combo_count >= 2 && (
                      <div className="mt-3 bg-[#FF9500]/10 border border-[#FF9500]/20 rounded-lg px-3 py-2 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Zap className="w-4 h-4 text-[#FFD700]" />
                          <span className="text-xs text-[#FFD700]">COMBO x{globalStreaks.combo_count}</span>
                        </div>
                        <span className="text-xs font-data text-[#FF9500]">+{globalStreaks.combo_bonus_xp} XP bônus</span>
                      </div>
                    )}
                  </Card>
                )}
              </div>

              {/* Row 1: Quick Stats */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6 md:mb-8">
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                  <div className="flex items-center justify-between mb-2 md:mb-4">
                    <CheckSquare className="w-6 h-6 md:w-8 md:h-8 text-[#007AFF]" />
                    <span className="font-data text-lg md:text-2xl">{stats.tasks_completed_today ?? 0}/{stats.tasks_today ?? 0}</span>
                  </div>
                  <p className="text-[#A1A1AA] uppercase text-[10px] md:text-xs tracking-wider">Tarefas</p>
                </Card>

                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                  <div className="flex items-center justify-between mb-2 md:mb-4">
                    <TrendingUp className="w-6 h-6 md:w-8 md:h-8 text-[#39FF14]" />
                    <span className="font-data text-lg md:text-2xl">{stats.habits_completed_today ?? 0}/{stats.habits_total ?? 0}</span>
                  </div>
                  <p className="text-[#A1A1AA] uppercase text-[10px] md:text-xs tracking-wider">Hábitos</p>
                </Card>

                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                  <div className="flex items-center justify-between mb-2 md:mb-4">
                    <DollarSign className="w-6 h-6 md:w-8 md:h-8 text-[#FF9500]" />
                    <span className="font-data text-lg md:text-2xl">R$ {(stats.balance ?? 0).toFixed(0)}</span>
                  </div>
                  <p className="text-[#A1A1AA] uppercase text-[10px] md:text-xs tracking-wider">Saldo</p>
                </Card>

                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                  <div className="flex items-center justify-between mb-2 md:mb-4">
                    <Target className="w-6 h-6 md:w-8 md:h-8 text-[#00F0FF]" />
                    <span className="font-data text-lg md:text-2xl">{(stats.goals_avg_progress ?? 0).toFixed(0)}%</span>
                  </div>
                  <p className="text-[#A1A1AA] uppercase text-[10px] md:text-xs tracking-wider">Metas</p>
                </Card>
              </div>

              {/* Row 2: Treino, Nutrição, Estudos */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4 mb-6 md:mb-8">
                {/* Card de Treino */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                  <div className="flex items-center space-x-3 md:space-x-4 mb-3 md:mb-4">
                    <Dumbbell className="w-8 h-8 md:w-10 md:h-10 text-[#FF6B6B]" />
                    <div>
                      <p className="text-sm text-[#A1A1AA] uppercase tracking-wider mb-1">Treinos</p>
                      <p className="font-heading text-2xl">Esta Semana</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] flex items-center gap-2"><Flame className="w-4 h-4" /> Sessões</span>
                      <span className="font-data text-[#FF6B6B]">{stats.workout_stats?.workouts_this_week || 0}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] flex items-center gap-2"><Clock className="w-4 h-4" /> Duração</span>
                      <span className="font-data">{stats.workout_stats?.total_duration_minutes || 0} min</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] flex items-center gap-2"><Flame className="w-4 h-4" /> Calorias</span>
                      <span className="font-data text-[#FF9500]">{stats.workout_stats?.total_calories_burned || 0} kcal</span>
                    </div>
                  </div>
                </Card>

                {/* Card de Nutrição */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                  <div className="flex items-center space-x-3 md:space-x-4 mb-3 md:mb-4">
                    <Utensils className="w-8 h-8 md:w-10 md:h-10 text-[#4ECDC4]" />
                    <div>
                      <p className="text-sm text-[#A1A1AA] uppercase tracking-wider mb-1">Nutrição</p>
                      <p className="font-heading text-2xl">Hoje</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-[#A1A1AA] text-sm">Calorias</span>
                        <span className="font-data text-sm">
                          {stats.nutrition_stats?.calories_consumed || 0} / {stats.nutrition_stats?.calories_goal || 2000}
                        </span>
                      </div>
                      <Progress 
                        value={Math.min(((stats.nutrition_stats?.calories_consumed || 0) / (stats.nutrition_stats?.calories_goal || 2000)) * 100, 100)} 
                        className="h-2" 
                      />
                    </div>
                    <div>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-[#A1A1AA] text-sm flex items-center gap-1"><Droplets className="w-3 h-3" /> Água</span>
                        <span className="font-data text-sm text-[#00B4D8]">
                          {((stats.nutrition_stats?.water_consumed_ml || 0) / 1000).toFixed(1)}L / {((stats.nutrition_stats?.water_goal_ml || 2000) / 1000).toFixed(1)}L
                        </span>
                      </div>
                      <Progress 
                        value={Math.min(((stats.nutrition_stats?.water_consumed_ml || 0) / (stats.nutrition_stats?.water_goal_ml || 2000)) * 100, 100)} 
                        className="h-2 [&>div]:bg-[#00B4D8]" 
                      />
                    </div>
                    <div className="flex justify-between items-center pt-1">
                      <span className="text-[#A1A1AA]">Refeições</span>
                      <span className="font-data">{stats.nutrition_stats?.meals_count || 0}</span>
                    </div>
                  </div>
                </Card>

                {/* Card de Estudos */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                  <div className="flex items-center space-x-3 md:space-x-4 mb-3 md:mb-4">
                    <BookOpen className="w-8 h-8 md:w-10 md:h-10 text-[#A78BFA]" />
                    <div>
                      <p className="text-sm text-[#A1A1AA] uppercase tracking-wider mb-1">Estudos</p>
                      <p className="font-heading text-2xl">Progresso</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] flex items-center gap-2"><Clock className="w-4 h-4" /> Hoje</span>
                      <span className="font-data">{stats.study_stats?.study_time_today_minutes || 0} min</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] flex items-center gap-2"><Flame className="w-4 h-4" /> Streak</span>
                      <span className="font-data text-[#FFD700]">{stats.study_stats?.current_streak || 0} dias</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] flex items-center gap-2"><Brain className="w-4 h-4" /> Flashcards</span>
                      <span className={`font-data ${(stats.study_stats?.flashcards_due || 0) > 0 ? 'text-[#FF9500]' : 'text-[#39FF14]'}`}>
                        {stats.study_stats?.flashcards_due || 0} pendentes
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] flex items-center gap-2"><Hash className="w-4 h-4" /> Matérias</span>
                      <span className="font-data">{stats.study_stats?.notebooks_count || 0}</span>
                    </div>
                  </div>
                </Card>
              </div>

              {/* Row 3: Simulados + Questões + Rank + Finanças */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6 md:mb-8">
                {/* Card de Simulados */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                  <div className="flex items-center space-x-3 mb-3">
                    <ClipboardList className="w-8 h-8 text-[#007AFF]" />
                    <div>
                      <p className="text-xs text-[#A1A1AA] uppercase tracking-wider">Simulados</p>
                      <p className="font-heading text-lg">Desempenho</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] text-sm">Total</span>
                      <span className="font-data text-[#007AFF]">{simStats.total_simulados || 0}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] text-sm">Tentativas</span>
                      <span className="font-data">{simStats.total_attempts || 0}</span>
                    </div>
                    <div>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-[#A1A1AA] text-sm">Média</span>
                        <span className={`font-data text-sm ${(simStats.average_score || 0) >= 70 ? 'text-[#39FF14]' : (simStats.average_score || 0) >= 50 ? 'text-[#FFD700]' : 'text-[#FF3B30]'}`}>
                          {simStats.average_score || 0}%
                        </span>
                      </div>
                      <Progress value={simStats.average_score || 0} className="h-2" />
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] text-sm">Melhor</span>
                      <span className="font-data text-[#39FF14]">{simStats.best_score || 0}%</span>
                    </div>
                  </div>
                </Card>

                {/* Card de Questões */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                  <div className="flex items-center space-x-3 mb-3">
                    <ListChecks className="w-8 h-8 text-[#FF6B6B]" />
                    <div>
                      <p className="text-xs text-[#A1A1AA] uppercase tracking-wider">Questões</p>
                      <p className="font-heading text-lg">Respondidas</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="text-center py-2">
                      <span className="font-data text-3xl text-white">{qOverview.total_answered || 0}</span>
                      <p className="text-xs text-[#A1A1AA] mt-1">total respondidas</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-center">
                      <div className="bg-[#121212] rounded-lg p-2">
                        <p className="font-data text-lg text-[#39FF14]">{qOverview.total_correct || 0}</p>
                        <p className="text-[10px] text-[#A1A1AA]">Acertos</p>
                      </div>
                      <div className="bg-[#121212] rounded-lg p-2">
                        <p className={`font-data text-lg ${(qOverview.accuracy_rate || 0) >= 70 ? 'text-[#39FF14]' : (qOverview.accuracy_rate || 0) >= 50 ? 'text-[#FFD700]' : 'text-[#FF3B30]'}`}>
                          {qOverview.accuracy_rate || 0}%
                        </p>
                        <p className="text-[10px] text-[#A1A1AA]">Taxa</p>
                      </div>
                    </div>
                  </div>
                </Card>

                {/* Rank Card */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                  <div className="flex items-center space-x-3 mb-3">
                    <Award className="w-8 h-8 text-[#FFD700]" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-[#A1A1AA] uppercase tracking-wider">Rank</p>
                      <p className="font-heading text-lg">{user?.rank || 'Recruta'}</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="font-data text-xl">{user?.xp ?? 0}</p>
                      <p className="text-[10px] text-[#A1A1AA]">XP</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-[#A1A1AA]">Próximo: {nextRank.name}</span>
                      <span className="font-data text-[#A1A1AA]">{nextRank.xp} XP</span>
                    </div>
                    <Progress value={nextRank.progress} className="h-2" />
                  </div>
                </Card>

                {/* Resumo Financeiro */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                  <div className="flex items-center space-x-3 mb-3">
                    <Zap className="w-8 h-8 text-[#007AFF]" />
                    <div>
                      <p className="text-xs text-[#A1A1AA] uppercase tracking-wider">Finanças</p>
                      <p className="font-heading text-lg">Mês Atual</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] text-sm">Receitas</span>
                      <span className="font-data text-sm text-[#39FF14]">+R$ {(stats.income ?? 0).toFixed(0)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#A1A1AA] text-sm">Despesas</span>
                      <span className="font-data text-sm text-[#FF3B30]">-R$ {(stats.expenses ?? 0).toFixed(0)}</span>
                    </div>
                    <div className="border-t border-[#27272A] pt-2 flex justify-between items-center">
                      <span className="font-medium text-sm">Saldo</span>
                      <span className={`font-data text-base ${(stats.balance ?? 0) >= 0 ? 'text-[#39FF14]' : 'text-[#FF3B30]'}`}>
                        R$ {(stats.balance ?? 0).toFixed(0)}
                      </span>
                    </div>
                  </div>
                </Card>
              </div>

              {/* Weekly Summary */}
              {weeklySummary && (
                <Card className="bg-gradient-to-r from-[#0A0A0A] to-[#0a0a1a] border-[#27272A] p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <BarChart3 className="w-6 h-6 text-[#007AFF]" />
                    <h2 className="font-heading text-lg">RESUMO SEMANAL</h2>
                    <span className="text-xs text-[#52525B]">{weeklySummary.period?.start} → {weeklySummary.period?.end}</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <div className="bg-[#121212] rounded-lg p-3 text-center">
                      <DollarSign className="w-5 h-5 mx-auto mb-1 text-[#39FF14]" />
                      <p className={`font-data text-lg ${(weeklySummary.finance?.balance || 0) >= 0 ? 'text-[#39FF14]' : 'text-[#FF3B30]'}`}>
                        R$ {(weeklySummary.finance?.balance || 0).toFixed(0)}
                      </p>
                      <p className="text-[10px] text-[#52525B]">Saldo Semana</p>
                    </div>
                    <div className="bg-[#121212] rounded-lg p-3 text-center">
                      <Dumbbell className="w-5 h-5 mx-auto mb-1 text-[#FF6B6B]" />
                      <p className="font-data text-lg text-white">{weeklySummary.workouts?.count || 0}</p>
                      <p className="text-[10px] text-[#52525B]">Treinos ({weeklySummary.workouts?.total_minutes || 0}min)</p>
                    </div>
                    <div className="bg-[#121212] rounded-lg p-3 text-center">
                      <Flame className="w-5 h-5 mx-auto mb-1 text-[#FF9500]" />
                      <p className="font-data text-lg text-white">{weeklySummary.habits?.completion_pct || 0}%</p>
                      <p className="text-[10px] text-[#52525B]">Hábitos</p>
                    </div>
                    <div className="bg-[#121212] rounded-lg p-3 text-center">
                      <CheckSquare className="w-5 h-5 mx-auto mb-1 text-[#007AFF]" />
                      <p className="font-data text-lg text-white">{weeklySummary.tasks?.completed || 0}/{weeklySummary.tasks?.total || 0}</p>
                      <p className="text-[10px] text-[#52525B]">Tarefas</p>
                    </div>
                    <div className="bg-[#121212] rounded-lg p-3 text-center">
                      <BookOpen className="w-5 h-5 mx-auto mb-1 text-[#A78BFA]" />
                      <p className="font-data text-lg text-white">{weeklySummary.study?.total_minutes || 0}</p>
                      <p className="text-[10px] text-[#52525B]">Min Estudados</p>
                    </div>
                  </div>
                </Card>
              )}
            </>
          )}

          {/* ===== ANALYTICS CHARTS ===== */}
          {analytics && analytics.data && analytics.data.length > 0 && (
            <div className="mt-8">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <Activity className="w-6 h-6 text-[#007AFF]" />
                  <h2 className="font-heading text-lg md:text-xl">ANÁLISE DE EVOLUÇÃO</h2>
                </div>
                <div className="flex gap-1 bg-[#0A0A0A] border border-[#27272A] rounded-lg p-1">
                  {[7, 14, 30].map(d => (
                    <button
                      key={d}
                      onClick={() => fetchAnalytics(d)}
                      className={"px-3 py-1 text-xs rounded-md transition-colors " + (analyticsDays === d ? "bg-[#007AFF] text-white" : "text-[#52525B] hover:text-white")}
                    >
                      {d}d
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Tarefas & Hábitos */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <CheckSquare className="w-5 h-5 text-[#007AFF]" />
                    <h3 className="text-sm font-medium text-[#A1A1AA] uppercase tracking-wider">Tarefas & Hábitos</h3>
                  </div>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={analytics.data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1A1A1A" />
                      <XAxis dataKey="label" tick={{ fill: "#52525B", fontSize: 11 }} axisLine={{ stroke: "#27272A" }} />
                      <YAxis tick={{ fill: "#52525B", fontSize: 11 }} axisLine={{ stroke: "#27272A" }} />
                      <Tooltip
                        contentStyle={{ background: "#0A0A0A", border: "1px solid #27272A", borderRadius: 8, color: "#fff", fontSize: 12 }}
                        labelStyle={{ color: "#A1A1AA" }}
                      />
                      <Bar dataKey="tasks" name="Tarefas" fill="#007AFF" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="habits" name="Hábitos" fill="#39FF14" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </Card>

                {/* Finanças */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <DollarSign className="w-5 h-5 text-[#FF9500]" />
                    <h3 className="text-sm font-medium text-[#A1A1AA] uppercase tracking-wider">Receitas vs Despesas</h3>
                  </div>
                  <ResponsiveContainer width="100%" height={220}>
                    <AreaChart data={analytics.data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                      <defs>
                        <linearGradient id="gradIncome" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#39FF14" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#39FF14" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="gradExpense" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#FF3B30" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#FF3B30" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1A1A1A" />
                      <XAxis dataKey="label" tick={{ fill: "#52525B", fontSize: 11 }} axisLine={{ stroke: "#27272A" }} />
                      <YAxis tick={{ fill: "#52525B", fontSize: 11 }} axisLine={{ stroke: "#27272A" }} />
                      <Tooltip
                        contentStyle={{ background: "#0A0A0A", border: "1px solid #27272A", borderRadius: 8, color: "#fff", fontSize: 12 }}
                        formatter={(val) => ["R$ " + Number(val).toFixed(2)]}
                      />
                      <Area type="monotone" dataKey="income" name="Receitas" stroke="#39FF14" fill="url(#gradIncome)" strokeWidth={2} />
                      <Area type="monotone" dataKey="expenses" name="Despesas" stroke="#FF3B30" fill="url(#gradExpense)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </Card>

                {/* Tempo de Estudo */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <BookOpen className="w-5 h-5 text-[#A78BFA]" />
                    <h3 className="text-sm font-medium text-[#A1A1AA] uppercase tracking-wider">Tempo de Estudo (min)</h3>
                  </div>
                  <ResponsiveContainer width="100%" height={220}>
                    <AreaChart data={analytics.data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                      <defs>
                        <linearGradient id="gradStudy" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#A78BFA" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#A78BFA" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1A1A1A" />
                      <XAxis dataKey="label" tick={{ fill: "#52525B", fontSize: 11 }} axisLine={{ stroke: "#27272A" }} />
                      <YAxis tick={{ fill: "#52525B", fontSize: 11 }} axisLine={{ stroke: "#27272A" }} />
                      <Tooltip
                        contentStyle={{ background: "#0A0A0A", border: "1px solid #27272A", borderRadius: 8, color: "#fff", fontSize: 12 }}
                        formatter={(val) => [val + " min"]}
                      />
                      <Area type="monotone" dataKey="study_min" name="Estudo" stroke="#A78BFA" fill="url(#gradStudy)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </Card>

                {/* XP Acumulado */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <Zap className="w-5 h-5 text-[#FFD700]" />
                    <h3 className="text-sm font-medium text-[#A1A1AA] uppercase tracking-wider">XP Ganho</h3>
                  </div>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={analytics.data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1A1A1A" />
                      <XAxis dataKey="label" tick={{ fill: "#52525B", fontSize: 11 }} axisLine={{ stroke: "#27272A" }} />
                      <YAxis tick={{ fill: "#52525B", fontSize: 11 }} axisLine={{ stroke: "#27272A" }} />
                      <Tooltip
                        contentStyle={{ background: "#0A0A0A", border: "1px solid #27272A", borderRadius: 8, color: "#fff", fontSize: 12 }}
                      />
                      <Line type="monotone" dataKey="xp" name="XP do Dia" stroke="#FFD700" strokeWidth={2} dot={{ fill: "#FFD700", r: 3 }} />
                      <Line type="monotone" dataKey="xp_cumulative" name="XP Acumulado" stroke="#007AFF" strokeWidth={2} dot={false} strokeDasharray="5 5" />
                    </LineChart>
                  </ResponsiveContainer>
                </Card>
              </div>

              {/* Summary totals */}
              {analytics.totals && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
                  <div className="bg-[#0A0A0A] border border-[#27272A] rounded-lg p-3 text-center">
                    <p className="font-data text-xl text-[#007AFF]">{analytics.totals.tasks}</p>
                    <p className="text-[10px] text-[#52525B] uppercase">Tarefas Feitas</p>
                  </div>
                  <div className="bg-[#0A0A0A] border border-[#27272A] rounded-lg p-3 text-center">
                    <p className="font-data text-xl text-[#A78BFA]">{analytics.totals.study_hours}h</p>
                    <p className="text-[10px] text-[#52525B] uppercase">Horas Estudadas</p>
                  </div>
                  <div className="bg-[#0A0A0A] border border-[#27272A] rounded-lg p-3 text-center">
                    <p className="font-data text-xl text-[#FF6B6B]">{analytics.totals.workouts}</p>
                    <p className="text-[10px] text-[#52525B] uppercase">Treinos</p>
                  </div>
                  <div className="bg-[#0A0A0A] border border-[#27272A] rounded-lg p-3 text-center">
                    <p className="font-data text-xl text-[#FFD700]">{analytics.totals.xp_earned}</p>
                    <p className="text-[10px] text-[#52525B] uppercase">XP Ganho</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      </PullToRefresh>
      <MobileNav user={user} />
    </div>
  );
}
