import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Trophy, Lock, CheckCircle2, Star, Zap, Shield, Target, Flame,
  BookOpen, Dumbbell, DollarSign, Apple, TrendingUp, Crown
} from "lucide-react";
import axios from "axios";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ICON_MAP = {
  "check": CheckCircle2, "check-double": CheckCircle2, "list-checks": CheckCircle2,
  "rocket": Zap, "trending-up": TrendingUp, "flame": Flame, "crown": Crown,
  "dollar": DollarSign, "wallet": DollarSign, "bar-chart": DollarSign,
  "book": BookOpen, "clock": BookOpen, "graduation-cap": BookOpen, "brain": BookOpen,
  "target": Target, "dumbbell": Dumbbell, "medal": Trophy, "timer": Dumbbell,
  "utensils": Apple, "apple": Apple, "trophy": Trophy, "zap": Zap,
  "star": Star, "shield": Shield,
};

const CATEGORY_LABELS = {
  tasks: "Tarefas", habits: "Hábitos", finance: "Finanças",
  study: "Estudos", workouts: "Treinos", nutrition: "Nutrição",
  goals: "Metas", xp: "XP & Rank",
};

export default function Achievements() {
  const [user, setUser] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [userRes, achRes] = await Promise.all([
        axios.get(`${API}/auth/me`, { withCredentials: true }),
        axios.get(`${API}/achievements/full`, { withCredentials: true })
      ]);
      setUser(userRes.data);
      setData(achRes.data);

      if (achRes.data.newly_unlocked && achRes.data.newly_unlocked.length > 0) {
        achRes.data.newly_unlocked.forEach(a => {
          toast.success(`Nova conquista desbloqueada: ${a.title}!`);
        });
      }
    } catch {
      toast.error("Erro ao carregar conquistas");
    } finally {
      setLoading(false);
    }
  };

  const filtered = data?.achievements?.filter(a => {
    if (filter === "all") return true;
    if (filter === "unlocked") return a.unlocked;
    if (filter === "locked") return !a.unlocked;
    return a.category === filter;
  }) || [];

  const categories = [...new Set((data?.achievements || []).map(a => a.category))];

  if (loading) {
    return (
      <div className="flex min-h-screen bg-[#050505]">
        <Sidebar user={user} />
        <div className="flex-1 ml-0 md:ml-64 p-4 md:p-6 lg:p-8 pt-[72px] md:pt-0 page-enter">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-[#27272A] rounded w-48" />
            <div className="h-4 bg-[#1A1A1A] rounded w-32" />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
              {[...Array(8)].map((_, i) => <div key={i} className="h-40 bg-[#0A0A0A] rounded-lg border border-[#1A1A1A]" />)}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-[#050505] text-white">
      <Sidebar user={user} />
      <div className="flex-1 ml-0 md:ml-64 p-4 md:p-6 lg:p-8 pb-24 md:pb-8 pt-[72px] md:pt-0 page-enter">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <h1 className="font-heading text-3xl md:text-4xl mb-2 flex items-center gap-3">
              <Trophy className="w-8 h-8 text-[#FFD700]" />
              CONQUISTAS
            </h1>
            <p className="text-[#A1A1AA]">Desbloqueie badges completando desafios em todos os módulos</p>
          </div>

          {/* Overview Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-8">
            <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
              <div className="flex items-center justify-between mb-2">
                <Trophy className="w-6 h-6 text-[#FFD700]" />
                <span className="font-data text-2xl">{data?.unlocked || 0}</span>
              </div>
              <p className="text-[#A1A1AA] text-xs uppercase tracking-wider">Desbloqueadas</p>
            </Card>
            <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
              <div className="flex items-center justify-between mb-2">
                <Lock className="w-6 h-6 text-[#52525B]" />
                <span className="font-data text-2xl">{data?.locked || 0}</span>
              </div>
              <p className="text-[#A1A1AA] text-xs uppercase tracking-wider">Bloqueadas</p>
            </Card>
            <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
              <div className="flex items-center justify-between mb-2">
                <Star className="w-6 h-6 text-[#007AFF]" />
                <span className="font-data text-2xl">{data?.total || 0}</span>
              </div>
              <p className="text-[#A1A1AA] text-xs uppercase tracking-wider">Total</p>
            </Card>
            <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-6 h-6 text-[#39FF14]" />
                <span className="font-data text-2xl">{data?.completion_pct || 0}%</span>
              </div>
              <Progress value={data?.completion_pct || 0} className="h-2 mt-1" />
              <p className="text-[#A1A1AA] text-xs uppercase tracking-wider mt-2">Progresso Geral</p>
            </Card>
          </div>

          {/* Filters */}
          <div className="flex gap-2 overflow-x-auto pb-2 mb-6">
            {[
              { key: "all", label: "Todas" },
              { key: "unlocked", label: "Desbloqueadas" },
              { key: "locked", label: "Bloqueadas" },
              ...categories.map(c => ({ key: c, label: CATEGORY_LABELS[c] || c }))
            ].map(f => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={"px-4 py-1.5 text-xs rounded-full border transition-colors whitespace-nowrap " +
                  (filter === f.key
                    ? "bg-[#007AFF] border-[#007AFF] text-white"
                    : "border-[#27272A] text-[#52525B] hover:text-white hover:border-[#3F3F46]"
                  )
                }
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Achievement Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.map((ach) => {
              const Icon = ICON_MAP[ach.icon] || Trophy;
              const isUnlocked = ach.unlocked;
              const progress = ach.progress || 0;

              return (
                <Card
                  key={ach.id}
                  className={
                    "relative overflow-hidden p-5 transition-all duration-300 " +
                    (isUnlocked
                      ? "bg-gradient-to-br from-[#0A0A0A] to-[#1a1a2e] border-[#27272A] hover:border-[" + ach.color + "]/50"
                      : "bg-[#0A0A0A] border-[#1A1A1A] opacity-70 hover:opacity-90"
                    )
                  }
                >
                  {/* Glow for unlocked */}
                  {isUnlocked && (
                    <div className="absolute top-0 right-0 w-24 h-24 rounded-full blur-[40px] opacity-20 pointer-events-none" style={{ backgroundColor: ach.color }} />
                  )}

                  <div className="relative z-10">
                    <div className="flex items-start justify-between mb-3">
                      <div
                        className={"w-12 h-12 rounded-xl flex items-center justify-center " +
                          (isUnlocked ? "" : "bg-[#1A1A1A]")
                        }
                        style={isUnlocked ? { backgroundColor: ach.color + "20" } : {}}
                      >
                        {isUnlocked ? (
                          <Icon className="w-6 h-6" style={{ color: ach.color }} />
                        ) : (
                          <Lock className="w-5 h-5 text-[#3F3F46]" />
                        )}
                      </div>
                      {isUnlocked && (
                        <CheckCircle2 className="w-5 h-5 text-[#39FF14]" />
                      )}
                    </div>

                    <h3 className={"font-heading text-base mb-1 " + (isUnlocked ? "text-white" : "text-[#52525B]")}>
                      {ach.title}
                    </h3>
                    <p className="text-xs text-[#52525B] mb-3 leading-relaxed">{ach.description}</p>

                    <div className="space-y-1.5">
                      <div className="flex justify-between items-center">
                        <span className="text-[10px] text-[#52525B] uppercase tracking-wider">
                          {CATEGORY_LABELS[ach.category] || ach.category}
                        </span>
                        <span className={"text-xs font-data " + (isUnlocked ? "text-[#39FF14]" : "text-[#52525B]")}>
                          {progress >= 100 ? "100%" : `${Math.floor(progress)}%`}
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-[#1A1A1A] rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.min(progress, 100)}%`,
                            backgroundColor: isUnlocked ? "#39FF14" : ach.color
                          }}
                        />
                      </div>
                      <p className="text-[10px] text-[#3F3F46]">
                        {ach.current} / {ach.target}
                      </p>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>

          {filtered.length === 0 && (
            <div className="text-center py-16">
              <Trophy className="w-12 h-12 text-[#27272A] mx-auto mb-4" />
              <p className="text-[#52525B]">Nenhuma conquista encontrada para este filtro</p>
            </div>
          )}
        </div>
      </div>
      <MobileNav user={user} />
    </div>
  );
}


