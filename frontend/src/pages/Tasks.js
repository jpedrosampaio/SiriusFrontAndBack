import { useEffect, useState, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { getLocalDateStr } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CheckSquare, Plus, Trash2, Circle, CheckCircle2, Calendar, Repeat, LayoutGrid, List, GripVertical, ArrowRight, Clock } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DragDropContext, Droppable, Draggable } from "react-beautiful-dnd";
import axios from "axios";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const COLUMNS = {
  todo: { id: "todo", title: "A FAZER", icon: Circle, color: "#52525B", bgAccent: "from-[#52525B]/10" },
  in_progress: { id: "in_progress", title: "EM PROGRESSO", icon: Clock, color: "#FF9500", bgAccent: "from-[#FF9500]/10" },
  done: { id: "done", title: "CONCLUÍDO", icon: CheckCircle2, color: "#39FF14", bgAccent: "from-[#39FF14]/10" },
};

const priorityColors = {
  low: "border-l-[#39FF14]",
  medium: "border-l-[#FF9500]",
  high: "border-l-[#FF3B30]",
};

const priorityLabels = { low: "Baixa", medium: "Média", high: "Alta" };
const recurrenceLabels = { all: "Todas", once: "Única vez", daily: "Diárias", weekly: "Semanais", monthly: "Mensais" };

function TaskCard({ task, index, onToggle, onDelete, viewMode }) {
  if (viewMode === "kanban") {
    return (
      <Draggable draggableId={task.task_id} index={index}>
        {(provided, snapshot) => (
          <div
            ref={provided.innerRef}
            {...provided.draggableProps}
            className={"bg-[#0A0A0A] border border-[#27272A] border-l-4 rounded-lg p-3 mb-2 transition-shadow " +
              priorityColors[task.priority] + " " +
              (snapshot.isDragging ? "shadow-lg shadow-[#007AFF]/20 border-[#007AFF]/50" : "hover:border-[#3F3F46]")
            }
          >
            <div className="flex items-start gap-2">
              <div {...provided.dragHandleProps} className="mt-1 cursor-grab active:cursor-grabbing">
                <GripVertical className="w-4 h-4 text-[#3F3F46]" />
              </div>
              <div className="flex-1 min-w-0">
                <h4 className={"text-sm font-medium truncate " + (task.completed ? "line-through text-[#52525B]" : "text-white")}>
                  {task.title}
                </h4>
                {task.description && <p className="text-xs text-[#52525B] truncate mt-0.5">{task.description}</p>}
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-[10px] uppercase text-[#A1A1AA] tracking-wider">{priorityLabels[task.priority]}</span>
                  <span className="font-data text-[10px] text-[#007AFF]">+{task.xp_reward} XP</span>
                </div>
              </div>
              <button onClick={() => onDelete(task.task_id)} className="text-[#FF3B30]/50 hover:text-[#FF3B30] transition-colors p-0.5">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </Draggable>
    );
  }

  // List view
  return (
    <Card className={"task-item bg-[#0A0A0A] border-[#27272A] border-l-4 " + priorityColors[task.priority] + " p-4"}>
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3 flex-1">
          <button data-testid={"task-toggle-" + task.task_id} onClick={() => onToggle(task)} className="mt-1">
            {task.completed ? <CheckCircle2 className="w-6 h-6 text-[#39FF14]" /> : <Circle className="w-6 h-6 text-[#52525B]" />}
          </button>
          <div className="flex-1">
            <h3 className={"font-medium mb-1 " + (task.completed ? "line-through text-[#52525B]" : "")}>{task.title}</h3>
            {task.description && <p className="text-sm text-[#A1A1AA]">{task.description}</p>}
            <div className="flex items-center space-x-3 mt-2">
              <span className="text-xs uppercase text-[#A1A1AA] tracking-wider">{priorityLabels[task.priority]}</span>
              {task.recurrence && (
                <span className="text-xs flex items-center gap-1 text-[#A1A1AA]">
                  <Repeat className="w-3 h-3" />
                  {task.recurrence === "once" ? "Única" : task.recurrence === "daily" ? "Diária" : task.recurrence === "weekly" ? "Semanal" : "Mensal"}
                </span>
              )}
              <span className="font-data text-xs text-[#007AFF]">+{task.xp_reward} XP</span>
            </div>
          </div>
        </div>
        <Button data-testid={"task-delete-" + task.task_id} variant="ghost" size="icon" onClick={() => onDelete(task.task_id)} className="text-[#FF3B30] hover:text-[#FF3B30] hover:bg-[#FF3B30]/10">
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>
    </Card>
  );
}

export default function Tasks() {
  const [user, setUser] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [selectedDate, setSelectedDate] = useState(getLocalDateStr());
  const [activeTab, setActiveTab] = useState("all");
  const [viewMode, setViewMode] = useState("kanban");
  const [open, setOpen] = useState(false);
  const [newTask, setNewTask] = useState({ title: "", description: "", priority: "medium", recurrence: "once" });

  const fetchUser = async () => {
    try {
      const res = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setUser(res.data);
    } catch (error) {
      toast.error("Erro ao carregar usuário");
    }
  };

  const fetchTasks = useCallback(async () => {
    try {
      const url = activeTab === "all"
        ? `${API}/tasks?date=${selectedDate}`
        : `${API}/tasks?date=${selectedDate}&recurrence=${activeTab}`;
      const res = await axios.get(url, { withCredentials: true });
      setTasks(Array.isArray(res.data) ? res.data : []);
    } catch (error) {
      toast.error("Erro ao carregar tarefas");
    }
  }, [selectedDate, activeTab]);

  useEffect(() => {
    fetchUser();
    fetchTasks();
  }, [selectedDate, activeTab, fetchTasks]);

  const handleCreateTask = async () => {
    if (!newTask.title.trim()) {
      toast.error("Título é obrigatório");
      return;
    }
    try {
      await axios.post(`${API}/tasks`, { ...newTask, date: selectedDate }, { withCredentials: true });
      toast.success("Tarefa criada!");
      setNewTask({ title: "", description: "", priority: "medium", recurrence: "once" });
      setOpen(false);
      fetchTasks();
      fetchUser();
    } catch (error) {
      toast.error("Erro ao criar tarefa");
    }
  };

  const handleToggleTask = async (task) => {
    try {
      const res = await axios.patch(`${API}/tasks/${task.task_id}?completed=${!task.completed}&date=${selectedDate}`, {}, { withCredentials: true });
      if (res.data.xp_earned) {
        toast.success(`+${res.data.xp_earned} XP! ${res.data.new_rank !== user?.rank ? "Novo rank: " + res.data.new_rank + "!" : ""}`);
      }
      fetchTasks();
      fetchUser();
    } catch (error) {
      toast.error("Erro ao atualizar tarefa");
    }
  };

  const handleDeleteTask = async (taskId) => {
    try {
      await axios.delete(`${API}/tasks/${taskId}`, { withCredentials: true });
      toast.success("Tarefa deletada");
      fetchTasks();
    } catch (error) {
      toast.error("Erro ao deletar tarefa");
    }
  };

  const getTaskStatus = (task) => {
    if (task.completed) return "done";
    if (task.status === "in_progress") return "in_progress";
    return "todo";
  };

  const kanbanTasks = {
    todo: tasks.filter(t => getTaskStatus(t) === "todo"),
    in_progress: tasks.filter(t => getTaskStatus(t) === "in_progress"),
    done: tasks.filter(t => getTaskStatus(t) === "done"),
  };

  const handleDragEnd = useCallback(async (result) => {
    if (!result.destination) return;
    const { source, destination, draggableId } = result;
    if (source.droppableId === destination.droppableId && source.index === destination.index) return;

    const newStatus = destination.droppableId;
    const task = tasks.find(t => t.task_id === draggableId);
    if (!task) return;

    // Optimistic update
    setTasks(prev => prev.map(t => {
      if (t.task_id === draggableId) {
        return { ...t, completed: newStatus === "done", status: newStatus };
      }
      return t;
    }));

    try {
      const res = await axios.patch(`${API}/tasks/${draggableId}/status`, {
        status: newStatus,
        date: selectedDate
      }, { withCredentials: true });
      if (res.data.xp_earned > 0) {
        toast.success(`+${res.data.xp_earned} XP!`);
        fetchUser();
      } else if (res.data.xp_earned < 0) {
        fetchUser();
      }
    } catch (error) {
      toast.error("Erro ao mover tarefa");
      fetchTasks();
    }
  }, [tasks, selectedDate, fetchTasks]);

  const totalDone = tasks.filter(t => t.completed).length;
  const totalTasks = tasks.length;

  return (
    <div className="flex min-h-screen bg-[#050505]">
      <Sidebar user={user} />
      <div className="flex-1 ml-0 md:ml-64 page-container pb-24 md:pb-8 pt-[72px] md:pt-0 page-enter">
        <div className="max-w-7xl mx-auto pt-12 md:pt-0">
          {/* Header */}
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-6 md:mb-8 gap-4">
            <div>
              <h1 className="font-heading text-2xl md:text-4xl mb-1 md:mb-2" data-testid="tasks-title">TAREFAS</h1>
              <p className="text-[#A1A1AA] text-sm md:text-base">
                Execute com precisão · <span className="font-data text-white">{totalDone}/{totalTasks}</span> concluídas
              </p>
            </div>
            <div className="flex items-center gap-2 w-full md:w-auto">
              {/* View toggle */}
              <div className="flex bg-[#0A0A0A] border border-[#27272A] rounded-lg p-0.5">
                <button
                  onClick={() => setViewMode("list")}
                  className={"p-1.5 rounded-md transition-colors " + (viewMode === "list" ? "bg-[#007AFF] text-white" : "text-[#52525B] hover:text-white")}
                >
                  <List className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setViewMode("kanban")}
                  className={"p-1.5 rounded-md transition-colors " + (viewMode === "kanban" ? "bg-[#007AFF] text-white" : "text-[#52525B] hover:text-white")}
                >
                  <LayoutGrid className="w-4 h-4" />
                </button>
              </div>
              <Dialog open={open} onOpenChange={setOpen}>
                <DialogTrigger asChild>
                  <Button data-testid="tasks-create-btn" className="bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs tracking-widest shadow-[0_0_10px_rgba(0,122,255,0.3)] flex-1 md:flex-none">
                    <Plus className="w-4 h-4 mr-2" /> Nova Tarefa
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white">
                  <DialogHeader>
                    <DialogTitle className="font-heading text-2xl">CRIAR TAREFA</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 mt-4">
                    <div>
                      <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">Título</Label>
                      <Input data-testid="task-title-input" value={newTask.title} onChange={(e) => setNewTask({ ...newTask, title: e.target.value })} className="bg-[#121212] border-[#27272A] text-white" />
                    </div>
                    <div>
                      <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">Descrição</Label>
                      <Textarea data-testid="task-description-input" value={newTask.description} onChange={(e) => setNewTask({ ...newTask, description: e.target.value })} className="bg-[#121212] border-[#27272A] text-white" />
                    </div>
                    <div>
                      <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">Recorrência</Label>
                      <Select value={newTask.recurrence} onValueChange={(v) => setNewTask({ ...newTask, recurrence: v })}>
                        <SelectTrigger className="bg-[#121212] border-[#27272A] text-white"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="once">Única vez</SelectItem>
                          <SelectItem value="daily">Diária</SelectItem>
                          <SelectItem value="weekly">Semanal</SelectItem>
                          <SelectItem value="monthly">Mensal</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">Prioridade</Label>
                      <Select value={newTask.priority} onValueChange={(v) => setNewTask({ ...newTask, priority: v })}>
                        <SelectTrigger className="bg-[#121212] border-[#27272A] text-white"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="low">Baixa</SelectItem>
                          <SelectItem value="medium">Média</SelectItem>
                          <SelectItem value="high">Alta</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <Button data-testid="task-submit-btn" onClick={handleCreateTask} className="w-full bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs tracking-widest">Criar</Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          {/* Date and Filter */}
          <div className="mb-4 md:mb-6 flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <div className="flex items-center space-x-2 w-full sm:w-auto">
              <Calendar className="w-5 h-5 text-[#007AFF]" />
              <Input type="date" value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)} className="bg-[#0A0A0A] border-[#27272A] text-white font-mono flex-1 sm:flex-none" />
            </div>
            {viewMode === "list" && (
              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full sm:w-auto">
                <TabsList className="bg-[#0A0A0A] border-[#27272A] w-full overflow-x-auto flex-nowrap">
                  <TabsTrigger value="all" className="data-[state=active]:bg-[#007AFF] text-xs">Todas</TabsTrigger>
                  <TabsTrigger value="once" className="data-[state=active]:bg-[#007AFF] text-xs">Única</TabsTrigger>
                  <TabsTrigger value="daily" className="data-[state=active]:bg-[#007AFF] text-xs">Diárias</TabsTrigger>
                  <TabsTrigger value="weekly" className="data-[state=active]:bg-[#007AFF] text-xs">Semanais</TabsTrigger>
                  <TabsTrigger value="monthly" className="data-[state=active]:bg-[#007AFF] text-xs">Mensais</TabsTrigger>
                </TabsList>
              </Tabs>
            )}
          </div>

          {/* KANBAN VIEW */}
          {viewMode === "kanban" && (
            <DragDropContext onDragEnd={handleDragEnd}>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {Object.values(COLUMNS).map((col) => {
                  const ColIcon = col.icon;
                  const colTasks = kanbanTasks[col.id] || [];
                  return (
                    <div key={col.id} className={"bg-[#0A0A0A]/50 border border-[#1A1A1A] rounded-xl p-3"}>
                      <div className="flex items-center justify-between mb-3 px-1">
                        <div className="flex items-center gap-2">
                          <ColIcon className="w-4 h-4" style={{ color: col.color }} />
                          <span className="font-heading text-xs tracking-wider" style={{ color: col.color }}>{col.title}</span>
                        </div>
                        <span className="text-xs font-data text-[#52525B]">{colTasks.length}</span>
                      </div>
                      <Droppable droppableId={col.id}>
                        {(provided, snapshot) => (
                          <div
                            ref={provided.innerRef}
                            {...provided.droppableProps}
                            className={"min-h-[120px] rounded-lg transition-colors p-1 " +
                              (snapshot.isDraggingOver ? "bg-[#121212] border border-dashed border-[#27272A]" : "")
                            }
                          >
                            {colTasks.map((task, idx) => (
                              <TaskCard
                                key={task.task_id}
                                task={task}
                                index={idx}
                                onToggle={handleToggleTask}
                                onDelete={handleDeleteTask}
                                viewMode="kanban"
                              />
                            ))}
                            {provided.placeholder}
                            {colTasks.length === 0 && !snapshot.isDraggingOver && (
                              <div className="flex items-center justify-center h-20 text-[#27272A]">
                                <p className="text-xs">Arraste tarefas aqui</p>
                              </div>
                            )}
                          </div>
                        )}
                      </Droppable>
                    </div>
                  );
                })}
              </div>
            </DragDropContext>
          )}

          {/* LIST VIEW */}
          {viewMode === "list" && (
            <div className="space-y-3">
              {tasks.length === 0 ? (
                <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center">
                  <CheckSquare className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                  <p className="text-[#A1A1AA]">
                    {activeTab === "all" ? "Nenhuma tarefa para esta data" : "Nenhuma tarefa " + (recurrenceLabels[activeTab] || "").toLowerCase()}
                  </p>
                </Card>
              ) : (
                tasks.map((task, idx) => (
                  <TaskCard
                    key={task.task_id}
                    task={task}
                    index={idx}
                    onToggle={handleToggleTask}
                    onDelete={handleDeleteTask}
                    viewMode="list"
                  />
                ))
              )}
            </div>
          )}
        </div>
      </div>
      <MobileNav user={user} />
    </div>
  );
}
