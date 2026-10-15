import WorkoutGeneratorDialog from '@/components/WorkoutGeneratorDialog';
import { editableExercises, editPlanExercises, planEditPayload } from '@/lib/workout-plan-editor';
import { createDailyWorkoutQueue } from '@/lib/daily-workout-queue';
import WorkoutTutorial from '@/components/WorkoutTutorial';
import { cachedGet, queryClient, cacheKey, sessionVersion } from '@/lib/query-cache';
import { openSirius } from '@/lib/sirius-context';
import WorkoutSession from '@/components/WorkoutSession';
import { workoutSummary } from '@/lib/workout-session';
import { lazy, Suspense } from 'react';
import { writeSaved } from "@/lib/session-storage";
import { createActivityRequests } from "@/lib/activity-requests";
import { getCurrentUser } from "@/lib/api";
import { getWorkoutCalendar } from "@/lib/workout-calendar";
import { getApiErrorMessage } from "@/lib/api-errors";
import { useEffect, useState, useCallback, useRef } from "react";
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
import { Dumbbell, Plus, Trash2, Play, Check, X, Timer, Flame, TrendingUp, Calendar, FileText, Activity, Edit2, ChevronDown, ChevronUp, Scale, Upload, Sparkles, BarChart3, RefreshCw, Loader2, BookOpen, XCircle, Zap, BookOpenCheck, Star, Clock, Trophy } from "lucide-react";

import axios from "@/lib/module-requests";
import { toast } from "sonner";

const WorkoutsStatsTab = lazy(() => import('@/components/tabs/WorkoutsStatsTab'));
const WorkoutsEvolutionTab = lazy(() => import('@/components/tabs/WorkoutsEvolutionTab'));
const TrainingIntelligence = lazy(() => import('@/components/TrainingIntelligence'));
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
  const workoutWrite = async (method, url, body, replayKey) => {
    if (workoutBusy.current) throw new Error('Aguarde o registro em andamento');
    const key = replayKey || workoutRequests.current.begin('workout-session', JSON.stringify({ method, url, body }));
    if (!key) throw new Error('Aguarde o registro em andamento');
    workoutBusy.current = true; setSessionSaving(true);
    let succeeded = false;
    try { const response = await axios[method](url, body, { headers: { 'Idempotency-Key': key } }); succeeded = true; return response; }
    finally { workoutRequests.current.finish('workout-session', succeeded); workoutBusy.current = false; setSessionSaving(false); }
  };
  const [workouts, setWorkouts] = useState([]);
  const [plans, setPlans] = useState(() => queryClient.getQueryData(cacheKey('/workout-plans')) || []);
  const [stats, setStats] = useState(null);
  const [detailedStats, setDetailedStats] = useState(null);
  const [openLog, setOpenLog] = useState(false);
  const [openPlan, setOpenPlan] = useState(false);
  const [openEditPlan, setOpenEditPlan] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [editingDay, setEditingDay] = useState(0);
  const editingExercises = editableExercises(editingPlan, editingDay);
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


  // Today's schedule
  const [todaySchedule, setTodaySchedule] = useState(null);

  // Workout Session
  const [activeSession, setActiveSession] = useState(null);
  const [sessionElapsed, setSessionElapsed] = useState(0);
  const [completionSummary, setCompletionSummary] = useState(null);
  const restDuration = 60;
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
        getCurrentUser().then(result => { setUser(result.data); return result; }), axios.get(`${API}/workouts`), cachedGet('/workout-plans').then(data => ({ data })),
      ]);
      setUser(userRes.data);
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
      } catch { /* Optional operation failed; preserve the current view. */ }

      const plansData = Array.isArray(plansRes.data) ? plansRes.data : [];
      if (plansData.length) {
        try { const states = await cachedGet('/daily-workout-status'); setDailyStatus(Object.fromEntries(Object.entries(states).map(([id, state]) => [id, dailyWrites.current?.reconcile(id, state) || state]))); }
        catch (error) { toast.error(getApiErrorMessage(error, 'Não foi possível atualizar os marcadores. Os dados anteriores foram mantidos.')); }
      } else setDailyStatus({});
      
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Não foi possível carregar os treinos. Tente atualizar a página.'));
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);



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

  const dailyWrites = useRef(null);
  if (!dailyWrites.current) {
    const owner = sessionVersion();
    dailyWrites.current = createDailyWorkoutQueue({
      write: async (planId, exerciseIdx, key) => {
        if (owner !== sessionVersion()) throw Object.assign(new Error('Session changed'), { response: { status: 401 } });
        return (await axios.post(`${API}/daily-workout-status/${planId}/toggle/${exerciseIdx}`, {}, { withCredentials: true, headers: { 'Idempotency-Key': key }, timeout: 20000 })).data;
      },
      publish: (planId, state) => { if (owner === sessionVersion()) setDailyStatus(prev => ({ ...prev, [planId]: state })); },
      failed: (error, retry) => {
        if (owner !== sessionVersion()) return;
        toast.error(getApiErrorMessage(error, "Erro ao atualizar exercício"), retry ? { duration: Infinity, action: { label: 'Tentar novamente', onClick: retry } } : undefined);
        if (error.response?.status === 409) checkActiveSession();
      },
    });
  }
  const toggleDailyExercise = (planId, exerciseIdx) => {
    dailyWrites.current.enqueue(planId, exerciseIdx, dailyStatus[planId]);
  };

  const resetDailyWorkout = async (planId) => {
    if (dailyWrites.current.busy(planId)) { toast.error("Aguarde o envio das marcações pendentes."); return; }
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
    
    setCompletingPlan(plan);
    setCompleteWorkoutData({
      duration_minutes: estimatedDuration,
      calories: null,
      notes: ""
    });
    setOpenCompleteWorkout(true);
  };

  const handleCompleteWorkout = async () => {
    if (!completingPlan) return;
    if (dailyWrites.current.busy(completingPlan.plan_id)) { toast.error('Aguarde o envio das marcações pendentes.'); return; }
    
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
    if (editingPlan.composition_policy?.version === 1 && editingPlan.days?.some(day => !day.exercises?.length)) {
      toast.error('Cada sessão planejada precisa de ao menos um exercício.');
      return;
    }
    try {
      await axios.patch(`${API}/workout-plans/${editingPlan.plan_id}`, planEditPayload(editingPlan), { withCredentials: true });
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
    setEditingDay(0);
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
    setEditingPlan(previous => editPlanExercises(previous, editingDay, exercises => [...exercises, { ...editExercise }]));
    setEditExercise({ name: "", sets: 3, reps: 12, weight: "" });
  };

  const removeExerciseFromEditPlan = (index) => {
    setEditingPlan(previous => editPlanExercises(previous, editingDay, exercises => exercises.filter((_, i) => i !== index)));
  };

  const updateExerciseInEditPlan = (index, field, value) => {
    setEditingPlan(previous => editPlanExercises(previous, editingDay, exercises => exercises.map((exercise, position) =>
      position === index ? { ...exercise, [field]: field === 'sets' ? parseInt(value) || 0 : value } : exercise)));
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
    } catch { /* Optional operation failed; preserve the current view. */ }
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
    } catch { /* Optional operation failed; preserve the current view. */ }
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
      setNextLoads(null);

      toast.success("Treino iniciado! Bora! 💪");
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao iniciar treino"));
    }
  };

  const [nextLoads, setNextLoads] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const fetchNextLoads = useCallback(async (planId) => {
    setLoadError(false);
    try {
      const res = await axios.get(`${API}/workouts/next-loads`, { params: { plan_id: planId }, withCredentials: true });
      setNextLoads(res.data);
    } catch { setLoadError(true); }
  }, []);
  useEffect(() => { if (activeSession?.plan_id) fetchNextLoads(activeSession.plan_id); }, [activeSession?.plan_id, fetchNextLoads]);
  const saveSessionSet = async operation => {
    try {
      const res = await workoutWrite('patch', `${API}/workout-sessions/${activeSession.session_id}/exercise/${operation.index}`, operation.body, operation.key);
      setActiveSession(current => current?.session_id === res.data.session_id && current.revision > res.data.revision ? current : res.data);
      return res.data;
    } catch (failure) {
      if (failure.response?.status === 409) await checkActiveSession();
      throw failure;
    }
  };
  const fetchSessionHistory = async exerciseName => {
    const data = await cachedGet(`/workouts/exercise-history?exercise_name=${encodeURIComponent(exerciseName)}`);
    return data.history || [];
  };

  const clearSessionStorage = () => {
    if (!user || !activeSession) return;
    writeSaved(`sirius-rest:${user.user_id}:${activeSession.session_id}`, null);
    writeSaved(`sirius-workout-ux2:${user.user_id}:${activeSession.session_id}`, null);
    writeSaved(`sirius-workout-draft:${user.user_id}:${activeSession.session_id}`, null);
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
      setCompletionSummary({ ...workoutSummary(activeSession), duration: res.data.total_duration_seconds, xp: res.data.xp_earned });
      setShowFeedbackDialog(false);
      clearSessionStorage();
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
      clearSessionStorage();
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
                {workout.calories != null && <span className="ml-2" title="Valor registrado; origem não verificada. Registros antigos podem conter estimativas.">🔥 {workout.calories} kcal registradas</span>}
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
      
      <div className={`flex-1 min-w-0 ml-0 p-4 md:p-6 lg:p-8 pb-24 md:pb-8 md:pt-0 page-enter`}>
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

          <div className="sirius-page-heading sirius-hero flex flex-col xl:flex-row justify-between items-start xl:items-center mb-8 gap-4 min-w-0">
            <div className="min-w-0 max-w-full">
              <div className="sirius-eyebrow">Movimento e constância</div>
              <h1 className="font-heading text-3xl md:text-4xl mb-2" data-testid="workouts-title">Seu próximo passo começa aqui.</h1>
              <p className="text-[#A1A1AA]">Seus treinos, suas marcas e a evolução de cada semana.</p><Button variant="ghost" className="mt-2" onClick={() => openSirius({ surface: 'workouts', draft: 'Ajude-me a entender meus treinos e minha evolução.' })}>Conversar com Sirius</Button>
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

              <WorkoutGeneratorDialog
                generate={async (payload, key) => (await axios.post(`${API}/workout-plans/generate`, payload,
                  { withCredentials: true, timeout: 300000, headers: { 'Idempotency-Key': key } })).data}
                onSaved={loadData}
              />
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
                  
                  {editingPlan.days?.length > 1 && <label className="block space-y-2 text-sm">Sessão para editar<select aria-label="Sessão para editar" className="w-full min-h-11 rounded-xl border border-border bg-background px-3" value={editingDay} onChange={event => setEditingDay(Number(event.target.value))}>{editingPlan.days.map((day, index) => <option key={index} value={index}>{day.day_label || day.day_name || `Sessão ${index + 1}`}</option>)}</select><span className="block text-xs text-muted-foreground">Alterações ficam nesta sessão. As demais semanas são preservadas.</span></label>}
                  {editingExercises.length > 0 && (
                    <div className="border-t border-[#27272A] pt-4">
                      <Label className="text-xs uppercase tracking-wider mb-3 block">Exercícios da Ficha</Label>
                      <div className="space-y-3">
                        {editingExercises.map((ex, idx) => (
                          <div key={idx} className="bg-[#121212] p-3 rounded border border-[#27272A]">
                            <div className="flex items-center justify-between mb-2">
                              <Input 
                                aria-label={`Exercício ${idx + 1}`}
                                value={ex.name} 
                                onChange={(e) => updateExerciseInEditPlan(idx, 'name', e.target.value)}
                                className="bg-[#0A0A0A] border-[#27272A] text-white flex-1 mr-2"
                                placeholder="Nome do exercício"
                              />
                              <Button aria-label={`Remover exercício ${idx + 1}`} variant="ghost" size="sm" onClick={() => removeExerciseFromEditPlan(idx)} className="text-red-500 h-11 w-11 p-0">
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                            <div className="grid grid-cols-3 gap-2">
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Séries</Label>
                                <Input 
                                  type="number" min="1" max="100" aria-label={`Séries ${idx + 1}`}
                                  value={ex.sets} 
                                  onChange={(e) => updateExerciseInEditPlan(idx, 'sets', e.target.value)}
                                  className="bg-[#0A0A0A] border-[#27272A] text-white"
                                />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Reps</Label>
                                <Input 
                                  type="text" aria-label={`Repetições ${idx + 1}`}
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
                        aria-label="Novo exercício"
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
                            type="text"
                            value={editExercise.reps} 
                            onChange={(e) => setEditExercise({...editExercise, reps: e.target.value})}
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
                      <Label htmlFor="completed-workout-calories" className="text-xs uppercase tracking-wider">Calorias (opcional)</Label>
                      <Input 
                        id="completed-workout-calories"
                        type="number" 
                        min="0"
                        max="50000"
                        value={completeWorkoutData.calories ?? ""}
                        onChange={(e) => setCompleteWorkoutData({...completeWorkoutData, calories: e.target.value === "" ? null : Number(e.target.value)})}
                        placeholder="Não informado"
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
            <div className="sirius-workout-stats flex flex-wrap items-center gap-6 p-4 bg-[#0A0A0A] border border-[#27272A] rounded-lg mb-6">
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
                <span className="text-xs text-[#A1A1AA] uppercase">Cal registradas</span>
                <span className="font-heading text-xl">{stats.total_calories ?? 'Não informado'}</span>
              </div>
              <div className="h-6 w-px bg-[#27272A]" />
              <div className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-[#22C55E]" />
                <span className="text-xs text-[#A1A1AA] uppercase">XP</span>
                <span className="font-heading text-xl">{stats.total_xp_earned}</span>
              </div>
              <p className="w-full text-xs text-[#A1A1AA]">Calorias com origem não verificada; registros antigos podem conter estimativas. O total exige informação em todos os treinos concluídos do período.</p>
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
            <TabsList className="bg-[#0A0A0A] border border-[#27272A] mb-6 overflow-x-auto flex-nowrap w-full max-w-full justify-start xl:justify-center">
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
              <TabsTrigger value="intelligence" className="data-[state=active]:bg-[#27272A]">Inteligência</TabsTrigger>
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
                      <Card key={plan.plan_id} className={`min-w-0 bg-[#0A0A0A] border-[#27272A] p-4 ${isCompleted ? 'border-green-900 bg-[#0a1a0a]' : ''} ${plan.generated_by_ai ? 'border-l-2 border-l-[#A855F7]' : ''}`}>
                        <div 
                          className="cursor-pointer"
                          onClick={() => togglePlanExpanded(plan.plan_id)}
                        >
                          <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-start">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                <h3 className="font-heading break-words text-lg">{plan.name}</h3>
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
                            <div className="flex max-w-full shrink-0 flex-wrap gap-1" onClick={(e) => e.stopPropagation()}>
                              {plan.generated_by_ai && (
                                <Button 
                                  variant="ghost" size="sm" 
                                  onClick={() => handleImproveWorkout(plan.plan_id)}
                                  className="text-[#A855F7] h-11 px-2 text-xs gap-1"
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
                                className="text-green-400 h-11 w-11 p-0"
                                title="Iniciar treino com timer"
                                disabled={!!activeSession}
                              >
                                <Play className="w-4 h-4" />
                              </Button>
                              <Button aria-label={`Editar ${plan.name}`} variant="ghost" size="sm" onClick={() => openEditDialog(plan)} className="text-[#00F0FF] h-11 w-11 p-0">
                                <Edit2 className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => handleDeletePlan(plan.plan_id)} className="text-red-500 h-11 w-11 p-0">
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
                                  const hasTutorial = !!ex.name;
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
                                            onClick={event => event.stopPropagation()}
                                            aria-label={`Marcar ${ex.name}`}
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
                                            aria-label={`Ver tutorial de ${ex.name}`} aria-expanded={!!expandedTutorials[tutorialKey]}
                                          >
                                            <BookOpenCheck className="w-4 h-4" />
                                          </Button>
                                        )}
                                        {isChecked && <Check className="w-4 h-4 text-green-500" />}
                                      </div>
                                      
                                      {/* Tutorial Expandable */}
                                      {hasTutorial && expandedTutorials[tutorialKey] && (
                                        <div className="bg-[#0a0a1a] border border-[#27272A] border-t-0 rounded-b p-3 space-y-2">
                                          <WorkoutTutorial exercise={ex} />
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

            <TabsContent value="intelligence">
              <Suspense fallback={<p role="status">Carregando análise…</p>}>
                <TrainingIntelligence userId={user?.user_id} plans={plans} />
              </Suspense>
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
              {activeSession && user ? (
                <WorkoutSession key={`${user.user_id}:${activeSession.session_id}`} session={activeSession} userId={user.user_id}
                  elapsed={sessionElapsed} saving={sessionSaving} onSave={saveSessionSet}
                  onFinish={() => setShowFeedbackDialog(true)} onAbandon={handleAbandonSession}
                  onHistory={fetchSessionHistory} nextLoads={nextLoads} loadError={loadError} />
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
                <DialogDescription>Confira os registros e conte como foi seu treino antes de concluir.</DialogDescription>
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
                      <Dumbbell className="w-5 h-5 text-purple-300 mx-auto mb-1" />
                      <p className="font-data text-xl text-purple-300">{workoutSummary(activeSession).sets}</p>
                      <p className="text-[10px] text-slate-400 uppercase">Séries registradas</p>
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
                        aria-label={`Dificuldade ${level} de 5`} aria-pressed={feedbackData.difficulty === level}
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
                  <Button disabled={sessionSaving} onClick={handleCompleteSession} className="flex-1 bg-gradient-to-r from-green-600 to-[#00F0FF] text-white">
                    <Trophy className="w-4 h-4 mr-2" /> Concluir
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>

          <Dialog open={!!completionSummary} onOpenChange={open => { if (!open) setCompletionSummary(null); }}>
            <DialogContent className="ws-dialog">
              <DialogHeader><DialogTitle>Treino concluído!</DialogTitle><DialogDescription>Resumo dos dados registrados nesta sessão.</DialogDescription></DialogHeader>
              {completionSummary && <dl className="grid grid-cols-2 gap-5 text-sm">
                <div><dt className="text-slate-400">Duração</dt><dd className="text-2xl">{formatTime(completionSummary.duration)}</dd></div>
                <div><dt className="text-slate-400">Exercícios concluídos</dt><dd className="text-2xl">{completionSummary.exercises}/{completionSummary.total}</dd></div>
                <div><dt className="text-slate-400">Séries registradas</dt><dd className="text-2xl">{completionSummary.sets}</dd></div>
                <div><dt className="text-slate-400">XP recebido</dt><dd className="text-2xl text-green-300">+{completionSummary.xp}</dd></div>
                {completionSummary.volume != null && <div className="col-span-2"><dt className="text-slate-400">Volume total (carga × repetições)</dt><dd className="text-2xl">{completionSummary.volume.toLocaleString('pt-BR', { maximumFractionDigits: 3 })} kg</dd></div>}
              </dl>}
              <Button onClick={() => setCompletionSummary(null)}>Continuar</Button>
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
      
    </div>
  );
}
