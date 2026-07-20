import { useEffect, useState, useRef, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Bell, Plus, Trash2, Clock, Droplets, Dumbbell, CheckSquare, Settings, BellRing, Calendar, CheckCircle2, Volume2 } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const CATEGORIES = [
  { value: "hydration", label: "Hidratação", color: "#00BFFF" },
  { value: "workout", label: "Treino", color: "#FF6B6B" },
  { value: "habit", label: "Hábitos", color: "#22C55E" },
  { value: "task", label: "Tarefas", color: "#F59E0B" },
  { value: "custom", label: "Personalizado", color: "#A855F7" },
];

const DAYS = [
  { value: "monday", label: "Seg" },
  { value: "tuesday", label: "Ter" },
  { value: "wednesday", label: "Qua" },
  { value: "thursday", label: "Qui" },
  { value: "friday", label: "Sex" },
  { value: "saturday", label: "Sáb" },
  { value: "sunday", label: "Dom" },
];

export default function Notifications() {
  const [user, setUser] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("active");
  const [browserPermission, setBrowserPermission] = useState("default");
  const [recentAlerts, setRecentAlerts] = useState([]);
  const pollingRef = useRef(null);
  
  const [newNotification, setNewNotification] = useState({
    title: "",
    message: "",
    type: "reminder",
    category: "custom",
    scheduled_time: "08:00",
    repeat: "daily",
    repeat_days: [],
    channels: ["in_app", "browser"]
  });

  // Function to trigger browser notification
  const triggerBrowserNotification = useCallback((notif) => {
    // Play sound
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      oscillator.frequency.value = 800;
      oscillator.type = 'sine';
      gainNode.gain.value = 0.3;
      oscillator.start();
      setTimeout(() => { oscillator.stop(); audioCtx.close(); }, 300);
    } catch (e) { /* ignore audio errors */ }

    // Browser notification
    if ("Notification" in window && Notification.permission === "granted") {
      try {
        const n = new Notification(notif.title, {
          body: notif.message || "Hora do lembrete!",
          icon: "/favicon.ico",
          tag: notif.notification_id,
          requireInteraction: true
        });
        n.onclick = () => { window.focus(); n.close(); };
      } catch (e) { console.error("Notification error:", e); }
    }

    // In-app toast
    toast.info(`🔔 ${notif.title}`, {
      description: notif.message || "",
      duration: 10000,
    });

    // Track recent alert
    setRecentAlerts(prev => [
      { ...notif, triggered_at: new Date().toLocaleTimeString('pt-BR') },
      ...prev.slice(0, 9)
    ]);
  }, []);

  // Polling for pending notifications
  const checkPendingNotifications = useCallback(async () => {
    if (!user) return;
    try {
      const tzOffset = new Date().getTimezoneOffset();
      const res = await axios.get(`${API}/notifications/check?timezone_offset=${tzOffset}`, { withCredentials: true });
      const pending = Array.isArray(res.data) ? res.data : [];
      for (const notif of pending) {
        triggerBrowserNotification(notif);
      }
    } catch (err) {
      // silently fail
    }
  }, [user, triggerBrowserNotification]);

  useEffect(() => {
    const load = async () => {
      try {
        const [userRes, notifsRes, templatesRes] = await Promise.all([
          axios.get(`${API}/auth/me`, { withCredentials: true }),
          axios.get(`${API}/notifications`, { withCredentials: true }),
          axios.get(`${API}/notification-templates`, { withCredentials: true })
        ]);
        setUser(userRes.data);
        setNotifications(Array.isArray(notifsRes.data) ? notifsRes.data : []);
        setTemplates(Array.isArray(templatesRes.data) ? templatesRes.data : []);
      } catch (error) {
        console.error("Erro ao carregar dados");
      }
    };
    load();
    if ("Notification" in window) {
      setBrowserPermission(Notification.permission);
    }
  }, []);

  // Start polling when user is loaded
  useEffect(() => {
    if (user) {
      // Check immediately
      checkPendingNotifications();
      // Then check every 30 seconds
      pollingRef.current = setInterval(checkPendingNotifications, 30000);
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [user, checkPendingNotifications]);

  const requestBrowserPermission = async () => {
    if ("Notification" in window) {
      const permission = await Notification.requestPermission();
      setBrowserPermission(permission);
      if (permission === "granted") toast.success("Notificações do navegador ativadas!");
    }
  };

  const handleCreateNotification = async () => {
    if (!newNotification.title.trim()) {
      toast.error("Título é obrigatório");
      return;
    }
    try {
      await axios.post(`${API}/notifications`, newNotification, { withCredentials: true });
      toast.success("Lembrete criado!");
      setNewNotification({ title: "", message: "", type: "reminder", category: "custom", scheduled_time: "08:00", repeat: "daily", repeat_days: [], channels: ["in_app"] });
      setOpen(false);
      const notifsRes = await axios.get(`${API}/notifications`, { withCredentials: true });
      setNotifications(Array.isArray(notifsRes.data) ? notifsRes.data : []);
    } catch (error) {
      toast.error("Erro ao criar lembrete");
    }
  };

  const handleToggleNotification = async (notificationId) => {
    try {
      const res = await axios.patch(`${API}/notifications/${notificationId}/toggle`, {}, { withCredentials: true });
      toast.success(res.data.enabled ? "Lembrete ativado" : "Lembrete desativado");
      const notifsRes = await axios.get(`${API}/notifications`, { withCredentials: true });
      setNotifications(Array.isArray(notifsRes.data) ? notifsRes.data : []);
    } catch (error) {
      toast.error("Erro ao atualizar lembrete");
    }
  };

  const handleDeleteNotification = async (notificationId) => {
    try {
      await axios.delete(`${API}/notifications/${notificationId}`, { withCredentials: true });
      toast.success("Lembrete deletado");
      const notifsRes = await axios.get(`${API}/notifications`, { withCredentials: true });
      setNotifications(Array.isArray(notifsRes.data) ? notifsRes.data : []);
    } catch (error) {
      toast.error("Erro ao deletar lembrete");
    }
  };

  const handleUseTemplate = (template) => {
    setNewNotification({ ...newNotification, title: template.title, message: template.message, category: template.category, scheduled_time: template.suggested_times[0], repeat: template.repeat });
    setOpen(true);
  };

  const toggleChannel = (channel) => {
    if (newNotification.channels.includes(channel)) {
      setNewNotification({ ...newNotification, channels: newNotification.channels.filter(c => c !== channel) });
    } else {
      setNewNotification({ ...newNotification, channels: [...newNotification.channels, channel] });
    }
  };

  const toggleDay = (day) => {
    if (newNotification.repeat_days.includes(day)) {
      setNewNotification({ ...newNotification, repeat_days: newNotification.repeat_days.filter(d => d !== day) });
    } else {
      setNewNotification({ ...newNotification, repeat_days: [...newNotification.repeat_days, day] });
    }
  };

  const getCategoryInfo = (category) => CATEGORIES.find(c => c.value === category) || CATEGORIES[4];
  const getRepeatLabel = (repeat, days) => {
    if (repeat === "none") return "Única vez";
    if (repeat === "daily") return "Diariamente";
    if (days && days.length > 0) return days.map(d => DAYS.find(day => day.value === d)?.label).join(", ");
    return "Personalizado";
  };

  const getCategoryIcon = (cat) => {
    const icons = { hydration: <Droplets className="w-4 h-4" />, workout: <Dumbbell className="w-4 h-4" />, habit: <CheckSquare className="w-4 h-4" />, task: <Calendar className="w-4 h-4" />, custom: <Bell className="w-4 h-4" /> };
    return icons[cat] || icons.custom;
  };

  return (
    <div className="flex min-h-screen bg-[#050505]">
      <Sidebar user={user} />
      <div className="flex-1 ml-0 md:ml-64 p-4 md:p-8 pb-24 md:pb-8 pt-[72px] md:pt-8">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
            <div>
              <h1 className="font-heading text-3xl md:text-4xl mb-2" data-testid="notifications-title">NOTIFICAÇÕES</h1>
              <p className="text-[#A1A1AA]">Configure lembretes personalizados</p>
            </div>
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button data-testid="create-notification-btn" className="bg-[#007AFF] hover:bg-[#0066DD] text-white">
                  <Plus className="w-4 h-4 mr-2" /> Novo Lembrete
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-lg max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle className="font-heading text-xl">CRIAR LEMBRETE</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 mt-4">
                  <div>
                    <Label className="text-xs uppercase tracking-wider">Título</Label>
                    <Input value={newNotification.title} onChange={(e) => setNewNotification({...newNotification, title: e.target.value})} placeholder="Ex: Hora de beber água" className="bg-[#121212] border-[#27272A] text-white mt-1" />
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wider">Mensagem</Label>
                    <Textarea value={newNotification.message} onChange={(e) => setNewNotification({...newNotification, message: e.target.value})} className="bg-[#121212] border-[#27272A] text-white mt-1" />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-xs uppercase tracking-wider">Categoria</Label>
                      <Select value={newNotification.category} onValueChange={(v) => setNewNotification({...newNotification, category: v})}>
                        <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1"><SelectValue /></SelectTrigger>
                        <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                          {CATEGORIES.map(cat => <SelectItem key={cat.value} value={cat.value}>{cat.label}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs uppercase tracking-wider">Horário</Label>
                      <Input type="time" value={newNotification.scheduled_time} onChange={(e) => setNewNotification({...newNotification, scheduled_time: e.target.value})} className="bg-[#121212] border-[#27272A] text-white mt-1" />
                    </div>
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wider">Repetição</Label>
                    <Select value={newNotification.repeat} onValueChange={(v) => setNewNotification({...newNotification, repeat: v})}>
                      <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1"><SelectValue /></SelectTrigger>
                      <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                        <SelectItem value="none">Única vez</SelectItem>
                        <SelectItem value="daily">Diariamente</SelectItem>
                        <SelectItem value="weekly">Semanal</SelectItem>
                        <SelectItem value="custom">Personalizado</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {(newNotification.repeat === "weekly" || newNotification.repeat === "custom") && (
                    <div>
                      <Label className="text-xs uppercase tracking-wider mb-2 block">Dias da Semana</Label>
                      <div className="flex flex-wrap gap-2">
                        {DAYS.map(day => (
                          <Button key={day.value} type="button" variant={newNotification.repeat_days.includes(day.value) ? "default" : "outline"} size="sm" onClick={() => toggleDay(day.value)} className={newNotification.repeat_days.includes(day.value) ? "bg-[#007AFF]" : "border-[#27272A]"}>
                            {day.label}
                          </Button>
                        ))}
                      </div>
                    </div>
                  )}
                  <div>
                    <Label className="text-xs uppercase tracking-wider mb-2 block">Canais</Label>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between bg-[#121212] p-3 rounded">
                        <span className="flex items-center gap-2"><Bell className="w-4 h-4" /> No App</span>
                        <Switch checked={newNotification.channels.includes("in_app")} onCheckedChange={() => toggleChannel("in_app")} />
                      </div>
                      <div className="flex items-center justify-between bg-[#121212] p-3 rounded">
                        <span className="flex items-center gap-2"><BellRing className="w-4 h-4" /> Navegador</span>
                        <Switch checked={newNotification.channels.includes("browser")} onCheckedChange={() => toggleChannel("browser")} />
                      </div>
                    </div>
                  </div>
                  <Button onClick={handleCreateNotification} className="w-full bg-[#007AFF] hover:bg-[#0066DD] text-white">Criar Lembrete</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          {browserPermission !== "granted" && (
            <Card className="bg-[#1A1A2E] border-[#27272A] p-4 mb-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <BellRing className="w-6 h-6 text-[#F59E0B]" />
                  <div>
                    <p className="font-medium">Ativar notificações do navegador</p>
                    <p className="text-sm text-[#A1A1AA]">Receba lembretes mesmo quando não estiver no app</p>
                  </div>
                </div>
                <Button onClick={requestBrowserPermission} className="bg-[#F59E0B] hover:bg-[#D97706] text-black">Ativar</Button>
              </div>
            </Card>
          )}

          {browserPermission === "granted" && (
            <Card className="bg-[#0A2E1A] border-[#27272A] p-4 mb-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="w-6 h-6 text-green-400" />
                  <div>
                    <p className="font-medium text-green-300">Notificações ativadas</p>
                    <p className="text-sm text-[#A1A1AA]">Verificando lembretes a cada 30 segundos</p>
                  </div>
                </div>
                <Button onClick={() => {
                  triggerBrowserNotification({ title: "Teste de Notificação", message: "As notificações estão funcionando!", notification_id: "test" });
                }} variant="outline" size="sm" className="border-green-500 text-green-400 hover:bg-green-500/10">
                  <Volume2 className="w-4 h-4 mr-2" />Testar
                </Button>
              </div>
            </Card>
          )}

          {recentAlerts.length > 0 && (
            <Card className="bg-[#0A0A0A] border-[#27272A] p-4 mb-6">
              <h3 className="font-heading text-sm mb-3 flex items-center gap-2"><BellRing className="w-4 h-4 text-[#00F0FF]" />Alertas Recentes</h3>
              <div className="space-y-2">
                {recentAlerts.map((alert, i) => (
                  <div key={i} className="flex items-center gap-3 p-2 bg-[#121212] rounded-lg">
                    <Bell className="w-4 h-4 text-[#F59E0B]" />
                    <div className="flex-1">
                      <p className="text-sm font-medium">{alert.title}</p>
                      <p className="text-xs text-[#A1A1AA]">{alert.message}</p>
                    </div>
                    <span className="text-xs text-[#52525B]">{alert.triggered_at}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="bg-[#0A0A0A] border border-[#27272A] mb-6 overflow-x-auto flex-nowrap w-full justify-start md:justify-center">
              <TabsTrigger value="active" className="data-[state=active]:bg-[#27272A]"><Bell className="w-4 h-4 mr-2" /> Ativos</TabsTrigger>
              <TabsTrigger value="templates" className="data-[state=active]:bg-[#27272A]"><Settings className="w-4 h-4 mr-2" /> Templates</TabsTrigger>
            </TabsList>

            <TabsContent value="active">
              <div className="grid gap-4">
                {notifications.length === 0 ? (
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center">
                    <Bell className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                    <p className="text-[#A1A1AA]">Nenhum lembrete configurado</p>
                  </Card>
                ) : (
                  notifications.map(notif => {
                    const catInfo = getCategoryInfo(notif.category);
                    return (
                      <Card key={notif.notification_id} className={`bg-[#0A0A0A] border-[#27272A] p-4 ${!notif.enabled ? 'opacity-50' : ''}`}>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: catInfo.color + "20" }}>
                              <span style={{ color: catInfo.color }}>{getCategoryIcon(notif.category)}</span>
                            </div>
                            <div>
                              <h3 className="font-heading">{notif.title}</h3>
                              <div className="flex items-center gap-2 text-sm text-[#A1A1AA]">
                                <Clock className="w-3 h-3" /> {notif.scheduled_time} - {getRepeatLabel(notif.repeat, notif.repeat_days)}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Switch checked={notif.enabled} onCheckedChange={() => handleToggleNotification(notif.notification_id)} />
                            <Button variant="ghost" size="sm" onClick={() => handleDeleteNotification(notif.notification_id)} className="text-red-500">
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      </Card>
                    );
                  })
                )}
              </div>
            </TabsContent>

            <TabsContent value="templates">
              <div className="grid md:grid-cols-2 gap-4">
                {templates.map(template => {
                  const catInfo = getCategoryInfo(template.category);
                  return (
                    <Card key={template.id} className="bg-[#0A0A0A] border-[#27272A] p-4 hover:border-[#007AFF] transition-colors cursor-pointer" onClick={() => handleUseTemplate(template)}>
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0" style={{ backgroundColor: catInfo.color + "20" }}>
                          <span style={{ color: catInfo.color }}>{getCategoryIcon(template.category)}</span>
                        </div>
                        <div className="flex-1">
                          <h3 className="font-heading">{template.title}</h3>
                          <p className="text-sm text-[#A1A1AA] mt-1">{template.message}</p>
                          <div className="flex items-center gap-2 mt-2 text-xs text-[#52525B]">
                            <Clock className="w-3 h-3" /> Sugerido: {(template.suggested_times || []).join(", ")}
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
      <MobileNav user={user} />
    </div>
  );
}
