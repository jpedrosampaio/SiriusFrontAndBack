import { lazy, Suspense } from 'react';
import { readSaved, writeSaved } from "@/lib/session-storage";
import { createActivityRequests } from "@/lib/activity-requests";
import { getCurrentUser } from "@/lib/api";
import { getWorkoutCalendar } from "@/lib/workout-calendar";
import { getApiErrorMessage } from "@/lib/api-errors";
import { useEffect, useState, useCallback, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import PullToRefresh from "@/components/PullToRefresh";
import { getLocalDateStr } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Dumbbell, Plus, Trash2, Play, Check, X, Timer, Flame, TrendingUp, Calendar, FileText, Activity, Edit2, ChevronDown, ChevronUp, Scale, Upload, Sparkles, BarChart3, RefreshCw, Loader2, BookOpen, XCircle, Zap, BookOpenCheck, Star, Square, Clock, Trophy, Heart, ShieldCheck } from "lucide-react";

import axios from "@/lib/module-requests";
import { toast } from "sonner";

const WorkoutsStatsTab = lazy(() => import('@/components/tabs/WorkoutsStatsTab'));
const WorkoutsEvolutionTab = lazy(() => import('@/components/tabs/WorkoutsEvolutionTab'));
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ACTIVITY_TYPES = [
  { value: "weightlifting", label: "Musculação", icon: "💪" },
  { value: "running", label: "Corrida", icon: "🏃" },
  { value: "cycling", label: "Ciclismo", icon: "🚴" },
  { value: "swimming", label: "Natação", icon: "🏊" },
  { value: "yoga", label: "Yoga", icon: "🧘" },
  { value: "hiit", label: "HIIT", icon: "🔥" },
  { value: "other", label: "Outro", icon: "⚡" },
];

export default function Workouts() {
  const [user, setUser] = useState(null);
  const workoutRequests = useRef(createActivityRequests());
  const [sessionSaving, setSessionSaving] = useState(false);
  const workoutBusy = useRef(false);
  const restDeadline = useRef(null);
  const workoutWrite = async (method, url, body) => {
    const key = workoutRequests.current.begin('workout-session', JSON.stringify({ method, url, body }));
    if (!key) throw new Error('Aguarde o registro em andamento');
    workoutBusy.current = true; setSessionSaving(true);
    let succeeded = false;
    try { const response = await axios({ method, url, data: body, headers: { 'Idempotency-Key': key } }); succeeded = true; return response; }
    finally { workoutRequests.current.finish('workout-session', succeeded); workoutBusy.current = false; setSessionSaving(false); }
  };
  const [workouts, setWorkouts] = useState([]);
  const [plans, setPlans] = useState([]);
  const [stats, setStats] = useState(null);
  const [detailedStats, setDetailedStats] = useState(null);
  const [openLog, setOpenLog] = useState(false);
  const [openPlan, setOpenPlan] = useState(false);
  const [openEditPlan, setOpenEditPlan] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [activeTab, setActiveTab] = useState("log");
  useEffect(() => { if (activeTab === 'session') window.scrollTo({ top: 0, behavior: 'auto' }); }, [activeTab]);
  const [expandedWorkouts, setExpandedWorkouts] = useState({});
  const [expandedPlans, setExpandedPlans] = useState({});
  const [dailyStatus, setDailyStatus] = useState({});
  const [motivationalQuote, setMotivationalQuote] = useState(null);
  const [measurements, setMeasurements] = useState([]);
  const [latestMeasurement, setLatestMeasurement] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [aiSuggestions, setAiSuggestions] = useState(null);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [openMeasurement, setOpenMeasurement] = useState(false);
  const [openCompleteWorkout, setOpenCompleteWorkout] = useState(false);
  const [completingPlan, setCompletingPlan] = useState(null);
  const [completeWorkoutData, setCompleteWorkoutData] = useState({ duration_minutes: 45, calories: null, notes: "" });
  const [uploadingPdf, setUploadingPdf] = useState(false);
  const [pdfAnalysis, setPdfAnalysis] = useState(null);
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);
  
  // Import workout + saved insights
  const [importFile, setImportFile] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [savedInsights, setSavedInsights] = useState([]);
  const [showInsightsDialog, setShowInsightsDialog] = useState(false);

  // Today's schedule
  const [todaySchedule, setTodaySchedule] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("sidebar_collapsed") === "true");

  // AI Generation
  const [openAiGenerate, setOpenAiGenerate] = useState(false);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [aiGenMode, setAiGenMode] = useState("tipo_treino"); // "tipo_treino" or "periodo"
  const [aiGenForm, setAiGenForm] = useState({
    objective: "hipertrofia",
    level: "intermediario",
    muscle_groups: [],
    duration: "dia",
    // Split mode fields
    generation_mode: "tipo_treino",
    split_type: "ABC",
    split_config: [
      { label: "A", name: "Peito, Tríceps e Ombro", muscle_groups: ["peito", "triceps", "ombros"] },
      { label: "B", name: "Costas e Bíceps", muscle_groups: ["costas", "biceps"] },
      { label: "C", name: "Pernas e Abdômen", muscle_groups: ["pernas", "abdomen", "gluteos"] }
    ],
    training_days_per_week: 5,
    cycle_weeks: 4,
    include_cardio: false,
    cardio_type: "corrida",
    cardio_mode: "hibrido",
    health_condition: "",
    workout_type: "musculacao",
    running_goal: "5km",
    weekly_frequency: 4,
    preferred_terrain: "asfalto",
    calisthenics_focus: "full_body",
    calisthenics_equipment: "nenhum"
  });

  const SPLIT_OPTIONS = [
    { value: "AB", labels: ["A", "B"] },
    { value: "ABC", labels: ["A", "B", "C"] },
    { value: "ABCD", labels: ["A", "B", "C", "D"] },
    { value: "ABCDE", labels: ["A", "B", "C", "D", "E"] },
  ];

  const ALL_MUSCLE_GROUPS = [
    { value: "peito", label: "Peito", emoji: "🫁" },
    { value: "costas", label: "Costas", emoji: "🔙" },
    { value: "pernas", label: "Pernas", emoji: "🦵" },
    { value: "ombros", label: "Ombros", emoji: "🤷" },
    { value: "biceps", label: "Bíceps", emoji: "💪" },
    { value: "triceps", label: "Tríceps", emoji: "💪" },
    { value: "abdomen", label: "Abdômen", emoji: "🧱" },
    { value: "gluteos", label: "Glúteos", emoji: "🍑" },
    { value: "trapezio", label: "Trapézio", emoji: "🔺" },
    { value: "antebraco", label: "Antebraço", emoji: "✊" },
    { value: "panturrilha", label: "Panturrilha", emoji: "🦶" },
  ];

  const CARDIO_TYPES = [
    { value: "corrida", label: "Corrida", emoji: "🏃" },
    { value: "bike", label: "Bike/Ciclismo", emoji: "🚴" },
    { value: "HIIT", label: "HIIT", emoji: "🔥" },
    { value: "caminhada", label: "Caminhada", emoji: "🚶" },
    { value: "natacao", label: "Natação", emoji: "🏊" },
    { value: "pular_corda", label: "Pular Corda", emoji: "⏭️" },
    { value: "eliptico", label: "Elíptico", emoji: "🏋️" },
    { value: "remo", label: "Remo", emoji: "🚣" },
  ];

  const handleSplitTypeChange = (newSplitType) => {
    const option = SPLIT_OPTIONS.find(o => o.value === newSplitType);
    if (!option) return;
    
    const defaultConfigs = {
      "AB": [
        { label: "A", name: "Superior", muscle_groups: ["peito", "costas", "ombros", "biceps", "triceps"] },
        { label: "B", name: "Inferior", muscle_groups: ["pernas", "gluteos", "abdomen", "panturrilha"] },
      ],
      "ABC": [
        { label: "A", name: "Peito, Tríceps e Ombro", muscle_groups: ["peito", "triceps", "ombros"] },
        { label: "B", name: "Costas e Bíceps", muscle_groups: ["costas", "biceps"] },
        { label: "C", name: "Pernas e Abdômen", muscle_groups: ["pernas", "abdomen", "gluteos"] },
      ],
      "ABCD": [
        { label: "A", name: "Peito e Tríceps", muscle_groups: ["peito", "triceps"] },
        { label: "B", name: "Costas e Bíceps", muscle_groups: ["costas", "biceps"] },
        { label: "C", name: "Ombros e Abdômen", muscle_groups: ["ombros", "abdomen", "trapezio"] },
        { label: "D", name: "Pernas e Glúteos", muscle_groups: ["pernas", "gluteos", "panturrilha"] },
      ],
      "ABCDE": [
        { label: "A", name: "Peito", muscle_groups: ["peito"] },
        { label: "B", name: "Costas", muscle_groups: ["costas", "trapezio"] },
        { label: "C", name: "Ombros e Trapézio", muscle_groups: ["ombros", "trapezio"] },
        { label: "D", name: "Bíceps e Tríceps", muscle_groups: ["biceps", "triceps", "antebraco"] },
        { label: "E", name: "Pernas e Glúteos", muscle_groups: ["pernas", "gluteos", "panturrilha", "abdomen"] },
      ],
    };
    
    setAiGenForm(prev => ({
      ...prev,
      split_type: newSplitType,
      split_config: defaultConfigs[newSplitType] || option.labels.map(l => ({ label: l, name: "", muscle_groups: [] })),
    }));
  };

  const toggleSplitMuscleGroup = (splitIndex, muscleValue) => {
    setAiGenForm(prev => {
      const newConfig = [...prev.split_config];
      const current = newConfig[splitIndex].muscle_groups;
      newConfig[splitIndex] = {
        ...newConfig[splitIndex],
        muscle_groups: current.includes(muscleValue)
          ? current.filter(g => g !== muscleValue)
          : [...current, muscleValue]
      };
      // Auto-update the name based on selected muscle groups
      const selectedLabels = newConfig[splitIndex].muscle_groups.map(
        g => ALL_MUSCLE_GROUPS.find(mg => mg.value === g)?.label || g
      );
      newConfig[splitIndex].name = selectedLabels.join(", ") || "";
      return { ...prev, split_config: newConfig };
    });
  };

  // Workout Session
  const [activeSession, setActiveSession] = useState(null);
  const [sessionElapsed, setSessionElapsed] = useState(0);
  const [restTimer, setRestTimer] = useState(0);
  const [isResting, setIsResting] = useState(false);
  const [restDuration, setRestDuration] = useState(60);
  const [showFeedbackDialog, setShowFeedbackDialog] = useState(false);
  const [feedbackData, setFeedbackData] = useState({ difficulty: 3, feeling: "bom", notes: "" });
  const [expandedTutorials, setExpandedTutorials] = useState({});
  const [exerciseEvoData, setExerciseEvoData] = useState(null);
  const [exerciseFilter, setExerciseFilter] = useState("");
  const [evoLoading, setEvoLoading] = useState(false);
  const [evoError, setEvoError] = useState("");
  const [selectedDays, setSelectedDays] = useState({});
  const [improvingPlan, setImprovingPlan] = useState(null);

  const today = getLocalDateStr();
  
  const [newWorkout, setNewWorkout] = useState({
    activity_type: "weightlifting",
    name: "",
    duration_minutes: 30,
    notes: "",
    date: today,
    plan_id: null,
    exercises_completed: []
  });
  
  const [newPlan, setNewPlan] = useState({ name: "", description: "", exercises: [] });
  const [newExercise, setNewExercise] = useState({ name: "", sets: 3, reps: 12, weight: "" });
  const [editExercise, setEditExercise] = useState({ name: "", sets: 3, reps: 12, weight: "" });
  
  const [newMeasurement, setNewMeasurement] = useState({
    date: today,
    weight_kg: "",
    height_cm: "",
    body_fat_percentage: "",
    muscle_mass_kg: "",
    bone_mass_kg: "",
    water_percentage: "",
    visceral_fat: "",
    metabolic_age: "",
    bmr_kcal: "",
    neck_cm: "",
    shoulders_cm: "",
    chest_cm: "",
    waist_cm: "",
    abdomen_cm: "",
    hips_cm: "",
    left_arm_cm: "",
    right_arm_cm: "",
    left_forearm_cm: "",
    right_forearm_cm: "",
    left_thigh_cm: "",
    right_thigh_cm: "",
    left_calf_cm: "",
    right_calf_cm: "",
    notes: ""
  });

  const loadData = useCallback(async () => {
    try {
      const [userRes, workoutsRes, plansRes] = await Promise.all([
        getCurrentUser(), axios.get(`${API}/workouts`), axios.get(`${API}/workout-plans`),
      ]);
      setUser(userRes.data);
      if (userRes.data.health_condition) setAiGenForm(prev => ({ ...prev, health_condition: userRes.data.health_condition }));
      setWorkouts(Array.isArray(workoutsRes.data) ? workoutsRes.data : []);
      setPlans(Array.isArray(plansRes.data) ? plansRes.data : []);
      void Promise.allSettled([
        ['/workout-stats?period=week', setStats],
        ['/body-measurements/latest', setLatestMeasurement], ['/motivational-quote', setMotivationalQuote],
      ].map(([path, apply]) => axios.get(`${API}${path}`).then(r => apply(r.data || null))));

      // Load daily status for each plan
      // Fetch today's schedule
      try {
        const scheduleRes = await axios.get(`${API}/workouts/today-schedule`, { withCredentials: true });
        if (scheduleRes.data.scheduled) setTodaySchedule(scheduleRes.data);
        else setTodaySchedule(null);
      } catch {}

      const plansData = Array.isArray(plansRes.data) ? plansRes.data : [];
      const statusPromises = plansData.map(plan => 
        axios.get(`${API}/daily-workout-status/${plan.plan_id}`, { withCredentials: true })
          .then(res => ({ planId: plan.plan_id, status: res.data }))
          .catch(() => ({ planId: plan.plan_id, status: { exercises_status: {}, completed: false } }))
      );
      const statuses = await Promise.all(statusPromises);
      const statusMap = {};
      statuses.forEach(s => { statusMap[s.planId] = s.status; });
      setDailyStatus(statusMap);
      
    } catch (error) {
      console.error("Erro ao carregar dados");
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const check = () => setSidebarCollapsed(localStorage.getItem("sidebar_collapsed") === "true");
    window.addEventListener("sidebar-toggle", check);
    window.addEventListener("storage", check);
    return () => { window.removeEventListener("sidebar-toggle", check); window.removeEventListener("storage", check); };
  }, []);

  useEffect(() => {
    if (!['stats', 'evolution'].includes(activeTab)) return;
    const controller = new AbortController();
    const paths = activeTab === 'stats' ? [['/workout-stats/detailed', setDetailedStats]] : [['/body-measurements?limit=30', d => setMeasurements(Array.isArray(d) ? d : [])]];
    paths.forEach(([path, apply]) => axios.get(`${API}${path}`, { signal: controller.signal }).then(r => apply(r.data)).catch(error => { if (!controller.signal.aborted) toast.error(getApiErrorMessage(error, 'Falha ao carregar os dados da aba.')); }));
    return () => controller.abort();
  }, [activeTab]);

  const refreshQuote = async () => {
    try {
      const res = await axios.get(`${API}/motivational-quote`, { withCredentials: true });
      setMotivationalQuote(res.data);
    } catch (error) {
      console.error("Erro ao atualizar frase");
    }
  };

  const getAiSuggestions = async () => {
    setLoadingSuggestions(true);
    try {
      const res = await axios.post(`${API}/workout-suggestions`, {}, { withCredentials: true });
      setAiSuggestions(res.data);
      toast.success("Sugestões geradas com sucesso!");
    } catch (error) {
      toast.error("Erro ao gerar sugestões. Tente novamente.");
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const toggleDailyExercise = async (planId, exerciseIdx) => {
    try {
      const res = await axios.post(`${API}/daily-workout-status/${planId}/toggle/${exerciseIdx}`, {}, { withCredentials: true });
      setDailyStatus(prev => ({ ...prev, [planId]: res.data }));
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao atualizar exercício"));
      if (error.response?.status === 409) checkActiveSession();
    }
  };

  const resetDailyWorkout = async (planId) => {
    try {
      await axios.post(`${API}/daily-workout-status/${planId}/reset`, {}, { withCredentials: true });
      setDailyStatus(prev => ({ ...prev, [planId]: { exercises_status: {}, completed: false } }));
      toast.success("Treino do dia resetado");
    } catch (error) {
      toast.error("Erro ao resetar treino");
    }
  };

  const openCompleteDialog = (plan) => {
    const status = dailyStatus[plan.plan_id] || {};
    const completedCount = Object.values(status.exercises_status || {}).filter(Boolean).length;
    const estimatedDuration = Math.max(30, completedCount * 5 + 15);
    const estimatedCalories = Math.round(estimatedDuration * 6);
    
    setCompletingPlan(plan);
    setCompleteWorkoutData({
      duration_minutes: estimatedDuration,
      calories: estimatedCalories,
      notes: ""
    });
    setOpenCompleteWorkout(true);
  };

  const handleCompleteWorkout = async () => {
    if (!completingPlan) return;
    
    try {
      const res = await axios.post(
        `${API}/daily-workout-status/${completingPlan.plan_id}/complete`,
        completeWorkoutData,
        { withCredentials: true }
      );
      
      toast.success(`Treino concluído! +${res.data.xp_earned} XP (${res.data.exercises_completed_count}/${res.data.total_exercises} exercícios)`);
      setOpenCompleteWorkout(false);
      setCompletingPlan(null);
      
      // Reload data
      loadData();
    } catch (error) {
      toast.error("Erro ao concluir treino");
    }
  };

  const handleSelectPlan = (planId) => {
    const plan = plans.find(p => p.plan_id === planId);
    if (plan) {
      setNewWorkout({
        ...newWorkout,
        plan_id: planId,
        name: plan.name || 'Treino',
        exercises_completed: (plan.exercises || []).map(ex => ({
          ...ex,
          completed: false
        }))
      });
    } else {
      setNewWorkout({
        ...newWorkout,
        plan_id: null,
        exercises_completed: []
      });
    }
  };

  const toggleExerciseInNewWorkout = (index) => {
    const updated = [...newWorkout.exercises_completed];
    updated[index] = { ...updated[index], completed: !updated[index].completed };
    setNewWorkout({ ...newWorkout, exercises_completed: updated });
  };

  const handleLogWorkout = async () => {
    if (!newWorkout.name.trim()) {
      toast.error("Nome do treino é obrigatório");
      return;
    }
    try {
      const res = await axios.post(`${API}/workouts`, newWorkout, { withCredentials: true });
      toast.success(`Treino registrado! +${res.data.xp_earned} XP`);
      setNewWorkout({ activity_type: "weightlifting", name: "", duration_minutes: 30, notes: "", date: today, plan_id: null, exercises_completed: [] });
      setOpenLog(false);
      loadData();
    } catch (error) {
      toast.error("Erro ao registrar treino");
    }
  };

  const handleToggleWorkout = async (logId) => {
    try {
      const res = await axios.patch(`${API}/workouts/${logId}/toggle`, {}, { withCredentials: true });
      toast.success(res.data.completed ? `+${res.data.xp_change} XP` : `${res.data.xp_change} XP`);
      loadData();
    } catch (error) {
      toast.error("Erro ao atualizar treino");
    }
  };

  const handleDeleteWorkout = async (logId) => {
    try {
      await axios.delete(`${API}/workouts/${logId}`, { withCredentials: true });
      toast.success("Treino deletado");
      loadData();
    } catch (error) {
      toast.error("Erro ao deletar treino");
    }
  };

  const handleCreatePlan = async () => {
    if (!newPlan.name.trim()) {
      toast.error("Nome da ficha é obrigatório");
      return;
    }
    try {
      await axios.post(`${API}/workout-plans`, newPlan, { withCredentials: true });
      toast.success("Ficha de treino criada!");
      setNewPlan({ name: "", description: "", exercises: [] });
      setOpenPlan(false);
      loadData();
    } catch (error) {
      toast.error("Erro ao criar ficha");
    }
  };

  const handleUpdatePlan = async () => {
    if (!editingPlan || !editingPlan.name.trim()) {
      toast.error("Nome da ficha é obrigatório");
      return;
    }
    try {
      await axios.patch(`${API}/workout-plans/${editingPlan.plan_id}`, {
        name: editingPlan.name,
        description: editingPlan.description,
        exercises: editingPlan.exercises
      }, { withCredentials: true });
      toast.success("Ficha atualizada!");
      setOpenEditPlan(false);
      setEditingPlan(null);
      loadData();
    } catch (error) {
      toast.error("Erro ao atualizar ficha");
    }
  };

  const handleDeletePlan = async (planId) => {
    try {
      await axios.delete(`${API}/workout-plans/${planId}`, { withCredentials: true });
      toast.success("Ficha deletada");
      loadData();
    } catch (error) {
      toast.error("Erro ao deletar ficha");
    }
  };

  const openEditDialog = (plan) => {
    setEditingPlan({ ...plan });
    setEditExercise({ name: "", sets: 3, reps: 12, weight: "" });
    setOpenEditPlan(true);
  };

  const addExerciseToPlan = () => {
    if (!newExercise.name.trim()) return;
    setNewPlan({ ...newPlan, exercises: [...newPlan.exercises, { ...newExercise }] });
    setNewExercise({ name: "", sets: 3, reps: 12, weight: "" });
  };

  const removeExerciseFromPlan = (index) => {
    setNewPlan({ ...newPlan, exercises: newPlan.exercises.filter((_, i) => i !== index) });
  };

  const addExerciseToEditPlan = () => {
    if (!editExercise.name.trim()) return;
    setEditingPlan({ ...editingPlan, exercises: [...editingPlan.exercises, { ...editExercise }] });
    setEditExercise({ name: "", sets: 3, reps: 12, weight: "" });
  };

  const removeExerciseFromEditPlan = (index) => {
    setEditingPlan({ ...editingPlan, exercises: editingPlan.exercises.filter((_, i) => i !== index) });
  };

  const updateExerciseInEditPlan = (index, field, value) => {
    const updated = [...editingPlan.exercises];
    updated[index] = { ...updated[index], [field]: field === 'sets' || field === 'reps' ? parseInt(value) || 0 : value };
    setEditingPlan({ ...editingPlan, exercises: updated });
  };

  const toggleWorkoutExpanded = (logId) => {
    setExpandedWorkouts(prev => ({ ...prev, [logId]: !prev[logId] }));
  };

  const togglePlanExpanded = (planId) => {
    setExpandedPlans(prev => ({ ...prev, [planId]: !prev[planId] }));
  };

  const handleCreateMeasurement = async () => {
    try {
      const dataToSend = { ...newMeasurement };
      // Convert empty strings to null
      Object.keys(dataToSend).forEach(key => {
        if (dataToSend[key] === "") dataToSend[key] = null;
        else if (key !== "date" && key !== "notes" && key !== "source" && dataToSend[key]) {
          dataToSend[key] = parseFloat(dataToSend[key]);
        }
      });
      
      await axios.post(`${API}/body-measurements`, dataToSend, { withCredentials: true });
      toast.success("Medidas registradas!");
      setOpenMeasurement(false);
      setNewMeasurement({
        date: today, weight_kg: "", height_cm: "", body_fat_percentage: "", muscle_mass_kg: "",
        bone_mass_kg: "", water_percentage: "", visceral_fat: "", metabolic_age: "", bmr_kcal: "",
        neck_cm: "", shoulders_cm: "", chest_cm: "", waist_cm: "", abdomen_cm: "", hips_cm: "",
        left_arm_cm: "", right_arm_cm: "", left_forearm_cm: "", right_forearm_cm: "",
        left_thigh_cm: "", right_thigh_cm: "", left_calf_cm: "", right_calf_cm: "", notes: ""
      });
      loadData();
    } catch (error) {
      toast.error("Erro ao registrar medidas");
    }
  };

  const handlePdfUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    setUploadingPdf(true);
    setPdfAnalysis(null);
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const res = await axios.post(`${API}/body-measurements/analyze-pdf`, formData, {
        withCredentials: true,
        headers: { "Content-Type": "multipart/form-data" }
      });
      
      setPdfAnalysis(res.data);
      
      if (res.data.extracted_data && !res.data.extracted_data.parse_error) {
        const data = res.data.extracted_data;
        setNewMeasurement(prev => ({
          ...prev,
          weight_kg: data.weight_kg || prev.weight_kg,
          height_cm: data.height_cm || prev.height_cm,
          body_fat_percentage: data.body_fat_percentage || prev.body_fat_percentage,
          muscle_mass_kg: data.muscle_mass_kg || prev.muscle_mass_kg,
          bone_mass_kg: data.bone_mass_kg || prev.bone_mass_kg,
          water_percentage: data.water_percentage || prev.water_percentage,
          visceral_fat: data.visceral_fat || prev.visceral_fat,
          metabolic_age: data.metabolic_age || prev.metabolic_age,
          bmr_kcal: data.bmr_kcal || prev.bmr_kcal,
          neck_cm: data.neck_cm || prev.neck_cm,
          shoulders_cm: data.shoulders_cm || prev.shoulders_cm,
          chest_cm: data.chest_cm || prev.chest_cm,
          waist_cm: data.waist_cm || prev.waist_cm,
          abdomen_cm: data.abdomen_cm || prev.abdomen_cm,
          hips_cm: data.hips_cm || prev.hips_cm,
          left_arm_cm: data.left_arm_cm || prev.left_arm_cm,
          right_arm_cm: data.right_arm_cm || prev.right_arm_cm,
          left_forearm_cm: data.left_forearm_cm || prev.left_forearm_cm,
          right_forearm_cm: data.right_forearm_cm || prev.right_forearm_cm,
          left_thigh_cm: data.left_thigh_cm || prev.left_thigh_cm,
          right_thigh_cm: data.right_thigh_cm || prev.right_thigh_cm,
          left_calf_cm: data.left_calf_cm || prev.left_calf_cm,
          right_calf_cm: data.right_calf_cm || prev.right_calf_cm,
          notes: data.notes || prev.notes,
          source: "pdf_import"
        }));
        toast.success("Dados extraídos do PDF com sucesso!");
      }
    } catch (error) {
      toast.error("Erro ao analisar PDF");
    } finally {
      setUploadingPdf(false);
    }
  };


  // Import workout from file
  const handleImportWorkout = async () => {
    if (!importFile) { toast.error("Selecione um arquivo"); return; }
    setImportLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", importFile);
      const res = await axios.post(`${API}/workouts/import-plan`, formData, {
        withCredentials: true, headers: { "Content-Type": "multipart/form-data" }, timeout: 120000
      });
      toast.success(res.data.message || "Treino importado!");
      setImportFile(null);
      setShowImportDialog(false);
      // Refresh plans
      const plansRes = await axios.get(`${API}/workout-plans`, { withCredentials: true });
      setPlans(Array.isArray(plansRes.data) ? plansRes.data : []);
    } catch (err) { toast.error(getApiErrorMessage(err, "Erro ao importar treino")); }
    finally { setImportLoading(false); }
  };

  // Save AI suggestion
  const handleSaveInsight = async (content) => {
    try {
      await axios.post(`${API}/workout-suggestions/save`, { title: "Sugestão de Treino", content }, { withCredentials: true });
      toast.success("Sugestão salva!");
      fetchSavedInsights();
    } catch { toast.error("Erro ao salvar sugestão"); }
  };

  const fetchSavedInsights = async () => {
    try {
      const res = await axios.get(`${API}/workout-suggestions/saved`, { withCredentials: true });
      setSavedInsights(Array.isArray(res.data) ? res.data : []);
    } catch {}
  };

  const handleDeleteInsight = async (id) => {
    try {
      await axios.delete(`${API}/workout-suggestions/saved/${id}`, { withCredentials: true });
      setSavedInsights(prev => prev.filter(i => i.insight_id !== id));
    } catch { toast.error("Erro ao remover"); }
  };

  const fetchExerciseEvolution = async (exerciseName) => {
    setEvoLoading(true);
    setEvoError("");
    try {
      const params = exerciseName ? `?exercise_name=${encodeURIComponent(exerciseName)}` : "";
      const res = await axios.get(`${API}/workout-stats/exercise-evolution${params}`, { withCredentials: true });
      setExerciseEvoData(res.data.exercises || {});
    } catch {
      setEvoError("Erro ao buscar evolução");
    } finally {
      setEvoLoading(false);
    }
  };

  // === AI GENERATION ===
  const handleGenerateWithAI = async () => {
    setGeneratingPlan(true);
    try {
      const payload = {
        objective: aiGenForm.objective,
        level: aiGenForm.level,
        workout_type: aiGenForm.workout_type,
        generation_mode: aiGenMode,
        health_condition: aiGenForm.health_condition || null,
      };
      
      if (aiGenForm.workout_type === "corrida") {
        payload.generation_mode = "periodo";
        payload.running_goal = aiGenForm.running_goal;
        payload.weekly_frequency = aiGenForm.weekly_frequency;
        payload.preferred_terrain = aiGenForm.preferred_terrain;
        payload.duration = aiGenForm.duration;
      } else if (aiGenForm.workout_type === "calistenia") {
        payload.calisthenics_focus = aiGenForm.calisthenics_focus;
        payload.calisthenics_equipment = aiGenForm.calisthenics_equipment;
        payload.duration = aiGenForm.duration;
        payload.generation_mode = "periodo";
      } else if (aiGenMode === "tipo_treino") {
        payload.split_type = aiGenForm.split_type;
        payload.split_config = aiGenForm.split_config;
        payload.training_days_per_week = aiGenForm.training_days_per_week;
        payload.cycle_weeks = aiGenForm.cycle_weeks;
        payload.include_cardio = aiGenForm.include_cardio;
        payload.cardio_type = aiGenForm.include_cardio ? aiGenForm.cardio_type : null;
        payload.cardio_mode = aiGenForm.include_cardio ? aiGenForm.cardio_mode : null;
        payload.duration = "ciclo";
      } else {
        payload.duration = aiGenForm.duration;
        payload.muscle_groups = aiGenForm.muscle_groups;
      }
      
      const res = await axios.post(`${API}/workout-plans/generate`, payload, { withCredentials: true, timeout: 300000 });
      if (res.data.success) {
        toast.success(`Treino gerado com IA! +${res.data.xp_earned} XP`);
        setOpenAiGenerate(false);
        setAiGenForm(prev => ({
          ...prev,
          objective: "hipertrofia",
          level: "intermediario",
          muscle_groups: [],
          duration: "dia",
          workout_type: "musculacao",
          running_goal: "5km",
          weekly_frequency: 4,
          preferred_terrain: "asfalto",
          calisthenics_focus: "full_body",
          calisthenics_equipment: "nenhum"
        }));
        loadData();
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao gerar treino com IA"));
    } finally {
      setGeneratingPlan(false);
    }
  };

  const toggleMuscleGroup = (group) => {
    setAiGenForm(prev => ({
      ...prev,
      muscle_groups: prev.muscle_groups.includes(group)
        ? prev.muscle_groups.filter(g => g !== group)
        : [...prev.muscle_groups, group]
    }));
  };

  // === IMPROVE WORKOUT ===
  const handleImproveWorkout = async (planId) => {
    setImprovingPlan(planId);
    try {
      const res = await axios.post(`${API}/workout-plans/${planId}/improve`, {}, { withCredentials: true, timeout: 300000 });
      if (res.data.success) {
        toast.success(`Treino evoluído! +${res.data.xp_earned} XP`);
        if (res.data.improvements_summary) {
          toast.info(res.data.improvements_summary, { duration: 8000 });
        }
        loadData();
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao melhorar treino"));
    } finally {
      setImprovingPlan(null);
    }
  };

  // === WORKOUT SESSION ===
  const checkActiveSession = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/workout-sessions/active`, { withCredentials: true });
      if (res.data.active) {
        setActiveSession(res.data.session);
        // Calculate elapsed time
        const started = new Date(res.data.session.started_at);
        const elapsed = Math.floor((Date.now() - started.getTime()) / 1000);
        setSessionElapsed(elapsed);
      }
    } catch {}
  }, []);

  useEffect(() => {
    checkActiveSession();
  }, [checkActiveSession]);

  // Timestamp-based clocks remain accurate after the browser suspends a tab.
  useEffect(() => {
    if (activeSession?.status !== 'active') return;
    const tick = () => setSessionElapsed(Math.max(0, Math.floor((Date.now() - new Date(activeSession.started_at).getTime()) / 1000)));
    tick(); const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [activeSession?.session_id, activeSession?.started_at, activeSession?.status]);
  useEffect(() => {
    if (!activeSession || !user) return;
    const deadline = readSaved(`sirius-rest:${user.user_id}:${activeSession.session_id}`);
    if (Number.isFinite(deadline) && deadline > Date.now()) { restDeadline.current = deadline; setRestTimer(Math.ceil((deadline - Date.now()) / 1000)); setIsResting(true); }
  }, [activeSession?.session_id, user?.user_id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!isResting) return;
    const tick = () => {
      const left = Math.max(0, Math.ceil((restDeadline.current - Date.now()) / 1000));
      setRestTimer(left);
      if (!left) { setIsResting(false); toast.success('Descanso finalizado. Próxima série!'); }
    };
    tick(); const interval = setInterval(tick, 500);
    return () => clearInterval(interval);
  }, [isResting]);

  const handleStartWorkout = async (plan, dayIdx = 0) => {
    if (workoutBusy.current) return;
    try {
      const res = await workoutWrite("post", `${API}/workout-sessions/start`, {
        plan_id: plan.plan_id,
        day_index: dayIdx,
        rest_timer_seconds: restDuration
      });
      setActiveSession(res.data);
      setSessionElapsed(0);
      setActiveTab("session");
      setExerciseHistory({});
      fetchNextLoads(plan.plan_id);
      toast.success("Treino iniciado! Bora! 💪");
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao iniciar treino"));
    }
  };

  const handleToggleSessionExercise = async (idx) => {
    if (workoutBusy.current) return;
    if (!activeSession) return;
    const ex = activeSession.exercises[idx];
    const newCompleted = !ex.completed;
    const newSetsCompleted = newCompleted ? ex.sets : 0;
    
    try {
      const res = await workoutWrite("patch",
        `${API}/workout-sessions/${activeSession.session_id}/exercise/${idx}`,
        { completed: newCompleted, sets_completed: newSetsCompleted, current_exercise_idx: idx, revision: activeSession.revision || 0 }
      );
      setActiveSession(res.data);
      
      if (newCompleted) {
        toast.success(`${ex.name} concluído! ✅`);
        // Auto-start rest timer for next exercise
        const nextIdx = activeSession.exercises.findIndex((e, i) => i > idx && !e.completed);
        if (nextIdx >= 0) {
          startRestManual(ex.rest_seconds || restDuration);
        }
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao atualizar exercício"));
      if (error.response?.status === 409) checkActiveSession();
    }
  };

  const [setInputIdx, setSetInputIdx] = useState(null); // index of exercise awaiting set weight input
  const [setInputWeight, setSetInputWeight] = useState("");
  const [setInputReps, setSetInputReps] = useState("");
  const [setInputRpe, setSetInputRpe] = useState(""); // RPE for current set
  const setDraftKey = user && activeSession ? `sirius-workout-draft:${user.user_id}:${activeSession.session_id}` : null;
  const restoredDraftKey = useRef(null);
  useEffect(() => {
    if (!setDraftKey || restoredDraftKey.current === setDraftKey) return;
    const draft = readSaved(setDraftKey);
    if (draft) { setSetInputIdx(draft.index); setSetInputWeight(draft.weight || ''); setSetInputRpe(draft.rpe || ''); setSetInputReps(draft.reps || ''); }
    restoredDraftKey.current = setDraftKey;
  }, [setDraftKey]);
  useEffect(() => {
    if (!setDraftKey || restoredDraftKey.current !== setDraftKey) return;
    if (setInputIdx !== null) writeSaved(setDraftKey, { index: setInputIdx, weight: setInputWeight, rpe: setInputRpe, reps: setInputReps });
  }, [setDraftKey, setInputIdx, setInputWeight, setInputRpe, setInputReps]);
  const [nextLoads, setNextLoads] = useState(null); // suggested next weights
  const [exerciseHistory, setExerciseHistory] = useState({}); // {exerciseIdx: history}

  const handleIncrementSets = async (idx) => {
    if (!activeSession) return;
    const ex = activeSession.exercises[idx];
    // Show weight input before completing the set
    setSetInputIdx(idx);
    setSetInputReps(String(ex.reps || 12).match(/\d+/)?.[0] || '12');
    setSetInputWeight(ex.sets_data?.length > 0 ? ex.sets_data[ex.sets_data.length-1]?.weight || ex.weight || "" : ex.weight || "");
    setSetInputRpe(ex.sets_data?.length > 0 ? ex.sets_data[ex.sets_data.length-1]?.rpe || "" : "");
  };

  const confirmSet = async (idx) => {
    if (workoutBusy.current) return;
    if (!activeSession) return;
    const ex = activeSession.exercises[idx];
    const reps = Number(setInputReps);
    if (!Number.isInteger(reps) || reps < 1 || reps > 999) { toast.error('Informe de 1 a 999 repetições.'); return; }
    if (setInputRpe && (!Number.isFinite(Number(setInputRpe)) || Number(setInputRpe) < 1 || Number(setInputRpe) > 10)) { toast.error('O esforço percebido deve estar entre 1 e 10.'); return; }
    const setsData = [...(ex.sets_data || [])];
    const newSet = {
      weight: setInputWeight,
      reps,
      completed: true,
      rpe: setInputRpe || ""
    };
    setsData.push(newSet);
    const newSetsCompleted = setsData.length;
    const allSetsCompleted = newSetsCompleted >= (ex.sets || 1);
    
    try {
      const res = await workoutWrite("patch",
        `${API}/workout-sessions/${activeSession.session_id}/exercise/${idx}`,
        { sets_data: setsData, completed: allSetsCompleted, revision: activeSession.revision || 0 }
      );
      setActiveSession(res.data);
      if (setDraftKey) writeSaved(setDraftKey, null);
      setSetInputIdx(null);
      setSetInputWeight("");
      setSetInputRpe("");
      
      if (allSetsCompleted) {
        toast.success(`${ex.name} - Todas as séries concluídas! ✅`);
      } else {
        startRestManual(ex.rest_seconds || restDuration);
        toast.info(`Série ${newSetsCompleted}/${ex.sets} concluída. Descanse!`);
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Não foi possível salvar a série. Seus campos foram preservados."));
      if (error.response?.status === 409) checkActiveSession();
    }
  };

  const fetchNextLoads = async (planId) => {
    try {
      const res = await axios.get(`${API}/workouts/next-loads`, { params: { plan_id: planId }, withCredentials: true });
      setNextLoads(res.data);
    } catch {}
  };

  const fetchExerciseHistory = async (exerciseName, idx) => {
    if (!exerciseName) return;
    try {
      const res = await axios.get(`${API}/workouts/exercise-history`, { params: { exercise_name: exerciseName }, withCredentials: true });
      setExerciseHistory(prev => ({ ...prev, [idx]: res.data.history }));
    } catch {}
  };

  const startRestManual = (seconds) => {
    const duration = Math.max(1, Number(seconds || restDuration));
    restDeadline.current = Date.now() + duration * 1000;
    if (activeSession && user) writeSaved(`sirius-rest:${user.user_id}:${activeSession.session_id}`, restDeadline.current);
    setRestTimer(duration); setIsResting(true);
  };

  const stopRest = () => {
    restDeadline.current = null;
    if (activeSession && user) writeSaved(`sirius-rest:${user.user_id}:${activeSession.session_id}`, null);
    setRestTimer(0);
    setIsResting(false);
  };

  const handleCompleteSession = async () => {
    if (workoutBusy.current) return;
    if (!activeSession) return;
    try {
      const res = await workoutWrite("post",
        `${API}/workout-sessions/${activeSession.session_id}/complete`,
        feedbackData
      );
      toast.success(`Treino concluído! +${res.data.xp_earned} XP 🏆`);
      setShowFeedbackDialog(false);
      stopRest();
      setActiveSession(null);
      setSessionElapsed(0);
      setFeedbackData({ difficulty: 3, feeling: "bom", notes: "" });
      setActiveTab("log");
      loadData();
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Não foi possível confirmar a conclusão. Tente novamente."));
    }
  };

  const handleAbandonSession = async () => {
    if (workoutBusy.current) return;
    if (!activeSession) return;
    try {
      await workoutWrite("post", `${API}/workout-sessions/${activeSession.session_id}/abandon`, {});
      toast.info("Sessão abandonada");
      stopRest();
      setActiveSession(null);
      setSessionElapsed(0);
      setActiveTab("plans");
    } catch (error) {
      toast.error("Erro ao abandonar sessão");
    }
  };

  const formatTime = (seconds) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const toggleTutorial = (key) => {
    setExpandedTutorials(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const getSessionProgress = () => {
    if (!activeSession) return { completed: 0, total: 0, percent: 0 };
    const exercises = activeSession.exercises || [];
    const completed = exercises.filter(e => e.completed).length;
    return { completed, total: exercises.length, percent: exercises.length > 0 ? Math.round((completed / exercises.length) * 100) : 0 };
  };


  const loadRecommendations = async () => {
    setLoadingRecommendations(true);
    try {
      const res = await axios.get(`${API}/body-measurements/recommendations`, { withCredentials: true });
      setRecommendations(res.data);
    } catch (error) {
      toast.error("Erro ao carregar recomendações");
    } finally {
      setLoadingRecommendations(false);
    }
  };

  const getActivityIcon = (type) => ACTIVITY_TYPES.find(a => a.value === type)?.icon || "⚡";
  const getActivityLabel = (type) => ACTIVITY_TYPES.find(a => a.value === type)?.label || type;

  const getCompletedCount = (exercises) => {
    if (!exercises || exercises.length === 0) return { completed: 0, total: 0 };
    const completed = exercises.filter(ex => ex.completed).length;
    return { completed, total: exercises.length };
  };

  const getDailyCompletedCount = (planId, totalExercises) => {
    const status = dailyStatus[planId];
    if (!status) return { completed: 0, total: totalExercises };
    const completed = Object.values(status.exercises_status || {}).filter(Boolean).length;
    return { completed, total: totalExercises };
  };

  const WorkoutCard = ({ workout, showDate = false }) => {
    const isExpanded = expandedWorkouts[workout.log_id];
    const hasExercises = workout.exercises_completed && workout.exercises_completed.length > 0;
    const { completed: completedExercises, total: totalExercises } = getCompletedCount(workout.exercises_completed);

    return (
      <Card key={workout.log_id} className={`bg-[#0A0A0A] border-[#27272A] p-4 ${!workout.completed ? 'opacity-50' : ''}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 flex-1">
            <span className="text-3xl">{getActivityIcon(workout.activity_type)}</span>
            <div className="flex-1">
              <h3 className="font-heading text-lg">{workout.name}</h3>
              <p className="text-sm text-[#A1A1AA]">
                {showDate ? `${workout.date} - ` : ''}{getActivityLabel(workout.activity_type)} - {workout.duration_minutes} min
                {workout.calories && <span className="ml-2">🔥 {workout.calories} kcal</span>}
                {hasExercises && (
                  <span className="ml-2 text-[#00F0FF]">
                    ({completedExercises}/{totalExercises} exercícios)
                  </span>
                )}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[#00F0FF] font-mono text-sm">{workout.completed ? '+' : ''}{workout.xp_earned} XP</span>
            {hasExercises && (
              <Button variant="ghost" size="sm" onClick={() => toggleWorkoutExpanded(workout.log_id)} className="text-[#A1A1AA]">
                {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={() => handleToggleWorkout(workout.log_id)} className={workout.completed ? "text-green-500" : "text-gray-500"}>
              {workout.completed ? <Check className="w-5 h-5" /> : <X className="w-5 h-5" />}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => handleDeleteWorkout(workout.log_id)} className="text-red-500">
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
        
        {hasExercises && isExpanded && (
          <div className="mt-4 border-t border-[#27272A] pt-4 space-y-2">
            <Label className="text-xs uppercase tracking-wider text-[#A1A1AA]">Exercícios do Treino</Label>
            {(workout.exercises_completed || []).map((ex, idx) => (
              <div key={idx} className={`flex items-center gap-3 p-2 rounded ${ex.completed ? 'bg-[#121212]' : 'bg-[#0A0A0A] border border-[#27272A]'}`}>
                <div className={`w-5 h-5 rounded border flex items-center justify-center ${ex.completed ? 'bg-[#00F0FF] border-[#00F0FF]' : 'border-[#52525B]'}`}>
                  {ex.completed && <Check className="w-3 h-3 text-black" />}
                </div>
                <span className={`font-mono text-sm flex-1 ${ex.completed ? 'text-white' : 'text-[#A1A1AA]'}`}>
                  {ex.name} - {ex.sets}x{ex.reps} {ex.weight && `@ ${ex.weight}`}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    );
  };

  return (
    <div className="flex min-h-screen bg-[#050505]" data-workout-executing={activeTab === 'session'}>
      <Sidebar user={user} />
      <div className={`flex-1 ml-0 ${sidebarCollapsed ? 'md:ml-16' : 'md:ml-64'} p-4 md:p-6 lg:p-8 pb-24 md:pb-8 pt-[72px] md:pt-0 page-enter`}>
        <PullToRefresh onRefresh={loadData}>
        <div className="max-w-6xl mx-auto">
          {/* Motivational Quote */}
          {motivationalQuote && (
            <Card className="bg-gradient-to-r from-[#0A0A0A] to-[#1a1a2e] border-[#27272A] p-4 mb-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Sparkles className="w-6 h-6 text-[#00F0FF]" />
                  <p className="text-lg italic text-white">{motivationalQuote.quote}</p>
                </div>
                <Button variant="ghost" size="sm" onClick={refreshQuote} className="text-[#A1A1AA]">
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
            </Card>
          )}

          <div className="sirius-page-heading sirius-hero flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
            <div>
              <div className="sirius-eyebrow">Movimento e constância</div>
              <h1 className="font-heading text-3xl md:text-4xl mb-2" data-testid="workouts-title">Seu próximo passo começa aqui.</h1>
              <p className="text-[#A1A1AA]">Seus treinos, suas marcas e a evolução de cada semana.</p>
            </div>
            <div className="flex gap-2 flex-wrap">
              <Dialog open={openLog} onOpenChange={setOpenLog}>
                <DialogTrigger asChild>
                  <Button data-testid="log-workout-btn" className="bg-[#00F0FF] hover:bg-[#00D4E5] text-black">
                    <Play className="w-4 h-4 mr-2" /> Registrar Treino
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-lg max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="font-heading text-xl">REGISTRAR TREINO</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 mt-4">
                    {plans.length > 0 && (
                      <div>
                        <Label className="text-xs uppercase tracking-wider">Usar Ficha de Treino</Label>
                        <Select value={newWorkout.plan_id || "none"} onValueChange={(v) => handleSelectPlan(v === "none" ? null : v)}>
                          <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                            <SelectValue placeholder="Selecione uma ficha (opcional)" />
                          </SelectTrigger>
                          <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                            <SelectItem value="none">Treino Livre</SelectItem>
                            {plans.map(plan => (
                              <SelectItem key={plan.plan_id} value={plan.plan_id}>{plan.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                    
                    <div>
                      <Label className="text-xs uppercase tracking-wider">Tipo de Atividade</Label>
                      <Select value={newWorkout.activity_type} onValueChange={(v) => setNewWorkout({...newWorkout, activity_type: v})}>
                        <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                          {ACTIVITY_TYPES.map(type => (
                            <SelectItem key={type.value} value={type.value}>{type.icon} {type.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs uppercase tracking-wider">Nome do Treino</Label>
                      <Input value={newWorkout.name} onChange={(e) => setNewWorkout({...newWorkout, name: e.target.value})} placeholder="Ex: Treino de Peito" className="bg-[#121212] border-[#27272A] text-white mt-1" />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <Label className="text-xs uppercase tracking-wider">Duração (min)</Label>
                        <Input type="number" value={newWorkout.duration_minutes} onChange={(e) => setNewWorkout({...newWorkout, duration_minutes: parseInt(e.target.value) || 0})} className="bg-[#121212] border-[#27272A] text-white mt-1" />
                      </div>
                      <div>
                        <Label className="text-xs uppercase tracking-wider">Data</Label>
                        <Input type="date" value={newWorkout.date} onChange={(e) => setNewWorkout({...newWorkout, date: e.target.value})} className="bg-[#121212] border-[#27272A] text-white mt-1" />
                      </div>
                    </div>
                    
                    {newWorkout.exercises_completed.length > 0 && (
                      <div className="border-t border-[#27272A] pt-4">
                        <Label className="text-xs uppercase tracking-wider mb-3 block">Marque os exercícios realizados</Label>
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                          {newWorkout.exercises_completed.map((ex, idx) => (
                            <div 
                              key={idx} 
                              onClick={() => toggleExerciseInNewWorkout(idx)}
                              className={`flex items-center gap-3 p-3 rounded cursor-pointer transition-colors ${ex.completed ? 'bg-[#1a2f1a] border border-green-900' : 'bg-[#121212] border border-[#27272A] hover:border-[#3f3f46]'}`}
                            >
                              <Checkbox 
                                checked={ex.completed} 
                                onCheckedChange={() => toggleExerciseInNewWorkout(idx)}
                                className="border-[#52525B] data-[state=checked]:bg-[#00F0FF] data-[state=checked]:border-[#00F0FF]"
                              />
                              <span className={`font-mono text-sm ${ex.completed ? 'text-green-400' : 'text-white'}`}>
                                {ex.name} - {ex.sets}x{ex.reps} {ex.weight && `@ ${ex.weight}`}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    <div>
                      <Label className="text-xs uppercase tracking-wider">Observações</Label>
                      <Textarea value={newWorkout.notes} onChange={(e) => setNewWorkout({...newWorkout, notes: e.target.value})} placeholder="Como foi o treino?" className="bg-[#121212] border-[#27272A] text-white mt-1" />
                    </div>
                    <Button onClick={handleLogWorkout} className="w-full bg-[#00F0FF] hover:bg-[#00D4E5] text-black">Registrar Treino</Button>
                  </div>
                </DialogContent>
              </Dialog>
              
              <Dialog open={openPlan} onOpenChange={setOpenPlan}>
                <DialogTrigger asChild>
                  <Button data-testid="create-plan-btn" variant="outline" className="border-[#27272A]">
                    <FileText className="w-4 h-4 mr-2" /> Nova Ficha
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-lg max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="font-heading text-xl">CRIAR FICHA DE TREINO</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 mt-4">
                    <div>
                      <Label className="text-xs uppercase tracking-wider">Nome da Ficha</Label>
                      <Input value={newPlan.name} onChange={(e) => setNewPlan({...newPlan, name: e.target.value})} placeholder="Ex: Treino A - Peito e Tríceps" className="bg-[#121212] border-[#27272A] text-white mt-1" />
                    </div>
                    <div>
                      <Label className="text-xs uppercase tracking-wider">Duração do Plano</Label>
                      <Select value={newPlan.plan_duration || "dia"} onValueChange={(v) => setNewPlan({...newPlan, plan_duration: v})}>
                        <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                          <SelectItem value="dia">📅 Dia (treino único)</SelectItem>
                          <SelectItem value="semana">📆 Semana (seg-sex)</SelectItem>
                          <SelectItem value="mes">🗓️ Mês (4 semanas)</SelectItem>
                          <SelectItem value="ciclo">🔄 Ciclo (periodizado)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs uppercase tracking-wider">Descrição</Label>
                      <Textarea value={newPlan.description} onChange={(e) => setNewPlan({...newPlan, description: e.target.value})} className="bg-[#121212] border-[#27272A] text-white mt-1" />
                    </div>
                    <div className="border-t border-[#27272A] pt-4">
                      <Label className="text-xs uppercase tracking-wider mb-2 block">Adicionar Exercício</Label>
                      <div className="space-y-2">
                        <Input value={newExercise.name} onChange={(e) => setNewExercise({...newExercise, name: e.target.value})} placeholder="Nome do exercício" className="bg-[#121212] border-[#27272A] text-white" />
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <Label className="text-xs text-[#A1A1AA]">Séries</Label>
                            <Input type="number" value={newExercise.sets} onChange={(e) => setNewExercise({...newExercise, sets: parseInt(e.target.value) || 0})} className="bg-[#121212] border-[#27272A] text-white" />
                          </div>
                          <div>
                            <Label className="text-xs text-[#A1A1AA]">Reps</Label>
                            <Input type="number" value={newExercise.reps} onChange={(e) => setNewExercise({...newExercise, reps: parseInt(e.target.value) || 0})} className="bg-[#121212] border-[#27272A] text-white" />
                          </div>
                          <div>
                            <Label className="text-xs text-[#A1A1AA]">Carga</Label>
                            <Input value={newExercise.weight} onChange={(e) => setNewExercise({...newExercise, weight: e.target.value})} placeholder="Ex: 20kg" className="bg-[#121212] border-[#27272A] text-white" />
                          </div>
                        </div>
                        <Button onClick={addExerciseToPlan} variant="outline" className="w-full border-[#27272A]">
                          <Plus className="w-4 h-4 mr-2" /> Adicionar Exercício
                        </Button>
                      </div>
                    </div>
                    {newPlan.exercises.length > 0 && (
                      <div className="space-y-2">
                        <Label className="text-xs uppercase tracking-wider">Exercícios na Ficha</Label>
                        {newPlan.exercises.map((ex, idx) => (
                          <div key={idx} className="bg-[#121212] p-3 rounded flex items-center justify-between">
                            <span className="text-sm font-mono">
                              {ex.name} - {ex.sets}x{ex.reps} {ex.weight && `@ ${ex.weight}`}
                            </span>
                            <Button variant="ghost" size="sm" onClick={() => removeExerciseFromPlan(idx)} className="text-red-500 h-8 w-8 p-0">
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                    <Button onClick={handleCreatePlan} className="w-full bg-[#00F0FF] hover:bg-[#00D4E5] text-black">Criar Ficha</Button>
                  </div>
                </DialogContent>
              </Dialog>

              {/* Gerar com IA Button */}
              <Dialog open={openAiGenerate} onOpenChange={setOpenAiGenerate}>
                <DialogTrigger asChild>
                  <Button data-testid="open-ai-generate-btn" className="bg-gradient-to-r from-[#A855F7] to-[#00F0FF] hover:opacity-90 text-white">
                    <Sparkles className="w-4 h-4 mr-2" /> Gerar com IA
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-2xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="font-heading text-xl flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-[#A855F7]" /> GERAR TREINO COM IA
                    </DialogTitle>
                    <DialogDescription className="sr-only">Escolha o modo de geração de treino com IA</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 mt-4">
                    <div className="rounded-xl border border-blue-400/30 bg-blue-500/5 p-4" role="status"><p className="font-medium">O que será gerado</p><p className="text-sm text-slate-300 mt-2">{(() => {
                      const split = aiGenForm.workout_type === 'musculacao' && aiGenMode === 'tipo_treino';
                      const weeks = split ? aiGenForm.cycle_weeks : ({ dia: 1, semana: 1, mes: 4, ciclo: 10 }[aiGenForm.duration] || 1);
                      const days = split ? aiGenForm.training_days_per_week : aiGenForm.duration === 'dia' ? 1 : aiGenForm.workout_type === 'corrida' ? aiGenForm.weekly_frequency : 5;
                      return `${weeks} semana(s) · ${days} dia(s) de treino por semana · ${weeks * days} sessões · ${7 - days} dia(s) livres por semana`;
                    })()}</p><p className="text-xs text-slate-400 mt-2">A duração de cada sessão depende dos exercícios e descansos. Confira a ficha gerada antes de iniciar.</p></div>
                    {/* Workout Type Selector */}
                    <div className="flex gap-2 p-1 bg-[#121212] rounded-lg border border-[#27272A]">
                      <button
                        onClick={() => setAiGenForm(prev => ({...prev, workout_type: "musculacao"}))}
                        className={`flex-1 py-2.5 px-4 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                          aiGenForm.workout_type === "musculacao" 
                            ? 'bg-gradient-to-r from-[#A855F7] to-[#7C3AED] text-white shadow-lg' 
                            : 'text-[#A1A1AA] hover:text-white hover:bg-[#1A1A1A]'
                        }`}
                      >
                        <Dumbbell className="w-4 h-4" /> Musculação
                      </button>
                      <button
                        onClick={() => setAiGenForm(prev => ({...prev, workout_type: "corrida"}))}
                        className={`flex-1 py-2.5 px-4 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                          aiGenForm.workout_type === "corrida" 
                            ? 'bg-gradient-to-r from-[#00F0FF] to-[#0EA5E9] text-white shadow-lg' 
                            : 'text-[#A1A1AA] hover:text-white hover:bg-[#1A1A1A]'
                        }`}
                      >
                        <span className="text-lg">🏃</span> Corrida
                      </button>
                      <button
                        onClick={() => setAiGenForm(prev => ({...prev, workout_type: "hibrido"}))}
                        className={`flex-1 py-2.5 px-4 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                          aiGenForm.workout_type === "hibrido" 
                            ? 'bg-gradient-to-r from-[#10B981] to-[#059669] text-white shadow-lg' 
                            : 'text-[#A1A1AA] hover:text-white hover:bg-[#1A1A1A]'
                        }`}
                      >
                        <Dumbbell className="w-4 h-4" /><span className="text-lg">🏃</span> Híbrido
                      </button>
                      <button
                        onClick={() => { setAiGenForm(prev => ({...prev, workout_type: "calistenia"})); setAiGenMode("periodo"); }}
                        className={`flex-1 py-2.5 px-4 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                          aiGenForm.workout_type === "calistenia" 
                            ? 'bg-gradient-to-r from-[#F97316] to-[#EA580C] text-white shadow-lg' 
                            : 'text-[#A1A1AA] hover:text-white hover:bg-[#1A1A1A]'
                        }`}
                      >
                        <Zap className="w-4 h-4" /> Calistenia
                      </button>
                    </div>

                    {/* ============ RUNNING MODE ============ */}
                    {aiGenForm.workout_type === "corrida" ? (
                      <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs uppercase tracking-wider">Objetivo da Corrida</Label>
                            <Select value={aiGenForm.running_goal} onValueChange={(v) => setAiGenForm({...aiGenForm, running_goal: v})}>
                              <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                                <SelectItem value="5km">🏃 5km</SelectItem>
                                <SelectItem value="10km">🏃 10km</SelectItem>
                                <SelectItem value="meia_maratona">🏅 Meia Maratona (21km)</SelectItem>
                                <SelectItem value="maratona">🏅 Maratona (42km)</SelectItem>
                                <SelectItem value="condicionamento">❤️ Condicionamento</SelectItem>
                                <SelectItem value="emagrecimento">🔥 Emagrecimento</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="text-xs uppercase tracking-wider">Nível</Label>
                            <Select value={aiGenForm.level} onValueChange={(v) => setAiGenForm({...aiGenForm, level: v})}>
                              <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                                <SelectItem value="iniciante">🟢 Iniciante</SelectItem>
                                <SelectItem value="intermediario">🟡 Intermediário</SelectItem>
                                <SelectItem value="avancado">🔴 Avançado</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs uppercase tracking-wider">Dias por Semana</Label>
                            <Select value={String(aiGenForm.weekly_frequency)} onValueChange={(v) => setAiGenForm({...aiGenForm, weekly_frequency: Number(v)})}>
                              <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                                {[2,3,4,5,6,7].map(n => <SelectItem key={n} value={String(n)}>{n} dias</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="text-xs uppercase tracking-wider">Terreno</Label>
                            <Select value={aiGenForm.preferred_terrain} onValueChange={(v) => setAiGenForm({...aiGenForm, preferred_terrain: v})}>
                              <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                                <SelectItem value="asfalto">🛣️ Asfalto</SelectItem>
                                <SelectItem value="esteira">🏃 Esteira</SelectItem>
                                <SelectItem value="trilha">⛰️ Trilha</SelectItem>
                                <SelectItem value="misto">🔄 Misto</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>

                        <div>
                          <Label className="text-xs uppercase tracking-wider">Duração do Plano</Label>
                          <Select value={aiGenForm.duration} onValueChange={(v) => setAiGenForm({...aiGenForm, duration: v})}>
                            <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                              <SelectItem value="dia">📅 Um dia</SelectItem>
                              <SelectItem value="semana">📅 Uma semana</SelectItem>
                              <SelectItem value="mes">📅 Um mês (4 semanas)</SelectItem>
                              <SelectItem value="ciclo">📅 Ciclo completo (8-12 semanas)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div>
                          <Label className="text-xs uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                            <Heart className="w-3.5 h-3.5 text-red-400" /> Condição de Saúde / Lesões
                            <span className="text-[#52525B] font-normal normal-case">(opcional)</span>
                          </Label>
                          <textarea
                            value={aiGenForm.health_condition}
                            onChange={(e) => setAiGenForm({...aiGenForm, health_condition: e.target.value})}
                            placeholder="Ex: Dor no joelho ao correr, lesão no tornozelo..."
                            className="w-full bg-[#121212] border border-[#27272A] rounded-lg p-3 text-sm text-white placeholder:text-[#52525B] focus:border-[#00F0FF] focus:ring-1 focus:ring-[#00F0FF] outline-none resize-none transition-colors"
                            rows={2}
                          />
                        </div>

                        <Button
                          onClick={handleGenerateWithAI}
                          disabled={generatingPlan}
                          className="w-full bg-gradient-to-r from-[#00F0FF] to-[#0EA5E9] hover:opacity-90 text-black font-bold"
                        >
                          {generatingPlan ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Gerando...</> : <><Sparkles className="w-4 h-4 mr-2" /> Gerar Treino de Corrida</>}
                        </Button>
                      </div>
                  ) : aiGenForm.workout_type === "calistenia" ? (
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label className="text-xs uppercase tracking-wider">Foco do Treino</Label>
                          <Select value={aiGenForm.calisthenics_focus} onValueChange={(v) => setAiGenForm({...aiGenForm, calisthenics_focus: v})}>
                            <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                              <SelectItem value="full_body">🔄 Full Body</SelectItem>
                              <SelectItem value="forca_upper">💪 Força Upper Body</SelectItem>
                              <SelectItem value="forca_lower">🦵 Força Lower Body</SelectItem>
                              <SelectItem value="habilidades">🤸 Habilidades (handstand, muscle-up, etc)</SelectItem>
                              <SelectItem value="condicionamento">❤️ Condicionamento</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs uppercase tracking-wider">Nível</Label>
                          <Select value={aiGenForm.level} onValueChange={(v) => setAiGenForm({...aiGenForm, level: v})}>
                            <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                              <SelectItem value="iniciante">🟢 Iniciante</SelectItem>
                              <SelectItem value="intermediario">🟡 Intermediário</SelectItem>
                              <SelectItem value="avancado">🔴 Avançado</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label className="text-xs uppercase tracking-wider">Equipamento Disponível</Label>
                          <Select value={aiGenForm.calisthenics_equipment} onValueChange={(v) => setAiGenForm({...aiGenForm, calisthenics_equipment: v})}>
                            <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                              <SelectItem value="nenhum">🙌 Nenhum (só peso corporal)</SelectItem>
                              <SelectItem value="solo">🧘 Solo (chão + colchonete)</SelectItem>
                              <SelectItem value="barra">💪 Barra Fixa</SelectItem>
                              <SelectItem value="paralelas">💪 Barras Paralelas</SelectItem>
                              <SelectItem value="argolas">⭕ Argolas</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs uppercase tracking-wider">Duração do Plano</Label>
                          <Select value={aiGenForm.duration} onValueChange={(v) => setAiGenForm({...aiGenForm, duration: v})}>
                            <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                              <SelectItem value="dia">📅 Um dia</SelectItem>
                              <SelectItem value="semana">📅 Uma semana</SelectItem>
                              <SelectItem value="mes">📅 Um mês (4 semanas)</SelectItem>
                              <SelectItem value="ciclo">📅 Ciclo completo (8-12 semanas)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div>
                        <Label className="text-xs uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                          <Heart className="w-3.5 h-3.5 text-red-400" /> Condição de Saúde / Lesões
                          <span className="text-[#52525B] font-normal normal-case">(opcional)</span>
                        </Label>
                        <textarea
                          value={aiGenForm.health_condition}
                          onChange={(e) => setAiGenForm({...aiGenForm, health_condition: e.target.value})}
                          placeholder="Ex: Dor no ombro ao fazer barra, lesão no punho..."
                          className="w-full bg-[#121212] border border-[#27272A] rounded-lg p-3 text-sm text-white placeholder:text-[#52525B] focus:border-[#F97316] focus:ring-1 focus:ring-[#F97316] outline-none resize-none transition-colors"
                          rows={2}
                        />
                      </div>

                      <Button
                        onClick={handleGenerateWithAI}
                        disabled={generatingPlan}
                        className="w-full bg-gradient-to-r from-[#F97316] to-[#EA580C] hover:opacity-90 text-white font-bold"
                      >
                        {generatingPlan ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Gerando...</> : <><Zap className="w-4 h-4 mr-2" /> Gerar Treino de Calistenia</>}
                      </Button>
                    </div>
                    ) : (
                    <>
                    {/* Mode Selector Tabs */}
                    <div className="flex gap-2 p-1 bg-[#121212] rounded-lg border border-[#27272A]">
                      <button
                        data-testid="tab-tipo-treino"
                        onClick={() => { setAiGenMode("tipo_treino"); setAiGenForm(prev => ({...prev, generation_mode: "tipo_treino"})); }}
                        className={`flex-1 py-2.5 px-4 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                          aiGenMode === "tipo_treino" 
                            ? 'bg-gradient-to-r from-[#A855F7] to-[#7C3AED] text-white shadow-lg' 
                            : 'text-[#A1A1AA] hover:text-white hover:bg-[#1A1A1A]'
                        }`}
                      >
                        <Dumbbell className="w-4 h-4" /> Por Tipo de Treino
                      </button>
                      <button
                        data-testid="tab-periodo"
                        onClick={() => { setAiGenMode("periodo"); setAiGenForm(prev => ({...prev, generation_mode: "periodo"})); }}
                        className={`flex-1 py-2.5 px-4 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                          aiGenMode === "periodo" 
                            ? 'bg-gradient-to-r from-[#00F0FF] to-[#0EA5E9] text-white shadow-lg' 
                            : 'text-[#A1A1AA] hover:text-white hover:bg-[#1A1A1A]'
                        }`}
                      >
                        <Calendar className="w-4 h-4" /> Por Período
                      </button>
                    </div>

                    {/* Common fields: Objective + Level */}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label className="text-xs uppercase tracking-wider">Objetivo</Label>
                        <Select value={aiGenForm.objective} onValueChange={(v) => setAiGenForm({...aiGenForm, objective: v})}>
                          <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                            <SelectItem value="hipertrofia">💪 Hipertrofia</SelectItem>
                            <SelectItem value="emagrecimento">🔥 Emagrecimento</SelectItem>
                            <SelectItem value="condicionamento">❤️ Condicionamento</SelectItem>
                            <SelectItem value="forca">🏋️ Força máxima</SelectItem>
                            <SelectItem value="flexibilidade">🧘 Flexibilidade</SelectItem>
                            <SelectItem value="resistencia">🏃 Resistência</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label className="text-xs uppercase tracking-wider">Nível</Label>
                        <Select value={aiGenForm.level} onValueChange={(v) => setAiGenForm({...aiGenForm, level: v})}>
                          <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                            <SelectItem value="iniciante">🟢 Iniciante (0-6 meses)</SelectItem>
                            <SelectItem value="intermediario">🟡 Intermediário (6-24m)</SelectItem>
                            <SelectItem value="avancado">🔴 Avançado (2+ anos)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    {/* Health Condition Field */}
                    <div>
                      <Label className="text-xs uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                        <Heart className="w-3.5 h-3.5 text-red-400" /> Condição de Saúde / Lesões
                        <span className="text-[#52525B] font-normal normal-case">(opcional)</span>
                      </Label>
                      <textarea
                        data-testid="health-condition-input"
                        value={aiGenForm.health_condition}
                        onChange={(e) => setAiGenForm({...aiGenForm, health_condition: e.target.value})}
                        placeholder="Ex: Luxação anterior no ombro esquerdo, preciso de fortalecimento. Dor no joelho direito..."
                        className="w-full bg-[#121212] border border-[#27272A] rounded-lg p-3 text-sm text-white placeholder:text-[#52525B] focus:border-[#A855F7] focus:ring-1 focus:ring-[#A855F7] outline-none resize-none transition-colors"
                        rows={2}
                      />
                      {aiGenForm.health_condition && (
                        <p className="text-[10px] text-[#A855F7] mt-1 flex items-center gap-1">
                          <ShieldCheck className="w-3 h-3" /> A IA adaptará os exercícios à sua condição
                        </p>
                      )}
                    </div>

                    {/* ============ MODE: TIPO DE TREINO (SPLIT) ============ */}
                    {aiGenMode === "tipo_treino" && (
                      <div className="space-y-4">
                        {/* Split Type Selector */}
                        <div>
                          <Label className="text-xs uppercase tracking-wider mb-2 block">Tipo de Divisão</Label>
                          <div className="flex gap-2">
                            {SPLIT_OPTIONS.map(opt => (
                              <button
                                key={opt.value}
                                onClick={() => handleSplitTypeChange(opt.value)}
                                className={`flex-1 py-2.5 px-3 rounded-lg text-sm font-bold transition-all border ${
                                  aiGenForm.split_type === opt.value
                                    ? 'bg-[#A855F7]/20 border-[#A855F7] text-[#A855F7] shadow-[0_0_10px_rgba(168,85,247,0.15)]'
                                    : 'bg-[#121212] border-[#27272A] text-[#A1A1AA] hover:border-[#A855F7]/50'
                                }`}
                              >
                                {opt.value}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Split Configuration - Muscle groups per division */}
                        <div>
                          <Label className="text-xs uppercase tracking-wider mb-2 block">Configurar Divisões</Label>
                          <div className="space-y-3">
                            {aiGenForm.split_config.map((split, splitIdx) => (
                              <div key={split.label} className="bg-[#121212] border border-[#27272A] rounded-lg p-3">
                                <div className="flex items-center gap-2 mb-2">
                                  <span className="w-8 h-8 flex items-center justify-center rounded-lg bg-[#A855F7]/20 text-[#A855F7] font-bold text-sm">
                                    {split.label}
                                  </span>
                                  <span className="text-sm text-[#A1A1AA] flex-1 truncate">
                                    {split.name || "Selecione os grupos musculares"}
                                  </span>
                                </div>
                                <div className="flex flex-wrap gap-1.5">
                                  {ALL_MUSCLE_GROUPS.map(mg => (
                                    <button
                                      key={mg.value}
                                      onClick={() => toggleSplitMuscleGroup(splitIdx, mg.value)}
                                      className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-all ${
                                        split.muscle_groups.includes(mg.value)
                                          ? 'bg-[#A855F7] text-white'
                                          : 'bg-[#0A0A0A] border border-[#27272A] text-[#71717A] hover:border-[#A855F7]/50 hover:text-[#A1A1AA]'
                                      }`}
                                    >
                                      {mg.emoji} {mg.label}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Training days + Cycle weeks */}
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs uppercase tracking-wider">Dias por semana</Label>
                            <Select 
                              value={String(aiGenForm.training_days_per_week)} 
                              onValueChange={(v) => setAiGenForm({...aiGenForm, training_days_per_week: parseInt(v)})}
                            >
                              <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                                {[2,3,4,5,6,7].map(n => (
                                  <SelectItem key={n} value={String(n)}>{n} dias</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="text-xs uppercase tracking-wider">Duração do ciclo</Label>
                            <Select 
                              value={String(aiGenForm.cycle_weeks)} 
                              onValueChange={(v) => setAiGenForm({...aiGenForm, cycle_weeks: parseInt(v)})}
                            >
                              <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                                {[1,2,3,4,6,8,12].map(n => (
                                  <SelectItem key={n} value={String(n)}>{n} semana{n > 1 ? 's' : ''}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>

                        {/* Cardio Toggle */}
                        <div className="bg-[#121212] border border-[#27272A] rounded-lg p-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <Activity className="w-4 h-4 text-[#00F0FF]" />
                              <span className="text-sm font-medium">Intercalar com Cardio</span>
                            </div>
                            <Switch
                              checked={aiGenForm.include_cardio}
                              onCheckedChange={(checked) => setAiGenForm({...aiGenForm, include_cardio: checked})}
                            />
                          </div>
                          {aiGenForm.include_cardio && (
                            <div className="mt-3 pt-3 border-t border-[#27272A] space-y-3">
                              {/* Cardio Mode */}
                              <div>
                                <Label className="text-xs uppercase tracking-wider mb-2 block">Modo de Cardio</Label>
                                <div className="grid grid-cols-1 gap-2">
                                  {[
                                    { value: "hibrido", label: "Híbrido", desc: "Musculação + Cardio no mesmo dia (cardio ao final do treino)", icon: "💪" },
                                    { value: "hibrido_alternado", label: "Híbrido Alternado", desc: "1 dia musculação, 1 dia cardio (variando intensidade) + dia de descanso", icon: "🔄" }
                                  ].map(mode => (
                                    <button
                                      key={mode.value}
                                      onClick={() => setAiGenForm({...aiGenForm, cardio_mode: mode.value})}
                                      className={`text-left p-2.5 rounded-lg border transition-all ${
                                        aiGenForm.cardio_mode === mode.value
                                          ? 'bg-[#00F0FF]/10 border-[#00F0FF] text-white'
                                          : 'bg-[#0A0A0A] border-[#27272A] text-[#71717A] hover:border-[#00F0FF]/50'
                                      }`}
                                    >
                                      <span className="text-sm font-medium">{mode.icon} {mode.label}</span>
                                      <p className="text-[11px] text-[#A1A1AA] mt-0.5">{mode.desc}</p>
                                    </button>
                                  ))}
                                </div>
                              </div>
                              
                              {/* Cardio Type */}
                              <div>
                                <Label className="text-xs uppercase tracking-wider mb-2 block">Tipo de Cardio</Label>
                                <div className="flex flex-wrap gap-2">
                                  {CARDIO_TYPES.map(ct => (
                                    <button
                                      key={ct.value}
                                      onClick={() => setAiGenForm({...aiGenForm, cardio_type: ct.value})}
                                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                                        aiGenForm.cardio_type === ct.value
                                          ? 'bg-[#00F0FF]/20 text-[#00F0FF] border border-[#00F0FF]'
                                          : 'bg-[#0A0A0A] border border-[#27272A] text-[#71717A] hover:border-[#00F0FF]/50'
                                      }`}
                                    >
                                      {ct.emoji} {ct.label}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Summary box */}
                        <div className="bg-[#121212] border border-[#A855F7]/30 rounded-lg p-4">
                          <div className="flex items-center gap-2 mb-2">
                            <Zap className="w-4 h-4 text-[#A855F7]" />
                            <span className="text-sm font-medium">Resumo do plano:</span>
                          </div>
                          <ul className="text-xs text-[#A1A1AA] space-y-1">
                            <li>• Divisão <span className="text-white font-medium">{aiGenForm.split_type}</span> com <span className="text-white font-medium">{aiGenForm.split_config.length}</span> treinos diferentes</li>
                            <li>• <span className="text-white font-medium">{aiGenForm.training_days_per_week}</span> dias por semana durante <span className="text-white font-medium">{aiGenForm.cycle_weeks}</span> semana{aiGenForm.cycle_weeks > 1 ? 's' : ''}</li>
                            <li>• Total: <span className="text-white font-medium">{aiGenForm.training_days_per_week * aiGenForm.cycle_weeks}</span> sessões de treino</li>
                            {aiGenForm.include_cardio && <li>• Cardio: <span className="text-[#00F0FF] font-medium">{
                              aiGenForm.cardio_mode === "hibrido" ? "Híbrido (mesmo dia)" : "Híbrido Alternado (dias alternados)"
                            }</span> ({CARDIO_TYPES.find(c => c.value === aiGenForm.cardio_type)?.label || aiGenForm.cardio_type})</li>}
                            <li>• Tutorial descritivo por exercício</li>
                            <li>• Progressão de carga entre semanas</li>
                          </ul>
                        </div>
                      </div>
                    )}

                    {/* ============ MODE: POR PERÍODO (existing) ============ */}
                    {aiGenMode === "periodo" && (
                      <div className="space-y-4">
                        <div>
                          <Label className="text-xs uppercase tracking-wider">Duração do Plano</Label>
                          <Select value={aiGenForm.duration} onValueChange={(v) => setAiGenForm({...aiGenForm, duration: v})}>
                            <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                              <SelectItem value="dia">📅 Dia (treino único)</SelectItem>
                              <SelectItem value="semana">📆 Semana (seg-sex)</SelectItem>
                              <SelectItem value="mes">🗓️ Mês (4 semanas)</SelectItem>
                              <SelectItem value="ciclo">🔄 Ciclo (8-12 semanas)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div>
                          <Label className="text-xs uppercase tracking-wider mb-2 block">Grupos Musculares (opcional)</Label>
                          <div className="flex flex-wrap gap-2">
                            {ALL_MUSCLE_GROUPS.map(mg => (
                              <button
                                key={mg.value}
                                onClick={() => toggleMuscleGroup(mg.value)}
                                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                                  aiGenForm.muscle_groups.includes(mg.value)
                                    ? 'bg-[#A855F7] text-white'
                                    : 'bg-[#121212] border border-[#27272A] text-[#A1A1AA] hover:border-[#A855F7]'
                                }`}
                              >
                                {mg.emoji} {mg.label}
                              </button>
                            ))}
                          </div>
                          <p className="text-xs text-[#52525B] mt-2">Deixe vazio para um treino completo</p>
                        </div>

                        <div className="bg-[#121212] border border-[#27272A] rounded-lg p-4">
                          <div className="flex items-center gap-2 mb-2">
                            <Zap className="w-4 h-4 text-[#00F0FF]" />
                            <span className="text-sm font-medium">O que a IA vai gerar:</span>
                          </div>
                          <ul className="text-xs text-[#A1A1AA] space-y-1">
                            <li>• Exercícios personalizados para seu nível e objetivo</li>
                            <li>• Tutorial detalhado de execução de cada exercício</li>
                            <li>• Séries, repetições e tempo de descanso adequados</li>
                            {aiGenForm.duration !== "dia" && <li>• Organização por dias com alternância de grupos</li>}
                          </ul>
                        </div>
                      </div>
                    )}

                    <Button 
                      data-testid="generate-ai-workout-btn"
                      onClick={handleGenerateWithAI} 
                      disabled={generatingPlan}
                      className="w-full bg-gradient-to-r from-[#A855F7] to-[#00F0FF] hover:opacity-90 text-white h-11"
                    >
                      {generatingPlan ? (
                        <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Gerando treino com IA...</>
                      ) : (
                        <><Sparkles className="w-4 h-4 mr-2" /> Gerar Treino</>
                      )}
                    </Button>
                    </>)}
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          {/* Dialog de Edição de Ficha */}
          <Dialog open={openEditPlan} onOpenChange={setOpenEditPlan}>
            <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-lg max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="font-heading text-xl">EDITAR FICHA DE TREINO</DialogTitle>
              </DialogHeader>
              {editingPlan && (
                <div className="space-y-4 mt-4">
                  <div>
                    <Label className="text-xs uppercase tracking-wider">Nome da Ficha</Label>
                    <Input 
                      value={editingPlan.name} 
                      onChange={(e) => setEditingPlan({...editingPlan, name: e.target.value})} 
                      className="bg-[#121212] border-[#27272A] text-white mt-1" 
                    />
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wider">Descrição</Label>
                    <Textarea 
                      value={editingPlan.description || ""} 
                      onChange={(e) => setEditingPlan({...editingPlan, description: e.target.value})} 
                      className="bg-[#121212] border-[#27272A] text-white mt-1" 
                    />
                  </div>
                  
                  {editingPlan.exercises.length > 0 && (
                    <div className="border-t border-[#27272A] pt-4">
                      <Label className="text-xs uppercase tracking-wider mb-3 block">Exercícios da Ficha</Label>
                      <div className="space-y-3">
                        {editingPlan.exercises.map((ex, idx) => (
                          <div key={idx} className="bg-[#121212] p-3 rounded border border-[#27272A]">
                            <div className="flex items-center justify-between mb-2">
                              <Input 
                                value={ex.name} 
                                onChange={(e) => updateExerciseInEditPlan(idx, 'name', e.target.value)}
                                className="bg-[#0A0A0A] border-[#27272A] text-white flex-1 mr-2"
                                placeholder="Nome do exercício"
                              />
                              <Button variant="ghost" size="sm" onClick={() => removeExerciseFromEditPlan(idx)} className="text-red-500 h-8 w-8 p-0">
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                            <div className="grid grid-cols-3 gap-2">
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Séries</Label>
                                <Input 
                                  type="number" 
                                  value={ex.sets} 
                                  onChange={(e) => updateExerciseInEditPlan(idx, 'sets', e.target.value)}
                                  className="bg-[#0A0A0A] border-[#27272A] text-white"
                                />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Reps</Label>
                                <Input 
                                  type="number" 
                                  value={ex.reps} 
                                  onChange={(e) => updateExerciseInEditPlan(idx, 'reps', e.target.value)}
                                  className="bg-[#0A0A0A] border-[#27272A] text-white"
                                />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Carga</Label>
                                <Input 
                                  value={ex.weight || ""} 
                                  onChange={(e) => updateExerciseInEditPlan(idx, 'weight', e.target.value)}
                                  placeholder="Ex: 20kg"
                                  className="bg-[#0A0A0A] border-[#27272A] text-white"
                                />
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  <div className="border-t border-[#27272A] pt-4">
                    <Label className="text-xs uppercase tracking-wider mb-2 block">Adicionar Novo Exercício</Label>
                    <div className="space-y-2">
                      <Input 
                        value={editExercise.name} 
                        onChange={(e) => setEditExercise({...editExercise, name: e.target.value})} 
                        placeholder="Nome do exercício" 
                        className="bg-[#121212] border-[#27272A] text-white" 
                      />
                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <Label className="text-xs text-[#A1A1AA]">Séries</Label>
                          <Input 
                            type="number" 
                            value={editExercise.sets} 
                            onChange={(e) => setEditExercise({...editExercise, sets: parseInt(e.target.value) || 0})} 
                            className="bg-[#121212] border-[#27272A] text-white" 
                          />
                        </div>
                        <div>
                          <Label className="text-xs text-[#A1A1AA]">Reps</Label>
                          <Input 
                            type="number" 
                            value={editExercise.reps} 
                            onChange={(e) => setEditExercise({...editExercise, reps: parseInt(e.target.value) || 0})} 
                            className="bg-[#121212] border-[#27272A] text-white" 
                          />
                        </div>
                        <div>
                          <Label className="text-xs text-[#A1A1AA]">Carga</Label>
                          <Input 
                            value={editExercise.weight} 
                            onChange={(e) => setEditExercise({...editExercise, weight: e.target.value})} 
                            placeholder="Ex: 20kg"
                            className="bg-[#121212] border-[#27272A] text-white" 
                          />
                        </div>
                      </div>
                      <Button onClick={addExerciseToEditPlan} variant="outline" className="w-full border-[#27272A]">
                        <Plus className="w-4 h-4 mr-2" /> Adicionar Exercício
                      </Button>
                    </div>
                  </div>
                  
                  <div className="flex gap-2">
                    <Button onClick={() => setOpenEditPlan(false)} variant="outline" className="flex-1 border-[#27272A]">
                      Cancelar
                    </Button>
                    <Button onClick={handleUpdatePlan} className="flex-1 bg-[#00F0FF] hover:bg-[#00D4E5] text-black">
                      Salvar Alterações
                    </Button>
                  </div>
                </div>
              )}
            </DialogContent>
          </Dialog>

          {/* Dialog de Conclusão de Treino */}
          <Dialog open={openCompleteWorkout} onOpenChange={setOpenCompleteWorkout}>
            <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-md">
              <DialogHeader>
                <DialogTitle className="font-heading text-xl">CONCLUIR TREINO</DialogTitle>
              </DialogHeader>
              {completingPlan && (
                <div className="space-y-4 mt-4">
                  <p className="text-[#A1A1AA]">Confirme os dados do treino <span className="text-white font-semibold">{completingPlan.name}</span></p>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-xs uppercase tracking-wider">Duração (min)</Label>
                      <Input 
                        type="number" 
                        value={completeWorkoutData.duration_minutes} 
                        onChange={(e) => setCompleteWorkoutData({...completeWorkoutData, duration_minutes: parseInt(e.target.value) || 0})}
                        className="bg-[#121212] border-[#27272A] text-white mt-1" 
                      />
                    </div>
                    <div>
                      <Label className="text-xs uppercase tracking-wider">Calorias (aprox)</Label>
                      <Input 
                        type="number" 
                        value={completeWorkoutData.calories || ""} 
                        onChange={(e) => setCompleteWorkoutData({...completeWorkoutData, calories: parseInt(e.target.value) || null})}
                        placeholder="Estimativa"
                        className="bg-[#121212] border-[#27272A] text-white mt-1" 
                      />
                    </div>
                  </div>
                  
                  <div>
                    <Label className="text-xs uppercase tracking-wider">Observações</Label>
                    <Textarea 
                      value={completeWorkoutData.notes} 
                      onChange={(e) => setCompleteWorkoutData({...completeWorkoutData, notes: e.target.value})}
                      placeholder="Como foi o treino?"
                      className="bg-[#121212] border-[#27272A] text-white mt-1" 
                    />
                  </div>
                  
                  <div className="flex gap-2">
                    <Button onClick={() => setOpenCompleteWorkout(false)} variant="outline" className="flex-1 border-[#27272A]">
                      Cancelar
                    </Button>
                    <Button onClick={handleCompleteWorkout} className="flex-1 bg-[#00F0FF] hover:bg-[#00D4E5] text-black">
                      <Check className="w-4 h-4 mr-2" /> Concluir Treino
                    </Button>
                  </div>
                </div>
              )}
            </DialogContent>
          </Dialog>

          {/* Stats Summary - Compact */}
          {stats && (
            <div className="sirius-workout-stats flex items-center gap-6 p-4 bg-[#0A0A0A] border border-[#27272A] rounded-lg mb-6">
              <div className="flex items-center gap-2">
                <Dumbbell className="w-5 h-5 text-[#00F0FF]" />
                <span className="text-xs text-[#A1A1AA] uppercase">Treinos</span>
                <span className="font-heading text-xl">{stats.total_workouts}</span>
              </div>
              <div className="h-6 w-px bg-[#27272A]" />
              <div className="flex items-center gap-2">
                <Timer className="w-5 h-5 text-[#F59E0B]" />
                <span className="text-xs text-[#A1A1AA] uppercase">Min</span>
                <span className="font-heading text-xl">{stats.total_duration_minutes}</span>
              </div>
              <div className="h-6 w-px bg-[#27272A]" />
              <div className="flex items-center gap-2">
                <Flame className="w-5 h-5 text-[#EF4444]" />
                <span className="text-xs text-[#A1A1AA] uppercase">Cal</span>
                <span className="font-heading text-xl">{stats.total_calories}</span>
              </div>
              <div className="h-6 w-px bg-[#27272A]" />
              <div className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-[#22C55E]" />
                <span className="text-xs text-[#A1A1AA] uppercase">XP</span>
                <span className="font-heading text-xl">{stats.total_xp_earned}</span>
              </div>
              {detailedStats && (
                <>
                  <div className="h-6 w-px bg-[#27272A]" />
                  <div className="flex items-center gap-2">
                    <Flame className="w-5 h-5 text-[#F59E0B]" />
                    <span className="text-xs text-[#A1A1AA] uppercase">Streak</span>
                    <span className="font-heading text-xl text-[#F59E0B]">{detailedStats.current_streak}</span>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Today's Schedule Banner */}
          {todaySchedule && (
            <div className="bg-gradient-to-r from-green-900/20 via-black/50 to-green-900/20 border border-green-800/50 rounded-lg p-4 mb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center">
                  <Dumbbell className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <p className="text-xs text-[#A1A1AA] uppercase tracking-wider">{todaySchedule.plan_name}</p>
                  <p className="text-sm font-medium text-white">{todaySchedule.day_label || "Treino do dia"}</p>
                  <p className="text-xs text-[#71717A]">{todaySchedule.exercise_count} exercícios · Semana {todaySchedule.week}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {todaySchedule.already_completed ? (
                  <Badge className="bg-green-500/20 text-green-400 border-green-500/30">Concluído</Badge>
                ) : (
                  <>
                    <span className="text-xs text-[#00F0FF] animate-pulse">● Pendente</span>
                    <Button size="sm" onClick={() => { const p = plans.find(pl => pl.plan_id === todaySchedule.plan_id); if (p) handleStartWorkout(p, todaySchedule.day_index || 0); else setActiveTab("plans"); }} className="bg-green-600 hover:bg-green-700 text-white text-xs h-8">
                      <Play className="w-3 h-3 mr-1" /> Iniciar
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}

          <section className="sirius-workout-flow mb-6 rounded-2xl border border-slate-700 bg-slate-900/50 p-4"><div className="flex flex-wrap items-center gap-3"><p className="text-sm text-slate-300 flex-1">{activeSession ? `Em andamento: ${activeSession.plan_name}` : 'Planeje seu treino, registre cada série e acompanhe sua evolução.'}</p><Button variant="outline" onClick={() => setActiveTab('plans')}>1. Meu plano</Button><Button disabled={!activeSession} onClick={() => setActiveTab('session')}>2. {activeSession ? 'Retomar treino' : 'Executar treino'}</Button><Button variant="outline" onClick={() => setActiveTab('evolution')}>3. Evolução</Button></div>{sessionSaving && <p role="status" className="text-sm text-blue-300 mt-3">Salvando seu progresso…</p>}</section>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="bg-[#0A0A0A] border border-[#27272A] mb-6 overflow-x-auto flex-nowrap w-full justify-start md:justify-center">
              <TabsTrigger value="log" className="data-[state=active]:bg-[#27272A]">
                <Activity className="w-4 h-4 mr-2" /> Hoje
              </TabsTrigger>
              <TabsTrigger value="plans" className="data-[state=active]:bg-[#27272A]">
                <FileText className="w-4 h-4 mr-2" /> Fichas
              </TabsTrigger>
              <TabsTrigger value="stats" className="data-[state=active]:bg-[#27272A]">
                <BarChart3 className="w-4 h-4 mr-2" /> Estatísticas
              </TabsTrigger>
              <TabsTrigger value="evolution" className="data-[state=active]:bg-[#27272A]">
                <Scale className="w-4 h-4 mr-2" /> Evolução
              </TabsTrigger>
              <TabsTrigger value="history" className="data-[state=active]:bg-[#27272A]">
                <Calendar className="w-4 h-4 mr-2" /> Histórico
              </TabsTrigger>
              <TabsTrigger value="saved_insights" className="data-[state=active]:bg-[#27272A]" onClick={fetchSavedInsights}>
                <BookOpen className="w-4 h-4 mr-2" /> Insights
              </TabsTrigger>
              {activeSession && (
                <TabsTrigger value="session" className="data-[state=active]:bg-[#27272A] text-green-400 animate-pulse">
                  <Zap className="w-4 h-4 mr-2" /> Sessão Ativa
                </TabsTrigger>
              )}
            </TabsList>

            <TabsContent value="log">
              <div className="grid gap-4">
                {workouts.filter(w => w.date === today).length === 0 ? (
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center">
                    <Dumbbell className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                    <p className="text-[#A1A1AA]">Nenhum treino registrado hoje</p>
                    <p className="text-sm text-[#52525B] mt-2">Selecione uma ficha na aba "Fichas" ou clique em "Registrar Treino"</p>
                  </Card>
                ) : (
                  workouts.filter(w => w.date === today).map(workout => (
                    <WorkoutCard key={workout.log_id} workout={workout} />
                  ))
                )}
              </div>
            </TabsContent>

            <TabsContent value="plans">
              <div className="flex gap-2 mb-4">
                <Button onClick={() => setShowImportDialog(true)} variant="outline" size="sm" className="border-purple-500/30 text-purple-400 hover:bg-purple-500/10">
                  <Upload className="w-3 h-3 mr-1" />Importar Ficha
                </Button>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                {plans.length === 0 ? (
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center md:col-span-2">
                    <FileText className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                    <p className="text-[#A1A1AA]">Nenhuma ficha de treino criada</p>
                    <p className="text-sm text-[#52525B] mt-2">Clique em "Nova Ficha" para criar uma</p>
                  </Card>
                ) : (
                  plans.map(plan => {
                    const isExpanded = expandedPlans[plan.plan_id];
                    const { weeks, weekNumbers, selectedWeek, selectedDayIndex, currentWeekDays } = getWorkoutCalendar(plan, selectedDays[plan.plan_id]);
                    const setSelectedDayIndex = index => setSelectedDays(previous => ({ ...previous, [plan.plan_id]: index }));
                    const status = dailyStatus[plan.plan_id] || {};
                    const { completed, total } = getDailyCompletedCount(plan.plan_id, plan.exercises.length);
                    const isCompleted = status.completed;
                    
                    return (
                      <Card key={plan.plan_id} className={`bg-[#0A0A0A] border-[#27272A] p-4 ${isCompleted ? 'border-green-900 bg-[#0a1a0a]' : ''} ${plan.generated_by_ai ? 'border-l-2 border-l-[#A855F7]' : ''}`}>
                        <div 
                          className="cursor-pointer"
                          onClick={() => togglePlanExpanded(plan.plan_id)}
                        >
                          <div className="flex justify-between items-start">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                <h3 className="font-heading text-lg">{plan.name}</h3>
                                {isCompleted && <Check className="w-5 h-5 text-green-500" />}
                                {plan.generated_by_ai && (
                                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#A855F7]/20 text-[#A855F7] border border-[#A855F7]/30">
                                    <Sparkles className="w-3 h-3 inline mr-1" />IA
                                  </span>
                                )}
                                {plan.plan_duration && plan.plan_duration !== "dia" && (
                                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#00F0FF]/10 text-[#00F0FF] border border-[#00F0FF]/30">
                                    {plan.plan_duration === "semana" ? "📆 Semana" : plan.plan_duration === "mes" ? "🗓️ Mês" : plan.plan_duration === "ciclo" ? "🔄 Ciclo" : "📅 Dia"}
                                  </span>
                                )}
                                {plan.generation_mode === "tipo_treino" && plan.split_type && (
                                  <span data-testid={`plan-split-badge-${plan.plan_id}`} className="text-[10px] px-2 py-0.5 rounded-full bg-[#A855F7]/10 text-[#C084FC] border border-[#A855F7]/30 font-bold">
                                    <Dumbbell className="w-3 h-3 inline mr-1" />Treino {plan.split_type}
                                  </span>
                                )}
                                {isExpanded ? (
                                  <ChevronUp className="w-4 h-4 text-[#A1A1AA]" />
                                ) : (
                                  <ChevronDown className="w-4 h-4 text-[#A1A1AA]" />
                                )}
                              </div>
                              {plan.description && <p className="text-sm text-[#A1A1AA] mt-1">{plan.description}</p>}
                              {plan.generation_mode === "tipo_treino" && plan.split_config && (
                                <div className="flex flex-wrap gap-1 mt-1.5">
                                  {plan.split_config.map((s) => (
                                    <span key={s.label} className="text-[10px] px-1.5 py-0.5 rounded bg-[#1A1A2E] text-[#A1A1AA] border border-[#27272A]">
                                      <span className="text-[#A855F7] font-bold">{s.label}</span> {s.name}
                                    </span>
                                  ))}
                                  {plan.training_days_per_week && <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#1A1A2E] text-[#71717A]">{plan.training_days_per_week}x/sem</span>}
                                  {plan.cycle_weeks && <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#1A1A2E] text-[#71717A]">{plan.cycle_weeks} sem</span>}
                                </div>
                              )}
                              <p className="text-xs text-[#52525B] mt-1">
                                {(plan.days && plan.days.length > 0) ? `${plan.days.length} dias · ` : ''}{(plan.exercises || []).length} exercícios
                                {total > 0 && (
                                  <span className={`ml-2 ${isCompleted ? 'text-green-500' : 'text-[#00F0FF]'}`}>
                                    ({completed}/{total} hoje)
                                  </span>
                                )}
                              </p>
                            </div>
                            <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                              {plan.generated_by_ai && (
                                <Button 
                                  variant="ghost" size="sm" 
                                  onClick={() => handleImproveWorkout(plan.plan_id)}
                                  className="text-[#A855F7] h-8 px-2 text-xs gap-1"
                                  title="Melhorar treino com IA"
                                  disabled={improvingPlan === plan.plan_id}
                                >
                                  {improvingPlan === plan.plan_id ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                  ) : (
                                    <><TrendingUp className="w-4 h-4" /> Evoluir</>
                                  )}
                                </Button>
                              )}
                              <Button 
                                variant="ghost" size="sm" 
                                onClick={() => handleStartWorkout(plan, selectedDayIndex)} 
                                className="text-green-400 h-8 w-8 p-0"
                                title="Iniciar treino com timer"
                                disabled={!!activeSession}
                              >
                                <Play className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => openEditDialog(plan)} className="text-[#00F0FF] h-8 w-8 p-0">
                                <Edit2 className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => handleDeletePlan(plan.plan_id)} className="text-red-500 h-8 w-8 p-0">
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>
                        </div>
                        
                        {isExpanded && (
                          <div className="mt-4 border-t border-[#27272A] pt-4">
                            {/* Day selector for multi-day plans */}
                            {plan.days && plan.days.length > 1 && (() => {
                              const hasMultipleWeeks = weekNumbers.length > 1;
                              const currentWeekProgression = plan.weekly_progression?.find(wp => Number(wp.week) === selectedWeek);

                              return (
                                <div className="mb-4 space-y-3">
                                  {/* Week selector (only for multi-week plans) */}
                                  {hasMultipleWeeks && (
                                    <div>
                                      <Label className="text-xs uppercase tracking-wider text-[#A1A1AA] mb-2 block">Semana</Label>
                                      <div className="flex gap-1.5 flex-wrap">
                                        {weekNumbers.map(wn => (
                                          <button
                                            key={wn}
                                            onClick={() => { setSelectedDayIndex(weeks[wn]?.[0]?._globalIdx || 0); }}
                                            className={`px-3 py-1.5 text-xs rounded-lg transition-all font-medium ${
                                              selectedWeek === wn 
                                                ? 'bg-[#A855F7] text-white' 
                                                : 'bg-[#121212] border border-[#27272A] text-[#A1A1AA] hover:border-[#A855F7]'
                                            }`}
                                          >
                                            Sem {wn}
                                          </button>
                                        ))}
                                      </div>
                                      {currentWeekProgression && (
                                        <div className="mt-2 px-3 py-2 bg-[#1A1A2E] rounded-lg border border-[#27272A]">
                                          <p className="text-xs text-[#A855F7] font-medium">{currentWeekProgression.focus}</p>
                                          <p className="text-[11px] text-[#A1A1AA] mt-0.5">{currentWeekProgression.notes}</p>
                                        </div>
                                      )}
                                    </div>
                                  )}

                                  {/* Day selector within week */}
                                  <div>
                                    <Label className="text-xs uppercase tracking-wider text-[#A1A1AA] mb-2 block">
                                      {hasMultipleWeeks ? 'Dia da Semana' : 'Selecione o dia'}
                                    </Label>
                                    <div className="flex gap-1.5 flex-wrap">
                                      {currentWeekDays.map((day, localIdx) => {
                                        const globalIdx = day._globalIdx !== undefined ? day._globalIdx : localIdx;
                                        const splitLabel = day.split_label || '';
                                        const isCardio = splitLabel.toLowerCase() === 'cardio';
                                        return (
                                          <button
                                            key={globalIdx}
                                            onClick={() => setSelectedDayIndex(globalIdx)}
                                            className={`px-3 py-2 text-xs rounded-lg transition-all ${
                                              selectedDayIndex === globalIdx 
                                                ? isCardio ? 'bg-green-600 text-white font-medium' : 'bg-[#00F0FF] text-black font-medium' 
                                                : 'bg-[#121212] border border-[#27272A] text-[#A1A1AA] hover:border-[#00F0FF]'
                                            }`}
                                          >
                                            <div className="flex flex-col items-center gap-0.5">
                                              <span className="font-bold">{splitLabel ? `Treino ${splitLabel}` : `Dia ${localIdx + 1}`}</span>
                                              {day.split_label && hasMultipleWeeks && (
                                                <span className="text-[10px] opacity-75">Dia {localIdx + 1}</span>
                                              )}
                                            </div>
                                          </button>
                                        );
                                      })}
                                    </div>
                                  </div>
                                </div>
                              );
                            })()}

                            {/* Start Workout Button */}
                            <div className="mb-4">
                              <Button 
                                onClick={() => handleStartWorkout(plan, plan.days && plan.days.length > 1 ? selectedDayIndex : 0)} 
                                className="w-full bg-gradient-to-r from-green-600 to-green-500 hover:opacity-90 text-white"
                                disabled={!!activeSession}
                              >
                                <Play className="w-4 h-4 mr-2" /> Iniciar Treino com Timer
                              </Button>
                            </div>

                            <div className="flex justify-between items-center mb-3">
                              <div>
                                <Label className="text-xs uppercase tracking-wider text-[#A1A1AA]">
                                  {plan.days && plan.days.length > 1 
                                    ? (plan.days[selectedDayIndex]?.split_label 
                                      ? `Treino ${plan.days[selectedDayIndex].split_label} - ${plan.days[selectedDayIndex]?.split_label === 'Cardio' ? 'Cardio' : (plan.split_config?.find(s => s.label === plan.days[selectedDayIndex]?.split_label)?.name || plan.days[selectedDayIndex]?.day_label || 'Exercícios')}`
                                      : (plan.days[selectedDayIndex]?.day_label || 'Exercícios'))
                                    : 'Treino de Hoje'
                                  }
                                </Label>
                                {plan.days?.[selectedDayIndex]?.progression_notes && (
                                  <p className="text-[11px] text-[#A855F7] mt-0.5">{plan.days[selectedDayIndex].progression_notes}</p>
                                )}
                              </div>
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                onClick={() => resetDailyWorkout(plan.plan_id)}
                                className="text-xs text-[#A1A1AA] h-6 px-2"
                              >
                                Resetar
                              </Button>
                            </div>
                            <div className="space-y-2">
                              {(() => {
                                const dayExercises = plan.days && plan.days.length > 0 
                                  ? (plan.days[selectedDayIndex]?.exercises || [])
                                  : (plan.exercises || []);
                                return dayExercises.map((ex, idx) => {
                                  const isChecked = status.exercises_status?.[idx] || false;
                                  const tutorialKey = `${plan.plan_id}_${selectedDayIndex}_${idx}`;
                                  const hasTutorial = !!ex.tutorial;
                                  return (
                                    <div key={idx} className="space-y-0">
                                      <div 
                                        className={`flex items-center gap-3 p-3 rounded-t ${hasTutorial && expandedTutorials[tutorialKey] ? '' : 'rounded-b'} cursor-pointer transition-all ${
                                          isChecked 
                                            ? 'bg-[#1a2f1a] border border-green-900' 
                                            : 'bg-[#121212] border border-[#27272A] hover:border-[#3f3f46]'
                                        } ${isCompleted ? 'cursor-default' : ''}`}
                                      >
                                        <div onClick={() => !isCompleted && toggleDailyExercise(plan.plan_id, idx)} className="flex items-center gap-3 flex-1">
                                          <Checkbox 
                                            checked={isChecked}
                                            disabled={isCompleted}
                                            onCheckedChange={() => !isCompleted && toggleDailyExercise(plan.plan_id, idx)}
                                            className="border-[#52525B] data-[state=checked]:bg-[#00F0FF] data-[state=checked]:border-[#00F0FF]"
                                          />
                                          <span className="text-[#52525B] font-mono text-sm">{idx + 1}.</span>
                                          <div className="flex-1">
                                            <span className={`font-mono text-sm ${isChecked ? 'text-green-400 line-through' : 'text-white'}`}>
                                              {ex.name} - {ex.sets}x{ex.reps} {ex.weight && `@ ${ex.weight}`}
                                            </span>
                                            {ex.muscle_group && (
                                              <span className="text-[10px] ml-2 px-1.5 py-0.5 rounded bg-[#27272A] text-[#A1A1AA]">{ex.muscle_group}</span>
                                            )}
                                            {ex.rest_seconds && (
                                              <span className="text-[10px] ml-1 text-[#52525B]">⏱ {ex.rest_seconds}s</span>
                                            )}
                                          </div>
                                        </div>
                                        {hasTutorial && (
                                          <Button 
                                            variant="ghost" size="sm" 
                                            onClick={(e) => { e.stopPropagation(); toggleTutorial(tutorialKey); }}
                                            className={`h-7 w-7 p-0 ${expandedTutorials[tutorialKey] ? 'text-[#A855F7]' : 'text-[#52525B]'}`}
                                            title="Ver tutorial"
                                          >
                                            <BookOpenCheck className="w-4 h-4" />
                                          </Button>
                                        )}
                                        {isChecked && <Check className="w-4 h-4 text-green-500" />}
                                      </div>
                                      
                                      {/* Tutorial Expandable */}
                                      {hasTutorial && expandedTutorials[tutorialKey] && (
                                        <div className="bg-[#0a0a1a] border border-[#27272A] border-t-0 rounded-b p-3 space-y-2">
                                          {ex.tutorial && (
                                            <div>
                                              <p className="text-xs text-[#A855F7] uppercase font-medium mb-1 flex items-center gap-1">
                                                <BookOpenCheck className="w-3 h-3" /> Como executar
                                              </p>
                                              <p className="text-xs text-[#A1A1AA] leading-relaxed">{ex.tutorial}</p>
                                            </div>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  );
                                });
                              })()}
                            </div>
                            
                            {total > 0 && (
                              <div className="mt-4">
                                <div className="flex justify-between text-xs text-[#A1A1AA] mb-1">
                                  <span>Progresso</span>
                                  <span>{Math.round((completed / total) * 100)}%</span>
                                </div>
                                <div className="h-2 bg-[#121212] rounded-full overflow-hidden">
                                  <div 
                                    className="h-full bg-gradient-to-r from-[#00F0FF] to-[#22C55E] transition-all duration-300"
                                    style={{ width: `${(completed / total) * 100}%` }}
                                  />
                                </div>
                              </div>
                            )}
                            
                            {!isCompleted && completed > 0 && (
                              <Button 
                                onClick={() => openCompleteDialog(plan)} 
                                className="w-full mt-4 bg-[#22C55E] hover:bg-[#16A34A] text-black"
                              >
                                <Check className="w-4 h-4 mr-2" /> Concluir Treino do Dia
                              </Button>
                            )}
                            
                            {isCompleted && (
                              <div className="mt-4 p-3 bg-[#1a2f1a] border border-green-900 rounded text-center">
                                <p className="text-green-400 font-semibold">✓ Treino concluído hoje!</p>
                              </div>
                            )}
                          </div>
                        )}
                      </Card>
                    );
                  })
                )}
              </div>
            </TabsContent>

            {/* Stats Tab - Gráficos e IA */}
            <TabsContent value="stats">
<Suspense fallback={<p role="status">Carregando...</p>}><WorkoutsStatsTab detailedStats={detailedStats} stats={stats} getAiSuggestions={getAiSuggestions} loadingSuggestions={loadingSuggestions} aiSuggestions={aiSuggestions} handleSaveInsight={handleSaveInsight} setAiSuggestions={setAiSuggestions} /></Suspense>
</TabsContent>

            <TabsContent value="evolution">
<Suspense fallback={<p role="status">Carregando...</p>}><WorkoutsEvolutionTab openMeasurement={openMeasurement} setOpenMeasurement={setOpenMeasurement} handlePdfUpload={handlePdfUpload} uploadingPdf={uploadingPdf} pdfAnalysis={pdfAnalysis} newMeasurement={newMeasurement} setNewMeasurement={setNewMeasurement} handleCreateMeasurement={handleCreateMeasurement} latestMeasurement={latestMeasurement} loadRecommendations={loadRecommendations} loadingRecommendations={loadingRecommendations} recommendations={recommendations} measurements={measurements} exerciseFilter={exerciseFilter} setExerciseFilter={setExerciseFilter} setExerciseEvoData={setExerciseEvoData} fetchExerciseEvolution={fetchExerciseEvolution} evoLoading={evoLoading} evoError={evoError} exerciseEvoData={exerciseEvoData} /></Suspense>
</TabsContent>

            <TabsContent value="history">
              <div className="space-y-4">
                {workouts.length === 0 ? (
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center">
                    <Calendar className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                    <p className="text-[#A1A1AA]">Nenhum treino no histórico</p>
                  </Card>
                ) : (
                  workouts.map(workout => (
                    <WorkoutCard key={workout.log_id} workout={workout} showDate={true} />
                  ))
                )}
              </div>
            </TabsContent>

            {/* SAVED INSIGHTS TAB */}
            <TabsContent value="saved_insights">
              <div className="space-y-3">
                {savedInsights.length === 0 ? (
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center">
                    <BookOpen className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                    <p className="text-[#A1A1AA]">Nenhuma sugestão salva ainda</p>
                    <p className="text-xs text-[#52525B]">Gere sugestões de treino com IA e salve para consultar depois</p>
                  </Card>
                ) : savedInsights.map(insight => (
                  <Card key={insight.insight_id} className="bg-[#0A0A0A] border-[#27272A] p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <p className="text-sm font-medium">{insight.title}</p>
                        <p className="text-[10px] text-[#52525B]">{new Date(insight.created_at).toLocaleDateString('pt-BR')}</p>
                      </div>
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-[#52525B] hover:text-red-400" onClick={() => handleDeleteInsight(insight.insight_id)}><Trash2 className="w-3 h-3" /></Button>
                    </div>
                    <p className="text-xs text-[#A1A1AA] whitespace-pre-wrap">{insight.content}</p>
                  </Card>
                ))}
              </div>
            </TabsContent>

            {/* ACTIVE SESSION TAB */}
            <TabsContent value="session">
              {activeSession ? (
                <div className="space-y-4">
                  {/* Session Header */}
                  <Card className="bg-gradient-to-r from-[#0A0A0A] to-[#0a1a0a] border-green-900 p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h2 className="font-heading text-2xl text-green-400">{activeSession.plan_name}</h2>
                        <p className="text-sm text-[#A1A1AA]">Sessão ativa</p>
                      </div>
                      <div className="text-right">
                        <div className="font-data text-4xl text-[#00F0FF]">{formatTime(sessionElapsed)}</div>
                        <p className="text-xs text-[#A1A1AA]">Tempo total</p>
                      </div>
                    </div>
                    
                    {/* Progress Bar */}
                    {(() => {
                      const { completed, total, percent } = getSessionProgress();
                      return (
                        <div>
                          <div className="flex justify-between text-xs text-[#A1A1AA] mb-1">
                            <span>{completed}/{total} exercícios</span>
                            <span>{percent}%</span>
                          </div>
                          <div className="h-3 bg-[#121212] rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-gradient-to-r from-green-500 to-[#00F0FF] transition-all duration-500"
                              style={{ width: `${percent}%` }}
                            />
                          </div>
                        </div>
                      );
                    })()}
                  </Card>
                  
                  {/* Next Load Suggestions */}
                  {nextLoads && nextLoads.suggestions && nextLoads.suggestions.some(s => s.next_weight) && (
                    <Card className="bg-[#0A0A0A] border-[#A855F7]/30 p-4">
                      <p className="text-xs text-[#A855F7] uppercase flex items-center gap-1 mb-2">
                        <TrendingUp className="w-3 h-3" /> Próximas cargas sugeridas
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {nextLoads.suggestions.filter(s => s.next_weight).map((s, i) => (
                          <Badge key={i} className="bg-[#A855F7]/10 text-[#A855F7] border-[#A855F7]/30 text-[10px]">
                            {s.name}: {s.next_weight}kg
                          </Badge>
                        ))}
                      </div>
                    </Card>
                  )}

                  {/* Rest Timer */}
                  {isResting && (
                    <Card className="bg-[#0A0A0A] border-[#F59E0B] p-6 text-center animate-pulse">
                      <Clock className="w-8 h-8 text-[#F59E0B] mx-auto mb-2" />
                      <p className="text-xs text-[#F59E0B] uppercase font-medium mb-2">Tempo de Descanso</p>
                      <div className="font-data text-6xl text-[#F59E0B]">{formatTime(restTimer)}</div>
                      <div className="flex gap-2 justify-center mt-4">
                        <Button variant="outline" size="sm" onClick={() => startRestManual(restTimer + 15)} className="border-[#F59E0B] text-[#F59E0B]">+15s</Button>
                        <Button variant="outline" size="sm" onClick={stopRest} className="border-red-500 text-red-400">
                          <Square className="w-3 h-3 mr-1" /> Pular
                        </Button>
                      </div>
                    </Card>
                  )}

                  {/* Rest Timer Presets */}
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <Label className="text-xs uppercase tracking-wider text-[#A1A1AA]">Timer de Descanso</Label>
                      <div className="flex gap-1">
                        {[30, 60, 90, 120].map(sec => (
                          <button
                            key={sec}
                            onClick={() => { setRestDuration(sec); startRestManual(sec); }}
                            className={`px-3 py-1 text-xs rounded ${
                              restDuration === sec && !isResting
                                ? 'bg-[#F59E0B] text-black'
                                : 'bg-[#121212] border border-[#27272A] text-[#A1A1AA] hover:border-[#F59E0B]'
                            }`}
                          >
                            {sec}s
                          </button>
                        ))}
                      </div>
                    </div>
                  </Card>

                  {/* Exercise List */}
                  <div className="space-y-2">
                    {(activeSession.exercises || []).map((ex, idx) => {
                      const tutorialKey = `session_${idx}`;
                      const hasTutorial = !!ex.tutorial;
                      const setsProgress = ex.sets_completed || 0;
                      
                      return (
                        <Card key={idx} className={`border-[#27272A] p-0 overflow-hidden ${
                          ex.completed ? 'bg-[#0a1a0a] border-green-900' : 'bg-[#0A0A0A]'
                        }`}>
                          <div className="p-4">
                            <div className="flex flex-wrap items-center gap-3">
                              <button type="button" disabled={sessionSaving} aria-label={`Alternar conclusão de ${ex.name}`} aria-pressed={!!ex.completed}
                                onClick={() => handleToggleSessionExercise(idx)}
                                className={`w-8 h-8 rounded-full border-2 flex items-center justify-center cursor-pointer transition-all ${
                                  ex.completed 
                                    ? 'bg-green-500 border-green-500' 
                                    : 'border-[#52525B] hover:border-[#00F0FF]'
                                }`}
                              >
                                {ex.completed ? <Check className="w-4 h-4 text-white" /> : <span className="text-xs text-[#52525B]">{idx + 1}</span>}
                              </button>
                              
                              <div className="flex-1">
                                <p className={`font-medium text-sm ${ex.completed ? 'text-green-400 line-through' : 'text-white'}`}>{ex.name}</p>
                                <p className="text-xs text-[#A1A1AA]">
                                  {ex.sets}x{ex.reps} {ex.weight && `@ ${ex.weight}`}
                                  {ex.muscle_group && <span className="ml-2 text-[#52525B]">· {ex.muscle_group}</span>}
                                </p>
                              </div>

                              <div className="flex items-center gap-2">
                                {/* Sets progress */}
                                {!ex.completed && (
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-xs text-[#A1A1AA]">{setsProgress}/{ex.sets}</span>
                                    {setInputIdx === idx ? (
                                      <div className="flex flex-wrap items-center gap-2">
                                        <input
                                          type="text"
                                          aria-label="Carga da série" inputMode="decimal" value={setInputWeight}
                                          onChange={(e) => setSetInputWeight(e.target.value)}
                                          placeholder="carga"
                                          className="w-20 h-11 px-2 text-sm bg-[#18181B] border border-[#00F0FF] rounded text-white text-center"
                                          autoFocus
                                          onKeyDown={(e) => { if (e.key === 'Enter') confirmSet(idx); if (e.key === 'Escape') setSetInputIdx(null); }}
                                        />
                                        <input type="number" min={1} max={999} inputMode="numeric" aria-label="Repetições da série" value={setInputReps} onChange={e => setSetInputReps(e.target.value)} placeholder="reps" className="w-16 h-11 px-2 text-sm bg-[#18181B] border border-slate-600 rounded text-white text-center" />
                                        <input
                                          type="text"
                                          aria-label="Esforço percebido da série (RPE)" inputMode="decimal" value={setInputRpe}
                                          onChange={(e) => setSetInputRpe(e.target.value)}
                                          placeholder="RPE 1–10"
                                          className="w-16 h-11 px-2 text-sm bg-[#18181B] border border-[#A855F7] rounded text-white text-center"
                                          onKeyDown={(e) => { if (e.key === 'Enter') confirmSet(idx); if (e.key === 'Escape') setSetInputIdx(null); }}
                                        />
                                        <Button 
                                          variant="outline" size="sm"
                                          aria-label="Salvar série" disabled={sessionSaving} onClick={() => confirmSet(idx)}
                                          className="h-7 px-2 text-xs border-green-500 text-green-400 hover:bg-green-500 hover:text-black"
                                        >
                                          <Check className="w-3 h-3" />
                                        </Button>
                                      </div>
                                    ) : (
                                      <Button 
                                        variant="outline" size="sm"
                                        aria-label={`Registrar série de ${ex.name}`} disabled={sessionSaving} onClick={() => handleIncrementSets(idx)}
                                        className="h-7 px-2 text-xs border-[#00F0FF] text-[#00F0FF] hover:bg-[#00F0FF] hover:text-black"
                                      >
                                        +1 série
                                      </Button>
                                    )}
                                  </div>
                                )}
                                
                                {/* Previous workout comparison */}
                                {!ex.completed && (
                                  <Button 
                                    variant="ghost" size="sm" 
                                    onClick={() => fetchExerciseHistory(ex.name, idx)}
                                    className={`h-7 px-2 text-xs ${exerciseHistory[idx]?.length > 0 ? 'text-[#00F0FF]' : 'text-[#52525B]'}`}
                                  >
                                    <TrendingUp className="w-3 h-3" /> Anterior
                                  </Button>
                                )}
                                
                                {hasTutorial && (
                                  <Button 
                                    variant="ghost" size="sm" 
                                    onClick={() => toggleTutorial(tutorialKey)}
                                    className={`h-7 w-7 p-0 ${expandedTutorials[tutorialKey] ? 'text-[#A855F7]' : 'text-[#52525B]'}`}
                                  >
                                    <BookOpenCheck className="w-4 h-4" />
                                  </Button>
                                )}
                              </div>
                            </div>

                            {/* Sets indicator dots with weight and RPE */}
                            {!ex.completed && ex.sets > 1 && (
                              <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 ml-11">
                                {Array.from({ length: ex.sets }).map((_, sIdx) => {
                                  const setData = ex.sets_data?.[sIdx];
                                  const isDone = sIdx < setsProgress;
                                  return (
                                    <div key={sIdx} className="flex items-center gap-1">
                                      <div className={`w-2.5 h-2.5 rounded-full transition-all ${
                                        isDone ? 'bg-[#00F0FF]' : 'bg-[#27272A]'
                                      }`} />
                                      {isDone && setData?.weight && (
                                        <span className="text-[10px] text-[#A1A1AA]">{setData.weight}</span>
                                      )}
                                      {isDone && setData?.rpe && (
                                        <span className="text-[9px] text-[#A855F7]">RPE {setData.rpe}</span>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Previous workout comparison */}
                            {exerciseHistory[idx] && exerciseHistory[idx].length > 0 && (
                              <div className="mt-2 ml-11 bg-[#00F0FF]/5 border border-[#00F0FF]/20 rounded p-2">
                                <p className="text-[10px] text-[#00F0FF] uppercase flex items-center gap-1 mb-1">
                                  <TrendingUp className="w-3 h-3" /> Último treino
                                </p>
                                {exerciseHistory[idx].slice(0, 3).map((h, hi) => (
                                  <div key={hi} className="text-[10px] text-[#A1A1AA] flex items-center gap-2">
                                    <span>{h.date?.slice(5)}</span>
                                    {h.sets_data?.length > 0 ? (
                                      h.sets_data.map((sd, si) => (
                                        <span key={si} className="text-[#71717A]">
                                          {sd.weight}kg{sd.rpe ? ` @${sd.rpe}` : ""}
                                        </span>
                                      ))
                                    ) : (
                                      <span>{h.weight}kg x {h.reps}</span>
                                    )}
                                  </div>
                                ))}
                                <div 
                                  className="text-[10px] text-[#00F0FF] mt-1 cursor-pointer"
                                  onClick={() => setActiveTab("evolution")}
                                >
                                  Ver evolução completa →
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Tutorial */}
                          {hasTutorial && expandedTutorials[tutorialKey] && (
                            <div className="bg-[#0a0a1a] border-t border-[#27272A] p-4 space-y-2">
                              {ex.tutorial && (
                                <div>
                                  <p className="text-xs text-[#A855F7] uppercase font-medium mb-1 flex items-center gap-1">
                                    <BookOpenCheck className="w-3 h-3" /> Como executar
                                  </p>
                                  <p className="text-xs text-[#A1A1AA] leading-relaxed">{ex.tutorial}</p>
                                </div>
                              )}
                            </div>
                          )}
                        </Card>
                      );
                    })}
                  </div>

                  {/* Session Actions */}
                  <div className="flex gap-3">
                    <Button 
                      onClick={handleAbandonSession} 
                      variant="outline" 
                      className="flex-1 border-red-900 text-red-400 hover:bg-red-900/20"
                    >
                      <X className="w-4 h-4 mr-2" /> Abandonar
                    </Button>
                    <Button 
                      onClick={() => setShowFeedbackDialog(true)} 
                      className="flex-1 bg-gradient-to-r from-green-600 to-[#00F0FF] text-white hover:opacity-90"
                    >
                      <Trophy className="w-4 h-4 mr-2" /> Finalizar Treino
                    </Button>
                  </div>
                </div>
              ) : (
                <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center">
                  <Dumbbell className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                  <p className="text-[#A1A1AA]">Nenhuma sessão ativa</p>
                  <p className="text-sm text-[#52525B] mt-2">Vá até a aba "Fichas" e clique em "Iniciar Treino"</p>
                </Card>
              )}
            </TabsContent>

          </Tabs>

          {/* FEEDBACK DIALOG */}
          <Dialog open={showFeedbackDialog} onOpenChange={setShowFeedbackDialog}>
            <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-md">
              <DialogHeader>
                <DialogTitle className="font-heading text-xl flex items-center gap-2">
                  <Trophy className="w-5 h-5 text-[#F59E0B]" /> TREINO CONCLUÍDO!
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-6 mt-4">
                {/* Session Summary */}
                {activeSession && (
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div className="bg-[#121212] rounded-lg p-3">
                      <Clock className="w-5 h-5 text-[#00F0FF] mx-auto mb-1" />
                      <p className="font-data text-xl text-[#00F0FF]">{formatTime(sessionElapsed)}</p>
                      <p className="text-[10px] text-[#52525B] uppercase">Duração</p>
                    </div>
                    <div className="bg-[#121212] rounded-lg p-3">
                      <Check className="w-5 h-5 text-green-400 mx-auto mb-1" />
                      <p className="font-data text-xl text-green-400">{getSessionProgress().completed}/{getSessionProgress().total}</p>
                      <p className="text-[10px] text-[#52525B] uppercase">Exercícios</p>
                    </div>
                    <div className="bg-[#121212] rounded-lg p-3">
                      <Flame className="w-5 h-5 text-[#EF4444] mx-auto mb-1" />
                      <p className="font-data text-xl text-[#EF4444]">{Math.round((sessionElapsed / 60) * 6)}</p>
                      <p className="text-[10px] text-[#52525B] uppercase">Cal (est.)</p>
                    </div>
                  </div>
                )}

                {/* Difficulty Rating */}
                <div>
                  <Label className="text-xs uppercase tracking-wider mb-3 block">Intensidade / Dificuldade</Label>
                  <div className="flex gap-2 justify-center">
                    {[1, 2, 3, 4, 5].map(level => (
                      <button
                        key={level}
                        onClick={() => setFeedbackData({...feedbackData, difficulty: level})}
                        className={`w-12 h-12 rounded-lg flex items-center justify-center transition-all ${
                          feedbackData.difficulty >= level 
                            ? 'bg-[#F59E0B] text-black' 
                            : 'bg-[#121212] border border-[#27272A] text-[#52525B]'
                        }`}
                      >
                        <Star className={`w-5 h-5 ${feedbackData.difficulty >= level ? 'fill-current' : ''}`} />
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-[#A1A1AA] text-center mt-2">
                    {feedbackData.difficulty === 1 && "Muito fácil"}
                    {feedbackData.difficulty === 2 && "Fácil"}
                    {feedbackData.difficulty === 3 && "Moderado"}
                    {feedbackData.difficulty === 4 && "Difícil"}
                    {feedbackData.difficulty === 5 && "Muito difícil"}
                  </p>
                </div>

                {/* Feeling */}
                <div>
                  <Label className="text-xs uppercase tracking-wider mb-2 block">Como você se sentiu?</Label>
                  <div className="flex gap-2 flex-wrap justify-center">
                    {[
                      { value: "otimo", label: "Ótimo", emoji: "🔥" },
                      { value: "bom", label: "Bom", emoji: "💪" },
                      { value: "regular", label: "Regular", emoji: "😐" },
                      { value: "cansado", label: "Cansado", emoji: "😮‍💨" },
                      { value: "exausto", label: "Exausto", emoji: "😵" }
                    ].map(f => (
                      <button
                        key={f.value}
                        onClick={() => setFeedbackData({...feedbackData, feeling: f.value})}
                        className={`px-4 py-2 rounded-lg text-sm transition-all ${
                          feedbackData.feeling === f.value
                            ? 'bg-[#00F0FF] text-black font-medium'
                            : 'bg-[#121212] border border-[#27272A] text-[#A1A1AA] hover:border-[#00F0FF]'
                        }`}
                      >
                        {f.emoji} {f.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Notes */}
                <div>
                  <Label className="text-xs uppercase tracking-wider">Observações</Label>
                  <Textarea 
                    value={feedbackData.notes} 
                    onChange={(e) => setFeedbackData({...feedbackData, notes: e.target.value})}
                    placeholder="Como foi o treino? Algo a melhorar?"
                    className="bg-[#121212] border-[#27272A] text-white mt-1"
                    rows={3}
                  />
                </div>

                <div className="flex gap-2">
                  <Button onClick={() => setShowFeedbackDialog(false)} variant="outline" className="flex-1 border-[#27272A]">
                    Voltar
                  </Button>
                  <Button onClick={handleCompleteSession} className="flex-1 bg-gradient-to-r from-green-600 to-[#00F0FF] text-white">
                    <Trophy className="w-4 h-4 mr-2" /> Concluir
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>

          {/* IMPORT WORKOUT DIALOG */}
          <Dialog open={showImportDialog} onOpenChange={setShowImportDialog}>
            <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-md">
              <DialogHeader><DialogTitle className="flex items-center gap-2"><Upload className="w-5 h-5 text-purple-400" />Importar Ficha de Treino</DialogTitle></DialogHeader>
              <div className="space-y-4 py-2">
                <div className={`border-2 border-dashed rounded-lg p-6 text-center ${importFile ? 'border-purple-500 bg-purple-500/10' : 'border-[#27272A]'}`}>
                  {importFile ? (
                    <div className="flex items-center justify-center gap-2">
                      <FileText className="w-5 h-5 text-purple-400" />
                      <span className="text-sm text-purple-300">{importFile.name}</span>
                      <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => setImportFile(null)}><XCircle className="w-4 h-4 text-red-400" /></Button>
                    </div>
                  ) : (
                    <label className="cursor-pointer">
                      <Upload className="w-8 h-8 mx-auto text-[#A1A1AA] mb-2" />
                      <p className="text-sm text-[#A1A1AA]">Clique para selecionar</p>
                      <p className="text-xs text-[#52525B]">PDF ou Imagem da ficha de treino</p>
                      <input type="file" accept=".pdf,image/*" className="hidden" onChange={e => setImportFile(e.target.files?.[0] || null)} />
                    </label>
                  )}
                </div>
                <Button onClick={handleImportWorkout} disabled={!importFile || importLoading} className="w-full bg-purple-600 hover:bg-purple-700">
                  {importLoading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Analisando ficha...</> : <><Sparkles className="w-4 h-4 mr-2" />Importar Treino</>}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </PullToRefresh>
      </div>
      <MobileNav user={user} />
    </div>
  );
}
