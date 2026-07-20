import { useEffect, useState, useMemo, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Calendar as CalendarIcon, ChevronLeft, ChevronRight,
  CheckSquare, TrendingUp, BookOpen, Dumbbell, Apple, Circle
} from "lucide-react";
import axios from "axios";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const TYPE_CONFIG = {
  task: { icon: CheckSquare, label: "Tarefa", color: "#007AFF" },
  habit: { icon: TrendingUp, label: "Hábito", color: "#39FF14" },
  study: { icon: BookOpen, label: "Estudo", color: "#A855F7" },
  workout: { icon: Dumbbell, label: "Treino", color: "#EF4444" },
  meal: { icon: Apple, label: "Refeição", color: "#22C55E" },
};

const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
const MONTHS = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

function getDaysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year, month) {
  return new Date(year, month, 1).getDay();
}

export default function CalendarPage() {
  const [user, setUser] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDay, setSelectedDay] = useState(null);
  const [filters, setFilters] = useState({ task: true, habit: true, study: true, workout: true, meal: true });

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const today = new Date().toISOString().split("T")[0];

  const fetchUser = async () => {
    try {
      const res = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setUser(res.data);
    } catch {}
  };

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const start = `${year}-${String(month + 1).padStart(2, "0")}-01`;
      const lastDay = getDaysInMonth(year, month);
      const end = `${year}-${String(month + 1).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`;
      const res = await axios.get(`${API}/calendar/events?start=${start}&end=${end}`, { withCredentials: true });
      setEvents(res.data.events || []);
    } catch {
      toast.error("Erro ao carregar eventos");
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => {
    fetchUser();
  }, []);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const navigate = (dir) => {
    setCurrentDate(prev => {
      const d = new Date(prev);
      d.setMonth(d.getMonth() + dir);
      return d;
    });
    setSelectedDay(null);
  };

  const goToday = () => {
    setCurrentDate(new Date());
    setSelectedDay(today);
  };

  const toggleFilter = (type) => {
    setFilters(prev => ({ ...prev, [type]: !prev[type] }));
  };

  const filteredEvents = useMemo(() => {
    return events.filter(e => filters[e.type] !== false);
  }, [events, filters]);

  const eventsByDate = useMemo(() => {
    const map = {};
    filteredEvents.forEach(e => {
      if (!map[e.date]) map[e.date] = [];
      map[e.date].push(e);
    });
    return map;
  }, [filteredEvents]);

  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfMonth(year, month);

  const calendarDays = useMemo(() => {
    const days = [];
    for (let i = 0; i < firstDay; i++) days.push(null);
    for (let i = 1; i <= daysInMonth; i++) days.push(i);
    return days;
  }, [firstDay, daysInMonth]);

  const selectedDateStr = selectedDay || today;
  const selectedEvents = eventsByDate[selectedDateStr] || [];

  // Stats for the month
  const monthStats = useMemo(() => {
    const stats = { task: 0, habit: 0, study: 0, workout: 0, meal: 0 };
    filteredEvents.forEach(e => { if (stats[e.type] !== undefined) stats[e.type]++; });
    return stats;
  }, [filteredEvents]);

  return (
    <div className="flex min-h-screen bg-[#050505] text-white">
      <Sidebar user={user} />
      <div className="flex-1 ml-0 md:ml-64 p-4 md:p-8 pb-24 md:pb-8 pt-[72px] md:pt-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-6">
            <h1 className="font-heading text-2xl md:text-4xl mb-2 flex items-center gap-3">
              <CalendarIcon className="w-8 h-8 text-[#007AFF]" />
              CALENDÁRIO
            </h1>
            <p className="text-[#A1A1AA]">Visualização unificada de todas as suas atividades</p>
          </div>

          {/* Filters */}
          <div className="flex gap-2 overflow-x-auto pb-2 mb-6">
            {Object.entries(TYPE_CONFIG).map(([key, cfg]) => {
              const Icon = cfg.icon;
              const active = filters[key];
              return (
                <button
                  key={key}
                  onClick={() => toggleFilter(key)}
                  className={"flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs transition-all whitespace-nowrap " +
                    (active
                      ? "border-transparent text-white"
                      : "border-[#27272A] text-[#52525B] opacity-50"
                    )
                  }
                  style={active ? { backgroundColor: cfg.color + "20", borderColor: cfg.color + "50" } : {}}
                >
                  <Icon className="w-3.5 h-3.5" style={{ color: active ? cfg.color : "#52525B" }} />
                  {cfg.label}
                  <span className="font-data text-[10px]" style={{ color: active ? cfg.color : "#52525B" }}>
                    {monthStats[key] || 0}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Calendar Grid */}
            <div className="lg:col-span-2">
              <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                {/* Month navigation */}
                <div className="flex items-center justify-between mb-6">
                  <Button variant="ghost" size="icon" onClick={() => navigate(-1)} className="text-[#A1A1AA] hover:text-white">
                    <ChevronLeft className="w-5 h-5" />
                  </Button>
                  <div className="text-center">
                    <h2 className="font-heading text-xl">{MONTHS[month]}</h2>
                    <p className="text-xs text-[#52525B]">{year}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={goToday} className="text-xs border-[#27272A] text-[#A1A1AA] hover:text-white">
                      Hoje
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => navigate(1)} className="text-[#A1A1AA] hover:text-white">
                      <ChevronRight className="w-5 h-5" />
                    </Button>
                  </div>
                </div>

                {/* Weekday headers */}
                <div className="grid grid-cols-7 gap-1 mb-2">
                  {WEEKDAYS.map(d => (
                    <div key={d} className="text-center text-[10px] text-[#52525B] uppercase tracking-wider font-medium py-1">{d}</div>
                  ))}
                </div>

                {/* Days */}
                <div className="grid grid-cols-7 gap-1">
                  {calendarDays.map((day, idx) => {
                    if (day === null) return <div key={"empty-" + idx} />;
                    const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                    const dayEvents = eventsByDate[dateStr] || [];
                    const isToday = dateStr === today;
                    const isSelected = dateStr === selectedDateStr;
                    const typeSet = new Set(dayEvents.map(e => e.type));

                    return (
                      <button
                        key={dateStr}
                        onClick={() => setSelectedDay(dateStr)}
                        className={"relative p-1.5 md:p-2 rounded-lg text-center transition-all min-h-[52px] md:min-h-[64px] flex flex-col items-center " +
                          (isSelected ? "bg-[#007AFF]/20 border border-[#007AFF]" :
                           isToday ? "bg-[#121212] border border-[#27272A]" :
                           "hover:bg-[#121212] border border-transparent"
                          )
                        }
                      >
                        <span className={"text-sm font-data " +
                          (isSelected ? "text-[#007AFF]" : isToday ? "text-white" : "text-[#A1A1AA]")
                        }>{day}</span>
                        {/* Event dots */}
                        {dayEvents.length > 0 && (
                          <div className="flex gap-0.5 mt-1 flex-wrap justify-center">
                            {[...typeSet].slice(0, 4).map(type => (
                              <div
                                key={type}
                                className="w-1.5 h-1.5 rounded-full"
                                style={{ backgroundColor: TYPE_CONFIG[type]?.color || "#52525B" }}
                              />
                            ))}
                            {dayEvents.length > 4 && (
                              <span className="text-[8px] text-[#52525B]">+{dayEvents.length - 4}</span>
                            )}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </Card>
            </div>

            {/* Day detail panel */}
            <div className="lg:col-span-1">
              <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-5 sticky top-20">
                <h3 className="font-heading text-lg mb-1">
                  {selectedDateStr === today ? "HOJE" : new Date(selectedDateStr + "T12:00:00").toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "short" })}
                </h3>
                <p className="text-xs text-[#52525B] mb-4">{selectedEvents.length} atividade{selectedEvents.length !== 1 ? "s" : ""}</p>

                {selectedEvents.length === 0 ? (
                  <div className="text-center py-8">
                    <CalendarIcon className="w-10 h-10 text-[#1A1A1A] mx-auto mb-3" />
                    <p className="text-sm text-[#3F3F46]">Nenhuma atividade neste dia</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-[calc(100vh-300px)] overflow-y-auto pr-1">
                    {selectedEvents.map((event) => {
                      const cfg = TYPE_CONFIG[event.type] || {};
                      const Icon = cfg.icon || Circle;
                      return (
                        <div
                          key={event.id}
                          className="flex items-start gap-3 p-3 rounded-lg bg-[#121212] border border-[#1A1A1A] hover:border-[#27272A] transition-colors"
                        >
                          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: (cfg.color || "#52525B") + "20" }}>
                            <Icon className="w-4 h-4" style={{ color: cfg.color }} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className={"text-sm font-medium truncate " + (event.completed ? "text-[#52525B] line-through" : "text-white")}>
                              {event.title}
                            </p>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-[10px] uppercase tracking-wider" style={{ color: cfg.color }}>{cfg.label}</span>
                              {event.duration_minutes > 0 && (
                                <span className="text-[10px] text-[#52525B]">{event.duration_minutes} min</span>
                              )}
                              {event.calories > 0 && (
                                <span className="text-[10px] text-[#52525B]">{Math.round(event.calories)} kcal</span>
                              )}
                            </div>
                          </div>
                          {event.completed && (
                            <div className="w-5 h-5 rounded-full bg-[#39FF14]/10 flex items-center justify-center flex-shrink-0">
                              <div className="w-2 h-2 rounded-full bg-[#39FF14]" />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </Card>
            </div>
          </div>
        </div>
      </div>
      <MobileNav user={user} />
    </div>
  );
}
