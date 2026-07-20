import { useEffect, useState, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { getLocalDateStr } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Dumbbell, Plus, Trash2, Play, Check, X, Timer, Flame, TrendingUp, Calendar, FileText, Activity, Edit2, ChevronDown, ChevronUp, Scale, Upload, Sparkles, Target, Ruler, BarChart3, RefreshCw, Loader2, Save, BookOpen, XCircle, Zap, BookOpenCheck, Star, Pause, RotateCcw, Square, Clock, Trophy, ChevronRight, Heart, ShieldCheck } from "lucide-react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, PieChart, Pie, Cell } from 'recharts';
import axios from "axios";
import { toast } from "sonner";

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
  const [workouts, setWorkouts] = useState([]);
  const [plans, setPlans] = useState([]);
  const [stats, setStats] = useState(null);
  const [detailedStats, setDetailedStats] = useState(null);
  const [openLog, setOpenLog] = useState(false);
  const [openPlan, setOpenPlan] = useState(false);
  const [openEditPlan, setOpenEditPlan] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [activeTab, setActiveTab] = useState("log");
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
    health_condition: ""
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
  const [selectedDayIndex, setSelectedDayIndex] = useState(0);
  const [selectedWeek, setSelectedWeek] = useState(1);
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
      const [userRes, workoutsRes, plansRes, statsRes, detailedStatsRes, measurementsRes, latestRes, quoteRes] = await Promise.all([
        axios.get(`${API}/auth/me`, { withCredentials: true }),
        axios.get(`${API}/workouts`, { withCredentials: true }),
        axios.get(`${API}/workout-plans`, { withCredentials: true }),
        axios.get(`${API}/workout-stats?period=week`, { withCredentials: true }),
        axios.get(`${API}/workout-stats/detailed`, { withCredentials: true }),
        axios.get(`${API}/body-measurements?limit=30`, { withCredentials: true }),
        axios.get(`${API}/body-measurements/latest`, { withCredentials: true }),
        axios.get(`${API}/motivational-quote`, { withCredentials: true })
      ]);
      setUser(userRes.data);
      // Pre-fill health condition from user profile
      if (userRes.data.health_condition) {
        setAiGenForm(prev => ({ ...prev, health_condition: userRes.data.health_condition }));
      }
      setWorkouts(Array.isArray(workoutsRes.data) ? workoutsRes.data : []);
      setPlans(Array.isArray(plansRes.data) ? plansRes.data : []);
      setStats(statsRes.data || null);
      setDetailedStats(detailedStatsRes.data || null);
      setMeasurements(Array.isArray(measurementsRes.data) ? measurementsRes.data : []);
      setLatestMeasurement(latestRes.data || null);
      setMotivationalQuote(quoteRes.data || null);
      
      // Load daily status for each plan
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
      toast.error("Erro ao atualizar exercício");
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
    } catch (err) { toast.error(err.response?.data?.detail || "Erro ao importar treino"); }
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

  // === AI GENERATION ===
  const handleGenerateWithAI = async () => {
    setGeneratingPlan(true);
    try {
      const payload = {
        objective: aiGenForm.objective,
        level: aiGenForm.level,
        generation_mode: aiGenMode,
        health_condition: aiGenForm.health_condition || null,
      };
      
      if (aiGenMode === "tipo_treino") {
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
      
      const res = await axios.post(`${API}/workout-plans/generate`, payload, { withCredentials: true, timeout: 120000 });
      if (res.data.success) {
        toast.success(`Treino gerado com IA! +${res.data.xp_earned} XP`);
        setOpenAiGenerate(false);
        setAiGenForm(prev => ({
          ...prev,
          objective: "hipertrofia",
          level: "intermediario",
          muscle_groups: [],
          duration: "dia"
        }));
        loadData();
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao gerar treino com IA");
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
      const res = await axios.post(`${API}/workout-plans/${planId}/improve`, {}, { withCredentials: true, timeout: 120000 });
      if (res.data.success) {
        toast.success(`Treino evoluído! +${res.data.xp_earned} XP`);
        if (res.data.improvements_summary) {
          toast.info(res.data.improvements_summary, { duration: 8000 });
        }
        loadData();
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao melhorar treino");
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

  // Session timer
  useEffect(() => {
    let interval;
    if (activeSession && activeSession.status === "active") {
      interval = setInterval(() => {
        setSessionElapsed(prev => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [activeSession]);

  // Rest timer
  useEffect(() => {
    let interval;
    if (isResting && restTimer > 0) {
      interval = setInterval(() => {
        setRestTimer(prev => {
          if (prev <= 1) {
            setIsResting(false);
            // Play beep sound
            try {
              const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
              const oscillator = audioCtx.createOscillator();
              oscillator.type = 'sine';
              oscillator.frequency.setValueAtTime(880, audioCtx.currentTime);
              oscillator.connect(audioCtx.destination);
              oscillator.start();
              oscillator.stop(audioCtx.currentTime + 0.3);
            } catch {}
            toast.success("Descanso finalizado! Próxima série 💪");
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isResting, restTimer]);

  const handleStartWorkout = async (plan, dayIdx = 0) => {
    try {
      const res = await axios.post(`${API}/workout-sessions/start`, {
        plan_id: plan.plan_id,
        day_index: dayIdx,
        rest_timer_seconds: restDuration
      }, { withCredentials: true });
      setActiveSession(res.data);
      setSessionElapsed(0);
      setActiveTab("session");
      toast.success("Treino iniciado! Bora! 💪");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao iniciar treino");
    }
  };

  const handleToggleSessionExercise = async (idx) => {
    if (!activeSession) return;
    const ex = activeSession.exercises[idx];
    const newCompleted = !ex.completed;
    const newSetsCompleted = newCompleted ? ex.sets : 0;
    
    try {
      const res = await axios.patch(
        `${API}/workout-sessions/${activeSession.session_id}/exercise/${idx}`,
        { completed: newCompleted, sets_completed: newSetsCompleted, current_exercise_idx: idx },
        { withCredentials: true }
      );
      setActiveSession(res.data);
      
      if (newCompleted) {
        toast.success(`${ex.name} concluído! ✅`);
        // Auto-start rest timer for next exercise
        const nextIdx = activeSession.exercises.findIndex((e, i) => i > idx && !e.completed);
        if (nextIdx >= 0) {
          setRestTimer(ex.rest_seconds || restDuration);
          setIsResting(true);
        }
      }
    } catch (error) {
      toast.error("Erro ao atualizar exercício");
    }
  };

  const handleIncrementSets = async (idx) => {
    if (!activeSession) return;
    const ex = activeSession.exercises[idx];
    const newSetsCompleted = Math.min((ex.sets_completed || 0) + 1, ex.sets);
    const allSetsCompleted = newSetsCompleted >= ex.sets;
    
    try {
      const res = await axios.patch(
        `${API}/workout-sessions/${activeSession.session_id}/exercise/${idx}`,
        { sets_completed: newSetsCompleted, completed: allSetsCompleted },
        { withCredentials: true }
      );
      setActiveSession(res.data);
      
      if (allSetsCompleted) {
        toast.success(`${ex.name} - Todas as séries concluídas! ✅`);
      } else {
        // Start rest timer between sets
        setRestTimer(ex.rest_seconds || restDuration);
        setIsResting(true);
        toast.info(`Série ${newSetsCompleted}/${ex.sets} concluída. Descanse!`);
      }
    } catch (error) {
      toast.error("Erro ao atualizar série");
    }
  };

  const startRestManual = (seconds) => {
    setRestTimer(seconds || restDuration);
    setIsResting(true);
  };

  const stopRest = () => {
    setRestTimer(0);
    setIsResting(false);
  };

  const handleCompleteSession = async () => {
    if (!activeSession) return;
    try {
      const res = await axios.post(
        `${API}/workout-sessions/${activeSession.session_id}/complete`,
        feedbackData,
        { withCredentials: true }
      );
      toast.success(`Treino concluído! +${res.data.xp_earned} XP 🏆`);
      setShowFeedbackDialog(false);
      setActiveSession(null);
      setSessionElapsed(0);
      setFeedbackData({ difficulty: 3, feeling: "bom", notes: "" });
      setActiveTab("log");
      loadData();
    } catch (error) {
      toast.error("Erro ao finalizar treino");
    }
  };

  const handleAbandonSession = async () => {
    if (!activeSession) return;
    try {
      await axios.post(`${API}/workout-sessions/${activeSession.session_id}/abandon`, {}, { withCredentials: true });
      toast.info("Sessão abandonada");
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
    <div className="flex min-h-screen bg-[#050505]">
      <Sidebar user={user} />
      <div className="flex-1 ml-0 md:ml-64 p-4 md:p-8 pb-24 md:pb-8 pt-[72px] md:pt-8">
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

          <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
            <div>
              <h1 className="font-heading text-3xl md:text-4xl mb-2" data-testid="workouts-title">ÁREA DE TREINOS</h1>
              <p className="text-[#A1A1AA]">Registre e acompanhe sua evolução física</p>
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
            <div className="flex items-center gap-6 p-4 bg-[#0A0A0A] border border-[#27272A] rounded-lg mb-6">
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
                              // Group days by week
                              const weeks = {};
                              plan.days.forEach((day, idx) => {
                                const weekNum = day.week || Math.floor(idx / (plan.training_days_per_week || 5)) + 1;
                                if (!weeks[weekNum]) weeks[weekNum] = [];
                                weeks[weekNum].push({ ...day, _globalIdx: idx });
                              });
                              const weekNumbers = Object.keys(weeks).map(Number).sort((a, b) => a - b);
                              const hasMultipleWeeks = weekNumbers.length > 1;
                              const currentWeekDays = hasMultipleWeeks ? (weeks[selectedWeek] || weeks[weekNumbers[0]] || []) : plan.days.map((d, i) => ({ ...d, _globalIdx: i }));
                              const currentWeekProgression = plan.weekly_progression?.find(wp => wp.week === selectedWeek);

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
                                            onClick={() => { setSelectedWeek(wn); setSelectedDayIndex(weeks[wn]?.[0]?._globalIdx || 0); }}
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
              <div className="space-y-6">
                {/* Consistency - Better Design */}
                {detailedStats && (
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
                    <div className="flex items-center justify-between mb-6">
                      <div>
                        <h3 className="font-heading text-xl mb-1">CONSISTÊNCIA</h3>
                        <p className="text-sm text-[#A1A1AA]">Últimos 30 dias de treino</p>
                      </div>
                      <div className="text-right">
                        <span className="font-data text-4xl text-[#00F0FF]">{detailedStats.consistency_percentage}%</span>
                        <p className="text-xs text-[#A1A1AA]">{detailedStats.trained_days} de 30 dias</p>
                      </div>
                    </div>
                    
                    {/* Calendar-style grid - 6 weeks x 7 days */}
                    <div className="grid grid-cols-7 gap-2">
                      {['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'].map(day => (
                        <div key={day} className="text-center text-xs text-[#52525B] pb-2">{day}</div>
                      ))}
                      {detailedStats.daily_data?.map((day, idx) => {
                        const dayOfWeek = new Date(day.date).getDay();
                        return (
                          <div
                            key={idx}
                            className={`aspect-square rounded-lg flex items-center justify-center transition-all hover:scale-105 cursor-pointer ${
                              day.count > 0 ? 'bg-[#00F0FF]' : 'bg-[#1a1a1a] border border-[#27272A]'
                            }`}
                            style={{
                              opacity: day.count > 0 ? Math.min(0.5 + (day.duration / 60) * 0.5, 1) : 1,
                              gridColumn: idx === 0 ? dayOfWeek + 1 : undefined
                            }}
                            title={`${day.date}: ${day.count > 0 ? `${day.duration}min, ${day.calories}cal` : 'Sem treino'}`}
                          >
                            {day.count > 0 && <Check className="w-4 h-4 text-black" />}
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                )}

                {/* Stats Grid */}
                {detailedStats && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4 text-center">
                      <Flame className="w-8 h-8 text-[#F59E0B] mx-auto mb-2" />
                      <div className="font-data text-3xl text-[#F59E0B]">{detailedStats.current_streak}</div>
                      <div className="text-xs text-[#A1A1AA] uppercase">Streak Atual</div>
                    </Card>
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4 text-center">
                      <TrendingUp className="w-8 h-8 text-[#22C55E] mx-auto mb-2" />
                      <div className="font-data text-3xl text-[#22C55E]">{detailedStats.best_streak}</div>
                      <div className="text-xs text-[#A1A1AA] uppercase">Melhor Streak</div>
                    </Card>
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4 text-center">
                      <Timer className="w-8 h-8 text-[#A855F7] mx-auto mb-2" />
                      <div className="font-data text-3xl text-[#A855F7]">{detailedStats.avg_duration_minutes}</div>
                      <div className="text-xs text-[#A1A1AA] uppercase">Min/Treino</div>
                    </Card>
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4 text-center">
                      <Flame className="w-8 h-8 text-[#EF4444] mx-auto mb-2" />
                      <div className="font-data text-3xl text-[#EF4444]">{detailedStats.avg_calories || 0}</div>
                      <div className="text-xs text-[#A1A1AA] uppercase">Cal/Treino</div>
                    </Card>
                  </div>
                )}

                {/* Workout Charts */}
                {detailedStats && detailedStats.daily_data && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {/* Training Frequency Chart */}
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                      <h3 className="font-heading text-sm mb-3 flex items-center gap-2"><Activity className="w-4 h-4 text-[#00F0FF]" />Frequência de Treino (30 dias)</h3>
                      <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={detailedStats.daily_data.filter((_, i) => i % 2 === 0)}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                          <XAxis dataKey="date" tick={{ fill: '#71717A', fontSize: 9 }} tickFormatter={(v) => v.slice(5)} />
                          <YAxis tick={{ fill: '#71717A', fontSize: 10 }} />
                          <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A', color: '#fff', fontSize: 11 }} />
                          <Bar dataKey="count" fill="#00F0FF" name="Treinos" radius={[2, 2, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </Card>

                    {/* Duration Trend */}
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                      <h3 className="font-heading text-sm mb-3 flex items-center gap-2"><Timer className="w-4 h-4 text-[#A855F7]" />Duração por Dia (min)</h3>
                      <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={detailedStats.daily_data.filter((_, i) => i % 2 === 0)}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                          <XAxis dataKey="date" tick={{ fill: '#71717A', fontSize: 9 }} tickFormatter={(v) => v.slice(5)} />
                          <YAxis tick={{ fill: '#71717A', fontSize: 10 }} />
                          <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A', color: '#fff', fontSize: 11 }} />
                          <Line type="monotone" dataKey="duration" stroke="#A855F7" strokeWidth={2} dot={false} name="Minutos" />
                          <Line type="monotone" dataKey="calories" stroke="#EF4444" strokeWidth={1} dot={false} name="Calorias" />
                          <Legend />
                        </LineChart>
                      </ResponsiveContainer>
                    </Card>

                    {/* Streak & Consistency */}
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                      <h3 className="font-heading text-sm mb-3 flex items-center gap-2"><Flame className="w-4 h-4 text-orange-400" />Consistência</h3>
                      <div className="grid grid-cols-3 gap-3 text-center">
                        <div>
                          <p className="font-data text-2xl text-orange-400">{detailedStats.current_streak}</p>
                          <p className="text-[10px] text-[#71717A] uppercase">Sequência Atual</p>
                        </div>
                        <div>
                          <p className="font-data text-2xl text-[#39FF14]">{detailedStats.best_streak}</p>
                          <p className="text-[10px] text-[#71717A] uppercase">Melhor Sequência</p>
                        </div>
                        <div>
                          <p className="font-data text-2xl text-[#00F0FF]">{detailedStats.consistency_percentage}%</p>
                          <p className="text-[10px] text-[#71717A] uppercase">Consistência</p>
                        </div>
                      </div>
                      <div className="mt-3">
                        <div className="flex justify-between text-[10px] text-[#71717A] mb-1">
                          <span>{detailedStats.trained_days} de {detailedStats.total_days} dias treinados</span>
                        </div>
                        <div className="w-full bg-[#27272A] rounded-full h-2">
                          <div className="h-2 rounded-full bg-gradient-to-r from-orange-500 to-[#39FF14]" style={{ width: `${detailedStats.consistency_percentage}%` }}></div>
                        </div>
                      </div>
                    </Card>

                    {/* Activity Type Distribution */}
                    {stats && stats.by_activity_type && Object.keys(stats.by_activity_type).length > 0 && (
                      <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                        <h3 className="font-heading text-sm mb-3 flex items-center gap-2"><Target className="w-4 h-4 text-[#39FF14]" />Tipo de Atividade</h3>
                        <ResponsiveContainer width="100%" height={200}>
                          <PieChart>
                            <Pie
                              data={Object.entries(stats.by_activity_type).map(([name, value]) => ({ name, value }))}
                              dataKey="value"
                              nameKey="name"
                              cx="50%"
                              cy="50%"
                              outerRadius={70}
                              label={(entry) => entry.name}
                            >
                              {Object.keys(stats.by_activity_type).map((_, i) => (
                                <Cell key={i} fill={['#00F0FF', '#A855F7', '#39FF14', '#FF9500', '#FF3B30', '#FFD700'][i % 6]} />
                              ))}
                            </Pie>
                            <Tooltip />
                          </PieChart>
                        </ResponsiveContainer>
                      </Card>
                    )}
                  </div>
                )}

                {/* AI Suggestions */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h3 className="font-heading text-xl mb-1 flex items-center gap-2">
                        <Sparkles className="w-5 h-5 text-[#A855F7]" />
                        SUGESTÕES DE TREINO
                      </h3>
                      <p className="text-sm text-[#A1A1AA]">Recomendações personalizadas por IA</p>
                    </div>
                    <Button
                      onClick={getAiSuggestions}
                      disabled={loadingSuggestions}
                      className="bg-gradient-to-r from-[#A855F7] to-[#00F0FF] hover:opacity-90 text-white"
                    >
                      {loadingSuggestions ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <Sparkles className="w-4 h-4 mr-2" />
                          Gerar
                        </>
                      )}
                    </Button>
                  </div>
                  
                  {aiSuggestions ? (
                    <div className="mt-4">
                      <div className="bg-[#121212] rounded-lg p-4 border border-[#27272A]">
                        <p className="text-[#A1A1AA] whitespace-pre-wrap text-sm leading-relaxed">
                          {aiSuggestions.suggestions}
                        </p>
                      </div>
                      <div className="mt-3 flex justify-between items-center">
                        <span className="text-xs text-[#52525B]">
                          Baseado em {aiSuggestions.based_on?.total_workouts || 0} treinos
                        </span>
                        <div className="flex gap-2">
                          <Button variant="ghost" size="sm" onClick={() => handleSaveInsight(aiSuggestions.suggestions)} className="text-xs text-green-400 hover:text-green-300"><Save className="w-3 h-3 mr-1" />Salvar</Button>
                          <Button variant="ghost" size="sm" onClick={() => setAiSuggestions(null)} className="text-xs text-[#52525B] hover:text-white">Limpar</Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-[#52525B] text-center py-4">
                      Clique em "Gerar" para receber sugestões personalizadas
                    </p>
                  )}
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="evolution">
              <div className="grid gap-6">
                {/* Header com botões */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                  <div>
                    <h2 className="font-heading text-xl">EVOLUÇÃO CORPORAL</h2>
                    <p className="text-sm text-[#A1A1AA]">Acompanhe suas medidas e progresso</p>
                  </div>
                  <div className="flex gap-2">
                    <Dialog open={openMeasurement} onOpenChange={setOpenMeasurement}>
                      <DialogTrigger asChild>
                        <Button className="bg-[#00F0FF] hover:bg-[#00D4E5] text-black">
                          <Plus className="w-4 h-4 mr-2" /> Nova Medição
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-2xl max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                          <DialogTitle className="font-heading text-xl">REGISTRAR MEDIDAS</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-6 mt-4">
                          {/* Upload PDF */}
                          <div className="border border-dashed border-[#27272A] rounded-lg p-4 text-center">
                            <input
                              type="file"
                              accept=".pdf"
                              onChange={handlePdfUpload}
                              className="hidden"
                              id="pdf-upload"
                            />
                            <label htmlFor="pdf-upload" className="cursor-pointer">
                              <Upload className="w-8 h-8 text-[#00F0FF] mx-auto mb-2" />
                              <p className="text-sm text-[#A1A1AA]">
                                {uploadingPdf ? "Analisando PDF..." : "Clique para importar PDF de avaliação física"}
                              </p>
                            </label>
                            {pdfAnalysis?.extracted_data?.recommendations && (
                              <div className="mt-4 text-left bg-[#121212] p-3 rounded">
                                <p className="text-xs text-[#00F0FF] uppercase mb-2">Recomendações do PDF:</p>
                                <p className="text-sm text-[#A1A1AA]">{(pdfAnalysis.extracted_data.recommendations || []).join(", ")}</p>
                              </div>
                            )}
                          </div>
                          
                          <div>
                            <Label className="text-xs uppercase tracking-wider">Data</Label>
                            <Input type="date" value={newMeasurement.date} onChange={(e) => setNewMeasurement({...newMeasurement, date: e.target.value})} className="bg-[#121212] border-[#27272A] text-white mt-1" />
                          </div>
                          
                          {/* Peso e Composição */}
                          <div>
                            <Label className="text-xs uppercase tracking-wider mb-3 block text-[#00F0FF]">Peso e Composição Corporal</Label>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Peso (kg)</Label>
                                <Input type="number" step="0.1" value={newMeasurement.weight_kg} onChange={(e) => setNewMeasurement({...newMeasurement, weight_kg: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Altura (cm)</Label>
                                <Input type="number" step="0.1" value={newMeasurement.height_cm} onChange={(e) => setNewMeasurement({...newMeasurement, height_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Gordura (%)</Label>
                                <Input type="number" step="0.1" value={newMeasurement.body_fat_percentage} onChange={(e) => setNewMeasurement({...newMeasurement, body_fat_percentage: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Massa Musc. (kg)</Label>
                                <Input type="number" step="0.1" value={newMeasurement.muscle_mass_kg} onChange={(e) => setNewMeasurement({...newMeasurement, muscle_mass_kg: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Massa Óssea (kg)</Label>
                                <Input type="number" step="0.1" value={newMeasurement.bone_mass_kg} onChange={(e) => setNewMeasurement({...newMeasurement, bone_mass_kg: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Água (%)</Label>
                                <Input type="number" step="0.1" value={newMeasurement.water_percentage} onChange={(e) => setNewMeasurement({...newMeasurement, water_percentage: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Gord. Visceral</Label>
                                <Input type="number" value={newMeasurement.visceral_fat} onChange={(e) => setNewMeasurement({...newMeasurement, visceral_fat: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Idade Metab.</Label>
                                <Input type="number" value={newMeasurement.metabolic_age} onChange={(e) => setNewMeasurement({...newMeasurement, metabolic_age: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                            </div>
                          </div>
                          
                          {/* Medidas Corporais */}
                          <div>
                            <Label className="text-xs uppercase tracking-wider mb-3 block text-[#00F0FF]">Medidas Corporais (cm)</Label>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Pescoço</Label>
                                <Input type="number" step="0.1" value={newMeasurement.neck_cm} onChange={(e) => setNewMeasurement({...newMeasurement, neck_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Ombros</Label>
                                <Input type="number" step="0.1" value={newMeasurement.shoulders_cm} onChange={(e) => setNewMeasurement({...newMeasurement, shoulders_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Peito</Label>
                                <Input type="number" step="0.1" value={newMeasurement.chest_cm} onChange={(e) => setNewMeasurement({...newMeasurement, chest_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Cintura</Label>
                                <Input type="number" step="0.1" value={newMeasurement.waist_cm} onChange={(e) => setNewMeasurement({...newMeasurement, waist_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Abdômen</Label>
                                <Input type="number" step="0.1" value={newMeasurement.abdomen_cm} onChange={(e) => setNewMeasurement({...newMeasurement, abdomen_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Quadril</Label>
                                <Input type="number" step="0.1" value={newMeasurement.hips_cm} onChange={(e) => setNewMeasurement({...newMeasurement, hips_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Braço Esq.</Label>
                                <Input type="number" step="0.1" value={newMeasurement.left_arm_cm} onChange={(e) => setNewMeasurement({...newMeasurement, left_arm_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Braço Dir.</Label>
                                <Input type="number" step="0.1" value={newMeasurement.right_arm_cm} onChange={(e) => setNewMeasurement({...newMeasurement, right_arm_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Antebraço Esq.</Label>
                                <Input type="number" step="0.1" value={newMeasurement.left_forearm_cm} onChange={(e) => setNewMeasurement({...newMeasurement, left_forearm_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Antebraço Dir.</Label>
                                <Input type="number" step="0.1" value={newMeasurement.right_forearm_cm} onChange={(e) => setNewMeasurement({...newMeasurement, right_forearm_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Coxa Esq.</Label>
                                <Input type="number" step="0.1" value={newMeasurement.left_thigh_cm} onChange={(e) => setNewMeasurement({...newMeasurement, left_thigh_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Coxa Dir.</Label>
                                <Input type="number" step="0.1" value={newMeasurement.right_thigh_cm} onChange={(e) => setNewMeasurement({...newMeasurement, right_thigh_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Panturrilha Esq.</Label>
                                <Input type="number" step="0.1" value={newMeasurement.left_calf_cm} onChange={(e) => setNewMeasurement({...newMeasurement, left_calf_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                              <div>
                                <Label className="text-xs text-[#A1A1AA]">Panturrilha Dir.</Label>
                                <Input type="number" step="0.1" value={newMeasurement.right_calf_cm} onChange={(e) => setNewMeasurement({...newMeasurement, right_calf_cm: e.target.value})} className="bg-[#121212] border-[#27272A] text-white" />
                              </div>
                            </div>
                          </div>
                          
                          <div>
                            <Label className="text-xs uppercase tracking-wider">Observações</Label>
                            <Textarea value={newMeasurement.notes} onChange={(e) => setNewMeasurement({...newMeasurement, notes: e.target.value})} placeholder="Notas adicionais..." className="bg-[#121212] border-[#27272A] text-white mt-1" />
                          </div>
                          
                          <Button onClick={handleCreateMeasurement} className="w-full bg-[#00F0FF] hover:bg-[#00D4E5] text-black">
                            Salvar Medidas
                          </Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>

                {/* Cards de Resumo */}
                {latestMeasurement && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                      <div className="flex items-center gap-3">
                        <Scale className="w-8 h-8 text-[#00F0FF]" />
                        <div>
                          <p className="text-xs text-[#A1A1AA] uppercase">Peso</p>
                          <p className="font-heading text-2xl">{latestMeasurement.weight_kg || "-"} kg</p>
                        </div>
                      </div>
                    </Card>
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                      <div className="flex items-center gap-3">
                        <Target className="w-8 h-8 text-[#F59E0B]" />
                        <div>
                          <p className="text-xs text-[#A1A1AA] uppercase">IMC</p>
                          <p className="font-heading text-2xl">{latestMeasurement.bmi || "-"}</p>
                        </div>
                      </div>
                    </Card>
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                      <div className="flex items-center gap-3">
                        <Flame className="w-8 h-8 text-[#EF4444]" />
                        <div>
                          <p className="text-xs text-[#A1A1AA] uppercase">Gordura</p>
                          <p className="font-heading text-2xl">{latestMeasurement.body_fat_percentage || "-"}%</p>
                        </div>
                      </div>
                    </Card>
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                      <div className="flex items-center gap-3">
                        <Ruler className="w-8 h-8 text-[#22C55E]" />
                        <div>
                          <p className="text-xs text-[#A1A1AA] uppercase">Cintura</p>
                          <p className="font-heading text-2xl">{latestMeasurement.waist_cm || "-"} cm</p>
                        </div>
                      </div>
                    </Card>
                  </div>
                )}

                {/* Recomendações da IA */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
                  <div className="flex justify-between items-center mb-4">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-[#00F0FF]" />
                      <h3 className="font-heading text-lg">RECOMENDAÇÕES DA IA</h3>
                    </div>
                    <Button 
                      onClick={loadRecommendations} 
                      variant="outline" 
                      size="sm" 
                      className="border-[#27272A]"
                      disabled={loadingRecommendations}
                    >
                      {loadingRecommendations ? "Carregando..." : "Atualizar"}
                    </Button>
                  </div>
                  {recommendations ? (
                    <div className="prose prose-invert max-w-none">
                      <p className="text-[#A1A1AA] whitespace-pre-wrap">{recommendations.recommendations}</p>
                    </div>
                  ) : (
                    <p className="text-[#52525B]">Clique em "Atualizar" para receber recomendações personalizadas baseadas em suas medidas e treinos.</p>
                  )}
                </Card>

                {/* Histórico de Medidas */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
                  <h3 className="font-heading text-lg mb-4">HISTÓRICO DE MEDIDAS</h3>
                  {measurements.length === 0 ? (
                    <p className="text-[#52525B] text-center py-4">Nenhuma medida registrada ainda</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-[#27272A]">
                            <th className="text-left p-2 text-[#A1A1AA]">Data</th>
                            <th className="text-right p-2 text-[#A1A1AA]">Peso</th>
                            <th className="text-right p-2 text-[#A1A1AA]">IMC</th>
                            <th className="text-right p-2 text-[#A1A1AA]">Gordura</th>
                            <th className="text-right p-2 text-[#A1A1AA]">Cintura</th>
                            <th className="text-right p-2 text-[#A1A1AA]">Fonte</th>
                          </tr>
                        </thead>
                        <tbody>
                          {measurements.slice(0, 10).map((m, idx) => (
                            <tr key={m.measurement_id || idx} className="border-b border-[#27272A]/50">
                              <td className="p-2">{m.date}</td>
                              <td className="text-right p-2">{m.weight_kg || "-"} kg</td>
                              <td className="text-right p-2">{m.bmi || "-"}</td>
                              <td className="text-right p-2">{m.body_fat_percentage || "-"}%</td>
                              <td className="text-right p-2">{m.waist_cm || "-"} cm</td>
                              <td className="text-right p-2 text-xs text-[#52525B]">{m.source}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </Card>
              </div>
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

                  {/* Rest Timer */}
                  {isResting && (
                    <Card className="bg-[#0A0A0A] border-[#F59E0B] p-6 text-center animate-pulse">
                      <Clock className="w-8 h-8 text-[#F59E0B] mx-auto mb-2" />
                      <p className="text-xs text-[#F59E0B] uppercase font-medium mb-2">Tempo de Descanso</p>
                      <div className="font-data text-6xl text-[#F59E0B]">{formatTime(restTimer)}</div>
                      <div className="flex gap-2 justify-center mt-4">
                        <Button variant="outline" size="sm" onClick={() => setRestTimer(prev => prev + 15)} className="border-[#F59E0B] text-[#F59E0B]">+15s</Button>
                        <Button variant="outline" size="sm" onClick={stopRest} className="border-red-500 text-red-400">
                          <Square className="w-3 h-3 mr-1" /> Pular
                        </Button>
                      </div>
                    </Card>
                  )}

                  {/* Rest Timer Presets */}
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                    <div className="flex items-center justify-between">
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
                            <div className="flex items-center gap-3">
                              <div 
                                onClick={() => handleToggleSessionExercise(idx)}
                                className={`w-8 h-8 rounded-full border-2 flex items-center justify-center cursor-pointer transition-all ${
                                  ex.completed 
                                    ? 'bg-green-500 border-green-500' 
                                    : 'border-[#52525B] hover:border-[#00F0FF]'
                                }`}
                              >
                                {ex.completed ? <Check className="w-4 h-4 text-white" /> : <span className="text-xs text-[#52525B]">{idx + 1}</span>}
                              </div>
                              
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
                                  <div className="flex items-center gap-1">
                                    <span className="text-xs text-[#A1A1AA]">{setsProgress}/{ex.sets}</span>
                                    <Button 
                                      variant="outline" size="sm"
                                      onClick={() => handleIncrementSets(idx)}
                                      className="h-7 px-2 text-xs border-[#00F0FF] text-[#00F0FF] hover:bg-[#00F0FF] hover:text-black"
                                    >
                                      +1 série
                                    </Button>
                                  </div>
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

                            {/* Sets indicator dots */}
                            {!ex.completed && ex.sets > 1 && (
                              <div className="flex gap-1 mt-2 ml-11">
                                {Array.from({ length: ex.sets }).map((_, sIdx) => (
                                  <div 
                                    key={sIdx} 
                                    className={`w-3 h-3 rounded-full transition-all ${
                                      sIdx < setsProgress ? 'bg-[#00F0FF]' : 'bg-[#27272A]'
                                    }`}
                                  />
                                ))}
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
      </div>
      <MobileNav user={user} />
    </div>
  );
}
