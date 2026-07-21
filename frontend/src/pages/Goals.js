import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import { Target, Plus, Trash2, Calendar, CheckSquare, Square } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Goals() {
  const [user, setUser] = useState(null);
  const [goals, setGoals] = useState([]);
  const [open, setOpen] = useState(false);
  const [newGoal, setNewGoal] = useState({
    title: "",
    description: "",
    target_date: "",
    sprint_duration: 60
  });

  useEffect(() => {
    fetchUser();
    fetchGoals();
  }, []);

  const fetchUser = async () => {
    try {
      const res = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setUser(res.data);
    } catch (error) {
      toast.error("Erro ao carregar usuário");
    }
  };

  const fetchGoals = async () => {
    try {
      const res = await axios.get(`${API}/goals`, { withCredentials: true });
      setGoals(Array.isArray(res.data) ? res.data : []);
    } catch (error) {
      toast.error("Erro ao carregar metas");
    }
  };

  const handleCreateGoal = async () => {
    if (!newGoal.title.trim() || !newGoal.target_date) {
      toast.error("Preencha todos os campos obrigatórios");
      return;
    }
    try {
      await axios.post(`${API}/goals`, newGoal, { withCredentials: true });
      toast.success("Meta criada!");
      setNewGoal({
        title: "",
        description: "",
        target_date: "",
        sprint_duration: 60
      });
      setOpen(false);
      fetchGoals();
    } catch (error) {
      toast.error("Erro ao criar meta");
    }
  };

  const handleCheckDay = async (goalId, date) => {
    try {
      const res = await axios.post(`${API}/goals/${goalId}/check?date=${date}`, {}, { withCredentials: true });
      if (res.data.xp_earned) {
        toast.success(`+${res.data.xp_earned} XP!`);
      }
      fetchGoals();
      fetchUser();
    } catch (error) {
      toast.error("Erro ao marcar dia");
    }
  };

  const handleDeleteGoal = async (goalId) => {
    try {
      await axios.delete(`${API}/goals/${goalId}`, { withCredentials: true });
      toast.success("Meta deletada");
      fetchGoals();
    } catch (error) {
      toast.error("Erro ao deletar meta");
    }
  };

  const getDaysArray = (sprintDuration) => {
    const days = [];
    const today = new Date();
    for (let i = 0; i < sprintDuration; i++) {
      const date = new Date(today);
      date.setDate(today.getDate() - sprintDuration + i + 1);
      days.push(date.toISOString().split('T')[0]);
    }
    return days;
  };

  return (
    <div className="flex min-h-screen bg-[#050505]">
      <Sidebar user={user} />
      <div className="flex-1 ml-0 md:ml-64 p-4 md:p-6 lg:p-8 pb-24 md:pb-8 pt-[72px] md:pt-0 page-enter">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-8 gap-4">
            <div>
              <h1 className="font-heading text-3xl md:text-4xl mb-2" data-testid="goals-title">METAS & SPRINTS</h1>
              <p className="text-[#A1A1AA]">Defina objetivos, marque dias, conquiste resultados</p>
            </div>
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button data-testid="goals-create-btn" className="bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs tracking-widest shadow-[0_0_10px_rgba(0,122,255,0.3)] w-full md:w-auto">
                  <Plus className="w-4 h-4 mr-2" />
                  Nova Meta
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-lg">
                <DialogHeader>
                  <DialogTitle className="font-heading text-2xl">CRIAR META</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 mt-4">
                  <div>
                    <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">Título</Label>
                    <Input
                      value={newGoal.title}
                      onChange={(e) => setNewGoal({...newGoal, title: e.target.value})}
                      className="bg-[#121212] border-[#27272A] text-white"
                    />
                  </div>
                  <div>
                    <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">Descrição</Label>
                    <Textarea
                      value={newGoal.description}
                      onChange={(e) => setNewGoal({...newGoal, description: e.target.value})}
                      className="bg-[#121212] border-[#27272A] text-white"
                    />
                  </div>
                  <div>
                    <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">Data Alvo</Label>
                    <Input
                      type="date"
                      value={newGoal.target_date}
                      onChange={(e) => setNewGoal({...newGoal, target_date: e.target.value})}
                      className="bg-[#121212] border-[#27272A] text-white font-mono"
                    />
                  </div>
                  <div>
                    <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">
                      Duração do Sprint (dias): {newGoal.sprint_duration}
                    </Label>
                    <Slider
                      value={[newGoal.sprint_duration]}
                      onValueChange={(value) => setNewGoal({...newGoal, sprint_duration: value[0]})}
                      min={7}
                      max={90}
                      step={1}
                      className="w-full"
                    />
                  </div>
                  <Button onClick={handleCreateGoal} className="w-full bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs tracking-widest">
                    Criar
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid grid-cols-1 gap-6">
            {goals.length === 0 ? (
              <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center">
                <Target className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                <p className="text-[#A1A1AA]">Nenhuma meta criada</p>
              </Card>
            ) : (
              goals.map((goal) => {
                const days = getDaysArray(goal.sprint_duration);
                const dailyChecks = goal.daily_checks || [];
                const progress = (dailyChecks.length / (goal.sprint_duration || 1)) * 100;
                
                return (
                  <Card key={goal.goal_id} className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                    <div className="flex flex-col md:flex-row items-start justify-between mb-4 gap-4">
                      <div className="flex-1">
                        <h3 className="font-heading text-xl md:text-2xl mb-2">{goal.title}</h3>
                        {goal.description && (
                          <p className="text-sm text-[#A1A1AA] mb-3">{goal.description}</p>
                        )}
                        <div className="flex flex-wrap items-center gap-4 text-xs text-[#A1A1AA]">
                          <div className="flex items-center space-x-1">
                            <Calendar className="w-4 h-4" />
                            <span>Alvo: {goal.target_date}</span>
                          </div>
                          <span>Sprint: {goal.sprint_duration} dias</span>
                          <span className="text-[#007AFF]">{dailyChecks.length}/{goal.sprint_duration} dias</span>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDeleteGoal(goal.goal_id)}
                        className="text-[#52525B] hover:text-[#FF3B30] hover:bg-[#FF3B30]/10"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>

                    <div className="space-y-3">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-[#A1A1AA]">Progresso</span>
                        <span className="font-data text-lg text-[#007AFF]">{(progress ?? 0).toFixed(0)}%</span>
                      </div>
                      <div className="h-2 bg-[#27272A] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#007AFF] transition-all"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                      
                      <div className="pt-4">
                        <Label className="text-[#A1A1AA] text-xs mb-3 block uppercase tracking-wider">Marcar Dias do Sprint</Label>
                        <div className="grid grid-cols-7 sm:grid-cols-10 md:grid-cols-15 gap-2">
                          {days.map((date, idx) => {
                            const isChecked = dailyChecks.includes(date);
                            const isToday = date === new Date().toISOString().split('T')[0];
                            
                            return (
                              <button
                                key={date}
                                onClick={() => handleCheckDay(goal.goal_id, date)}
                                className={`w-8 h-8 md:w-10 md:h-10 rounded-sm flex items-center justify-center text-xs font-mono transition-all ${
                                  isChecked
                                    ? 'bg-[#007AFF] text-white shadow-[0_0_10px_rgba(0,122,255,0.3)]'
                                    : isToday
                                    ? 'bg-[#121212] border-2 border-[#007AFF] text-[#007AFF]'
                                    : 'bg-[#121212] border border-[#27272A] text-[#52525B] hover:border-[#007AFF]'
                                }`}
                                title={date}
                              >
                                {isChecked ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                              </button>
                            );
                          })}
                        </div>
                        <p className="text-xs text-[#52525B] mt-2">Clique nas caixas para marcar os dias concluídos. +5 XP por dia!</p>
                      </div>
                    </div>
                  </Card>
                );
              })
            )}
          </div>
        </div>
      </div>
      <MobileNav user={user} />
    </div>
  );
}


