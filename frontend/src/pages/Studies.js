import { useState, useEffect, useRef, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import axios from "axios";
import ExportButtons from "@/components/ExportButtons";
import {
  BookOpen, Plus, Trash2, Folder, FileText, Clock, Calendar,
  Brain, Layers, Target, Trophy, Flame, ChevronRight, Loader2,
  GraduationCap, Briefcase, FolderOpen, RotateCcw, CheckCircle2,
  XCircle, Sparkles, PenTool, Link, Play, Pause,
  Edit3, Tag, AlertCircle, Timer, BookMarked, Lightbulb, Repeat,
  Send, ArrowLeft, BarChart3, HelpCircle, Zap, Coffee,
  MessageSquare, ChevronDown, ChevronUp, Hash, Award, TrendingUp,
  Upload, ListChecks, ClipboardList, Eye, EyeOff, ChevronLeft, CircleDot,
  SkipForward, Flag, StopCircle, FileUp, Scale, LayoutGrid,
  Download, Image, BellRing, Paperclip, Network
} from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, PieChart, Pie, Cell } from 'recharts';
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const areaIcons = {
  "graduation-cap": GraduationCap,
  "file-text": FileText,
  "briefcase": Briefcase,
  "folder": Folder,
  "book": BookOpen
};

const taskTypeLabels = {
  reading: "Leitura", exercise: "Exercício", review: "Revisão", project: "Projeto", exam: "Prova"
};
const recurrenceLabels = {
  once: "Única vez", daily: "Diária", weekly: "Semanal", monthly: "Mensal"
};
const dayLabels = {
  monday: "Seg", tuesday: "Ter", wednesday: "Qua", thursday: "Qui",
  friday: "Sex", saturday: "Sáb", sunday: "Dom"
};

// ========== POMODORO TIMER COMPONENT ==========
function PomodoroTimer({ notebooks, onComplete }) {
  const [isRunning, setIsRunning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isBreak, setIsBreak] = useState(false);
  const [timeLeft, setTimeLeft] = useState(25 * 60);
  const [focusMinutes, setFocusMinutes] = useState(25);
  const [breakMinutes, setBreakMinutes] = useState(5);
  const [selectedNb, setSelectedNb] = useState("");
  const [sessionsCompleted, setSessionsCompleted] = useState(0);
  const [showSettings, setShowSettings] = useState(false);
  const intervalRef = useRef(null);

  const handleFocusComplete = useCallback(async () => {
    try {
      await axios.post(`${API}/study/focus/complete`, {
        notebook_id: selectedNb || null,
        focus_minutes: focusMinutes,
        break_minutes: breakMinutes,
        notes: null
      }, { withCredentials: true });
      setSessionsCompleted(prev => prev + 1);
      toast.success(`Sessão concluída! +XP 🎉`);
      if (onComplete) onComplete();
    } catch (err) {
      console.error(err);
    }
  }, [selectedNb, focusMinutes, breakMinutes, onComplete]);

  useEffect(() => {
    if (isRunning && !isPaused) {
      intervalRef.current = setInterval(() => {
        setTimeLeft(prev => {
          if (prev <= 1) {
            clearInterval(intervalRef.current);
            if (!isBreak) {
              // Focus completed
              handleFocusComplete();
              setIsBreak(true);
              return breakMinutes * 60;
            } else {
              // Break completed
              setIsBreak(false);
              setIsRunning(false);
              toast.success("Pausa finalizada! Pronto para mais?");
              return focusMinutes * 60;
            }
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(intervalRef.current);
  }, [isRunning, isPaused, isBreak, breakMinutes, focusMinutes, handleFocusComplete]);

  const startTimer = () => {
    setIsRunning(true);
    setIsPaused(false);
    setTimeLeft(focusMinutes * 60);
    setIsBreak(false);
  };

  const togglePause = () => setIsPaused(p => !p);
  const resetTimer = () => {
    clearInterval(intervalRef.current);
    setIsRunning(false);
    setIsPaused(false);
    setIsBreak(false);
    setTimeLeft(focusMinutes * 60);
  };

  const mins = Math.floor(timeLeft / 60);
  const secs = timeLeft % 60;
  const totalSecs = isBreak ? breakMinutes * 60 : focusMinutes * 60;
  const progress = ((totalSecs - timeLeft) / totalSecs) * 100;

  return (
    <Card className={`border-2 transition-all ${isBreak ? 'bg-emerald-950/30 border-emerald-500/30' : isRunning ? 'bg-red-950/20 border-red-500/30' : 'bg-[#0A0A0A] border-[#27272A]'}`}>
      <CardContent className="p-4 md:p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Timer className={`w-5 h-5 ${isBreak ? 'text-emerald-400' : 'text-red-400'}`} />
            <span className="font-bold text-sm">{isBreak ? 'PAUSA' : 'FOCO'}</span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              <Coffee className="w-3 h-3 mr-1" /> {sessionsCompleted} sessões
            </Badge>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setShowSettings(!showSettings)}>
              <Edit3 className="w-3 h-3" />
            </Button>
          </div>
        </div>

        {showSettings && !isRunning && (
          <div className="mb-4 p-3 bg-[#121212] rounded-lg space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Foco (min)</Label>
                <Input type="number" value={focusMinutes} onChange={e => { setFocusMinutes(Number(e.target.value)); setTimeLeft(Number(e.target.value) * 60); }} className="bg-[#0A0A0A] border-[#27272A] h-8 text-sm" min={1} max={120} />
              </div>
              <div>
                <Label className="text-xs">Pausa (min)</Label>
                <Input type="number" value={breakMinutes} onChange={e => setBreakMinutes(Number(e.target.value))} className="bg-[#0A0A0A] border-[#27272A] h-8 text-sm" min={1} max={30} />
              </div>
            </div>
            <div>
              <Label className="text-xs">Matéria (opcional)</Label>
              <Select value={selectedNb} onValueChange={setSelectedNb}>
                <SelectTrigger className="bg-[#0A0A0A] border-[#27272A] h-8 text-sm">
                  <SelectValue placeholder="Nenhuma" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Nenhuma</SelectItem>
                  {notebooks.map(nb => (
                    <SelectItem key={nb.notebook_id} value={nb.notebook_id}>{nb.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        <div className="text-center mb-4">
          <div className={`text-5xl md:text-6xl font-mono font-bold tracking-wider ${isBreak ? 'text-emerald-400' : isRunning ? 'text-red-400' : 'text-white'}`}>
            {String(mins).padStart(2, '0')}:{String(secs).padStart(2, '0')}
          </div>
          <Progress value={progress} className="mt-3 h-1.5" />
        </div>

        <div className="flex justify-center gap-2">
          {!isRunning ? (
            <Button onClick={startTimer} className="bg-red-600 hover:bg-red-700 px-8">
              <Play className="w-4 h-4 mr-2" /> Iniciar Foco
            </Button>
          ) : (
            <>
              <Button onClick={togglePause} variant="outline" className="border-yellow-500 text-yellow-500">
                {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
              </Button>
              <Button onClick={resetTimer} variant="outline" className="border-red-500 text-red-500">
                <RotateCcw className="w-4 h-4" />
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ========== AI CHAT COMPONENT ==========
function StudyAIChat({ notebooks, selectedNotebook }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [contextType, setContextType] = useState("general");
  const [uploadFile, setUploadFile] = useState(null);
  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() && !uploadFile) return;
    const userContent = uploadFile ? `📎 ${uploadFile.name}\n${input || "Analise este arquivo"}` : input;
    const userMsg = { role: "user", content: userContent };
    setMessages(prev => [...prev, userMsg]);
    const currentInput = input;
    setInput("");
    setLoading(true);
    try {
      if (uploadFile) {
        // File upload mode
        const formData = new FormData();
        formData.append("file", uploadFile);
        formData.append("message", currentInput || "Analise este documento e faça um resumo detalhado.");
        formData.append("context_type", contextType);
        if (selectedNotebook?.notebook_id) formData.append("notebook_id", selectedNotebook.notebook_id);
        
        const res = await axios.post(`${API}/study/ai-chat-with-file`, formData, {
          withCredentials: true,
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 120000
        });
        setMessages(prev => [...prev, { role: "assistant", content: res.data.response }]);
        setUploadFile(null);
      } else {
        // Normal text mode
        const res = await axios.post(`${API}/study/ai-chat`, {
          message: currentInput,
          notebook_id: selectedNotebook?.notebook_id || null,
          context_type: contextType
        }, { withCredentials: true });
        setMessages(prev => [...prev, { role: "assistant", content: res.data.response }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: "assistant", content: "Desculpe, ocorreu um erro. Tente novamente." }]);
    } finally {
      setLoading(false);
    }
  };

  const contextOptions = [
    { value: "general", label: "Geral", icon: MessageSquare },
    { value: "explain", label: "Explicar", icon: Lightbulb },
    { value: "quiz_help", label: "Questões", icon: HelpCircle },
    { value: "summarize", label: "Resumir", icon: FileText },
    { value: "motivate", label: "Motivar", icon: Zap }
  ];

  return (
    <Card className="bg-[#0A0A0A] border-[#27272A] flex flex-col h-[400px] md:h-[500px]">
      <CardHeader className="pb-2 border-b border-[#27272A]">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#00F0FF]" />
            Assistente de Estudos
          </CardTitle>
        </div>
        <div className="flex gap-1 flex-wrap mt-1">
          {contextOptions.map(opt => {
            const Icon = opt.icon;
            return (
              <Button key={opt.value} variant={contextType === opt.value ? "default" : "ghost"} size="sm" className={`h-6 text-xs px-2 ${contextType === opt.value ? 'bg-[#007AFF]' : ''}`} onClick={() => setContextType(opt.value)}>
                <Icon className="w-3 h-3 mr-1" /> {opt.label}
              </Button>
            );
          })}
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-[#A1A1AA] py-8 text-sm">
            <Brain className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>Pergunte qualquer coisa sobre seus estudos!</p>
            <p className="text-xs mt-2 text-[#52525B]">📎 Envie PDFs ou imagens para resumo com IA</p>
          </div>
        )}
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] p-3 rounded-lg text-sm whitespace-pre-wrap ${msg.role === 'user' ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#E4E4E7]'}`}>
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-[#121212] p-3 rounded-lg"><Loader2 className="w-4 h-4 animate-spin text-[#00F0FF]" /></div>
          </div>
        )}
        <div ref={chatEndRef} />
      </CardContent>
      <div className="p-3 border-t border-[#27272A]">
        {uploadFile && (
          <div className="flex items-center gap-2 mb-2 p-2 bg-[#121212] rounded-lg">
            <Paperclip className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-purple-300 flex-1 truncate">{uploadFile.name}</span>
            <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => setUploadFile(null)}><XCircle className="w-3 h-3 text-red-400" /></Button>
          </div>
        )}
        <div className="flex gap-2">
          <input type="file" ref={fileInputRef} className="hidden" accept=".pdf,image/*" onChange={e => { if (e.target.files[0]) setUploadFile(e.target.files[0]); e.target.value = ''; }} />
          <Button variant="ghost" size="icon" className="shrink-0 text-[#A1A1AA] hover:text-purple-400" onClick={() => fileInputRef.current?.click()} title="Enviar PDF ou imagem">
            <Paperclip className="w-4 h-4" />
          </Button>
          <Input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()} placeholder={uploadFile ? "Mensagem sobre o arquivo..." : "Pergunte algo..."} className="bg-[#121212] border-[#27272A] text-sm" />
          <Button onClick={sendMessage} disabled={loading || (!input.trim() && !uploadFile)} size="icon" className="bg-[#007AFF] shrink-0">
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </Card>
  );
}

// ========== QUESTION LOGGER COMPONENT ==========
function QuestionLogger({ notebooks, onLog }) {
  const [nbId, setNbId] = useState("");
  const [total, setTotal] = useState(10);
  const [correct, setCorrect] = useState(0);
  const [saving, setSaving] = useState(false);

  const handleLog = async () => {
    if (!nbId || total < 1) { toast.error("Selecione matéria e quantidade"); return; }
    if (correct > total) { toast.error("Acertos não pode ser maior que total"); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/study/questions/log`, {
        notebook_id: nbId, total, correct, source: "manual"
      }, { withCredentials: true });
      toast.success(`${total} questões registradas! +${correct * 2} XP`);
      setTotal(10); setCorrect(0);
      if (onLog) onLog();
    } catch (err) {
      toast.error("Erro ao registrar questões");
    } finally {
      setSaving(false);
    }
  };

  const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;

  return (
    <Card className="bg-[#0A0A0A] border-[#27272A]">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Hash className="w-4 h-4 text-purple-400" />
          Registrar Questões
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Select value={nbId} onValueChange={setNbId}>
          <SelectTrigger className="bg-[#121212] border-[#27272A] h-9 text-sm">
            <SelectValue placeholder="Selecione a matéria" />
          </SelectTrigger>
          <SelectContent>
            {notebooks.map(nb => (
              <SelectItem key={nb.notebook_id} value={nb.notebook_id}>{nb.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label className="text-xs">Total</Label>
            <Input type="number" value={total} onChange={e => setTotal(Number(e.target.value))} className="bg-[#121212] border-[#27272A] h-8 text-sm" min={1} />
          </div>
          <div>
            <Label className="text-xs">Acertos</Label>
            <Input type="number" value={correct} onChange={e => setCorrect(Number(e.target.value))} className="bg-[#121212] border-[#27272A] h-8 text-sm" min={0} max={total} />
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className={`text-sm font-bold ${accuracy >= 70 ? 'text-green-400' : accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{accuracy}% acerto</span>
          <Button onClick={handleLog} disabled={saving || !nbId} size="sm" className="bg-purple-600 hover:bg-purple-700">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><CheckCircle2 className="w-4 h-4 mr-1" /> Registrar</>}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ========== MAIN STUDIES PAGE ==========
export default function Studies() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("dashboard");

  // Data
  const [areas, setAreas] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [notebooks, setNotebooks] = useState([]);
  const [notes, setNotes] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [flashcards, setFlashcards] = useState([]);
  const [quizzes, setQuizzes] = useState([]);
  const [schedule, setSchedule] = useState([]);
  const [streak, setStreak] = useState({ current_streak: 0, best_streak: 0 });
  const [stats, setStats] = useState(null);
  const [questionStats, setQuestionStats] = useState(null);
  const [focusStats, setFocusStats] = useState(null);

  // Navigation
  const [selectedArea, setSelectedArea] = useState(null);
  const [selectedProgram, setSelectedProgram] = useState(null);
  const [selectedNotebook, setSelectedNotebook] = useState(null);

  // Dialogs
  const [showAreaDialog, setShowAreaDialog] = useState(false);
  const [showProgramDialog, setShowProgramDialog] = useState(false);
  const [showNotebookDialog, setShowNotebookDialog] = useState(false);
  const [showNoteDialog, setShowNoteDialog] = useState(false);
  const [showTaskDialog, setShowTaskDialog] = useState(false);
  const [showFlashcardDialog, setShowFlashcardDialog] = useState(false);
  const [showSessionDialog, setShowSessionDialog] = useState(false);
  const [showReviewDialog, setShowReviewDialog] = useState(false);
  const [showQuizDialog, setShowQuizDialog] = useState(false);
  const [currentFlashcard, setCurrentFlashcard] = useState(null);
  const [showAnswer, setShowAnswer] = useState(false);
  const [currentQuiz, setCurrentQuiz] = useState(null);
  const [quizAnswers, setQuizAnswers] = useState([]);
  const [quizResult, setQuizResult] = useState(null);

  // Simulados
  const [simulados, setSimulados] = useState([]);
  const [simuladoStats, setSimuladoStats] = useState(null);
  const [showImportPdfDialog, setShowImportPdfDialog] = useState(false);
  const [showGenerateDialog, setShowGenerateDialog] = useState(false);
  const [simuladoGenerating, setSimuladoGenerating] = useState(false);
  const [simuladoImporting, setSimuladoImporting] = useState(false);
  const [currentSimulado, setCurrentSimulado] = useState(null);
  const [simuladoMode, setSimuladoMode] = useState(null); // null, "taking", "results", "viewing"
  const [simuladoAnswers, setSimuladoAnswers] = useState({});
  const [simuladoCurrentQ, setSimuladoCurrentQ] = useState(0);
  const [simuladoMarked, setSimuladoMarked] = useState(new Set());
  const [simuladoTimer, setSimuladoTimer] = useState(0);
  const [simuladoTimerRunning, setSimuladoTimerRunning] = useState(false);
  const [simuladoResult, setSimuladoResult] = useState(null);
  const [simuladoSubmitting, setSimuladoSubmitting] = useState(false);
  const [showSimuladoStatsView, setShowSimuladoStatsView] = useState(false);
  const [showGabarito, setShowGabarito] = useState(false);
  const simuladoTimerRef = useRef(null);

  const [generateForm, setGenerateForm] = useState({
    title: "", banca: "", disciplina: "", concurso: "",
    question_type: "multipla_escolha", num_questions: 10, difficulty: "medio"
  });
  const [importForm, setImportForm] = useState({
    title: "Simulado Importado", banca: "", disciplina: "", concurso: "",
    question_type: "multipla_escolha"
  });
  const [importFile, setImportFile] = useState(null);

  // Edital Import
  const [showEditalDialog, setShowEditalDialog] = useState(false);
  const [editalFile, setEditalFile] = useState(null);
  const [editalImporting, setEditalImporting] = useState(false);
  const [editalForm, setEditalForm] = useState({ target_date: "", hours_per_day: 4, days_per_week: 5 });
  const [editalResult, setEditalResult] = useState(null);
  const [showEditalResultDialog, setShowEditalResultDialog] = useState(false);
  const [showCronogramaDialog, setShowCronogramaDialog] = useState(false);
  const [cronogramaData, setCronogramaData] = useState(null);
  const [cronogramaLoading, setCronogramaLoading] = useState(false);
  const [editalEditMode, setEditalEditMode] = useState(false);
  const [editedDisciplinas, setEditedDisciplinas] = useState([]);
  const [editedProgramName, setEditedProgramName] = useState("");
  const [savingDisciplinas, setSavingDisciplinas] = useState(false);
  const [studyIndicators, setStudyIndicators] = useState(null);
  const [indicatorsLoading, setIndicatorsLoading] = useState(false);
  const [showSimuladoFromEdital, setShowSimuladoFromEdital] = useState(false);
  const [editalSimuladoForm, setEditalSimuladoForm] = useState({
    title: "", disciplina: "", question_type: "multipla_escolha", num_questions: 10, difficulty: "medio"
  });
  const [editalSimuladoGenerating, setEditalSimuladoGenerating] = useState(false);

  // Multi-cargo edital
  const [editalAnalysis, setEditalAnalysis] = useState(null);
  const [editalAnalyzing, setEditalAnalyzing] = useState(false);
  const [showCargoSelection, setShowCargoSelection] = useState(false);
  const [selectedCargoIndex, setSelectedCargoIndex] = useState(0);
  const [creatingFromCargo, setCreatingFromCargo] = useState(false);

  // Mind maps
  const [showMindmapDialog, setShowMindmapDialog] = useState(false);
  const [mindmapGenerating, setMindmapGenerating] = useState(false);
  const [mindmapData, setMindmapData] = useState(null);
  const [mindmapTopic, setMindmapTopic] = useState("");
  const [mindmapFile, setMindmapFile] = useState(null);
  const [mindmaps, setMindmaps] = useState([]);
  const [showMindmapView, setShowMindmapView] = useState(false);
  const [viewingMindmap, setViewingMindmap] = useState(null);

  // Progress history
  const [progressHistory, setProgressHistory] = useState(null);
  const [showProgressDialog, setShowProgressDialog] = useState(false);
  const [progressLoading, setProgressLoading] = useState(false);

  // Cronograma export ref
  const cronogramaRef = useRef(null);

  // Edital Verticalizado
  const [showVerticalizadoDialog, setShowVerticalizadoDialog] = useState(false);
  const [verticalizadoData, setVerticalizadoData] = useState(null);
  const [verticalizadoLoading, setVerticalizadoLoading] = useState(false);
  const [expandedDisciplinas, setExpandedDisciplinas] = useState(new Set());

  // Motivational Quote (daily, resets at 5AM)
  const [motivationalQuote, setMotivationalQuote] = useState(null);
  const [overallStudyStats, setOverallStudyStats] = useState(null);

  // Redação
  const [redacaoFile, setRedacaoFile] = useState(null);
  const [redacaoCorrection, setRedacaoCorrection] = useState(null);
  const [redacaoLoading, setRedacaoLoading] = useState(false);
  const [redacaoHistory, setRedacaoHistory] = useState([]);
  const [showRedacaoResult, setShowRedacaoResult] = useState(false);
  const [randomTheme, setRandomTheme] = useState(null);
  const [themeLoading, setThemeLoading] = useState(false);

  // PDF Content Analysis
  const [showContentPdfDialog, setShowContentPdfDialog] = useState(false);
  const [contentPdfFile, setContentPdfFile] = useState(null);
  const [contentPdfAnalyzing, setContentPdfAnalyzing] = useState(false);
  const [contentPdfOptions, setContentPdfOptions] = useState({
    generate_notes: true, generate_flashcards: true, generate_quiz: true,
    num_flashcards: 10, num_quiz_questions: 5
  });
  const [contentPdfResult, setContentPdfResult] = useState(null);

  // Loading states
  const [generatingFlashcards, setGeneratingFlashcards] = useState(false);
  const [generatingQuiz, setGeneratingQuiz] = useState(false);

  // Topic progress tracking
  const [topicProgress, setTopicProgress] = useState({});

  // Forms
  const [areaForm, setAreaForm] = useState({ name: "", description: "", color: "#007AFF", icon: "book" });
  const [programForm, setProgramForm] = useState({ name: "", description: "", color: "#007AFF", icon: "book", target_date: "" });
  const [notebookForm, setNotebookForm] = useState({ name: "", description: "", color: "#007AFF", tags: [] });
  const [noteForm, setNoteForm] = useState({ title: "", content: "", tags: [], links: [] });
  const [taskForm, setTaskForm] = useState({ title: "", description: "", task_type: "reading", recurrence: "once", deadline: "", priority: "medium", estimated_minutes: 30 });
  const [flashcardForm, setFlashcardForm] = useState({ front: "", back: "", deck_name: "Geral" });
  const [sessionForm, setSessionForm] = useState({ duration_minutes: 30, notes: "" });
  const [newTag, setNewTag] = useState("");
  const [newLink, setNewLink] = useState({ title: "", url: "" });

  useEffect(() => { fetchUser(); }, []);
  useEffect(() => { if (user) fetchAllData(); }, [user]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (user && selectedNotebook) fetchNotebookData(); }, [user, selectedNotebook]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchUser = async () => {
    try {
      const res = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setUser(res.data);
    } catch { window.location.href = '/login'; }
  };

  const fetchAllData = async () => {
    setLoading(true);
    try {
      const [areasR, programsR, notebooksR, tasksR, streakR, statsR, qStatsR, fStatsR] = await Promise.all([
        axios.get(`${API}/study/areas`, { withCredentials: true }),
        axios.get(`${API}/study/programs`, { withCredentials: true }),
        axios.get(`${API}/study/notebooks`, { withCredentials: true }),
        axios.get(`${API}/study/tasks`, { withCredentials: true }),
        axios.get(`${API}/study/streak`, { withCredentials: true }),
        axios.get(`${API}/study/stats`, { withCredentials: true }),
        axios.get(`${API}/study/questions/stats`, { withCredentials: true }),
        axios.get(`${API}/study/focus/stats`, { withCredentials: true })
      ]);
      setAreas(Array.isArray(areasR.data) ? areasR.data : []);
      setPrograms(Array.isArray(programsR.data) ? programsR.data : []);
      setNotebooks(Array.isArray(notebooksR.data) ? notebooksR.data : []);
      setTasks(Array.isArray(tasksR.data) ? tasksR.data : []);
      setStreak(streakR.data || {});
      setStats(statsR.data || null);
      setQuestionStats(qStatsR.data || null);
      setFocusStats(fStatsR.data || null);
      // Fetch motivational quote (cached daily, resets at 5AM)
      try {
        const quoteR = await axios.get(`${API}/motivational-quote`, { withCredentials: true });
        setMotivationalQuote(quoteR.data || null);
      } catch (e) { console.error("Quote fetch failed:", e); }
      // Fetch overall study stats for charts
      try {
        const studyStatsR = await axios.get(`${API}/study/overall-stats`, { withCredentials: true });
        setOverallStudyStats(studyStatsR.data || null);
      } catch (e) { console.error("Study stats fetch failed:", e); }
    } catch (err) {
      console.error(err);
      toast.error("Erro ao carregar dados");
    } finally {
      setLoading(false);
    }
  };

  const fetchNotebookData = async () => {
    if (!selectedNotebook) return;
    try {
      const [notesR, flashR, quizR, schedR, topicR] = await Promise.all([
        axios.get(`${API}/study/notes?notebook_id=${selectedNotebook.notebook_id}`, { withCredentials: true }),
        axios.get(`${API}/study/flashcards?notebook_id=${selectedNotebook.notebook_id}`, { withCredentials: true }),
        axios.get(`${API}/study/quizzes?notebook_id=${selectedNotebook.notebook_id}`, { withCredentials: true }),
        axios.get(`${API}/study/schedule`, { withCredentials: true }),
        axios.get(`${API}/study/notebooks/${selectedNotebook.notebook_id}/topic-progress`, { withCredentials: true }).catch(() => ({ data: { topics: {} } }))
      ]);
      setNotes(Array.isArray(notesR.data) ? notesR.data : []);
      setFlashcards(Array.isArray(flashR.data) ? flashR.data : []);
      setQuizzes(Array.isArray(quizR.data) ? quizR.data : []);
      setSchedule((Array.isArray(schedR.data) ? schedR.data : []).filter(s => s.notebook_id === selectedNotebook.notebook_id));
      setTopicProgress(topicR.data?.topics || {});
    } catch (err) {
      console.error(err);
    }
  };

  // ========== TOPIC PROGRESS ==========
  const toggleTopicProgress = async (topicKey, status) => {
    if (!selectedNotebook) return;
    const currentVal = topicProgress?.[topicKey]?.[status];
    try {
      await axios.post(`${API}/study/notebooks/${selectedNotebook.notebook_id}/topic-progress`, {
        topic_key: topicKey, status, checked: !currentVal
      }, { withCredentials: true });
      setTopicProgress(prev => ({
        ...prev,
        [topicKey]: { ...(prev[topicKey] || {}), [status]: !currentVal }
      }));
    } catch { toast.error("Erro ao atualizar progresso"); }
  };

  // ========== SIMULADOS FUNCTIONS ==========
  const fetchSimulados = async () => {
    try {
      const [simR, statsR] = await Promise.all([
        axios.get(`${API}/study/simulados`, { withCredentials: true }),
        axios.get(`${API}/study/simulados/stats`, { withCredentials: true })
      ]);
      setSimulados(Array.isArray(simR.data) ? simR.data : []);
      setSimuladoStats(statsR.data || null);
    } catch (err) { console.error(err); }
  };

  useEffect(() => { if (user && activeTab === "simulados") fetchSimulados(); }, [user, activeTab]); // eslint-disable-line react-hooks/exhaustive-deps

  // Simulado timer
  useEffect(() => {
    if (simuladoTimerRunning) {
      simuladoTimerRef.current = setInterval(() => {
        setSimuladoTimer(prev => prev + 1);
      }, 1000);
    } else if (simuladoTimerRef.current) {
      clearInterval(simuladoTimerRef.current);
    }
    return () => { if (simuladoTimerRef.current) clearInterval(simuladoTimerRef.current); };
  }, [simuladoTimerRunning]);

  const formatTimer = (seconds) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return h > 0 ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}` : `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  };

  const handleImportPdf = async () => {
    if (!importFile) { toast.error("Selecione um arquivo PDF"); return; }
    setSimuladoImporting(true);
    try {
      const formData = new FormData();
      formData.append("file", importFile);
      formData.append("title", importForm.title || "Simulado Importado");
      if (importForm.banca) formData.append("banca", importForm.banca);
      if (importForm.disciplina) formData.append("disciplina", importForm.disciplina);
      if (importForm.concurso) formData.append("concurso", importForm.concurso);
      formData.append("question_type", importForm.question_type);
      if (selectedArea) formData.append("area_id", selectedArea.area_id);
      if (selectedProgram) formData.append("program_id", selectedProgram.program_id);

      const res = await axios.post(`${API}/study/simulados/import-pdf`, formData, {
        withCredentials: true, headers: { "Content-Type": "multipart/form-data" }, timeout: 120000
      });
      toast.success(res.data.message || "Simulado importado!");
      setShowImportPdfDialog(false);
      setImportFile(null);
      setImportForm({ title: "Simulado Importado", banca: "", disciplina: "", concurso: "", question_type: "multipla_escolha" });
      fetchSimulados();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao importar PDF");
    } finally { setSimuladoImporting(false); }
  };

  const handleGenerateSimulado = async () => {
    if (!generateForm.title) { toast.error("Digite o título do simulado"); return; }
    if (generateForm.num_questions < 1) { toast.error("Quantidade deve ser pelo menos 1"); return; }
    setSimuladoGenerating(true);
    try {
      const payload = { ...generateForm };
      if (selectedArea) payload.area_id = selectedArea.area_id;
      if (selectedProgram) payload.program_id = selectedProgram.program_id;
      const res = await axios.post(`${API}/study/simulados/generate`, payload, { withCredentials: true, timeout: 120000 });
      toast.success(res.data.message || "Simulado gerado!");
      setShowGenerateDialog(false);
      setGenerateForm({ title: "", banca: "", disciplina: "", concurso: "", question_type: "multipla_escolha", num_questions: 10, difficulty: "medio" });
      fetchSimulados();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao gerar simulado");
    } finally { setSimuladoGenerating(false); }
  };

  const handleStartSimulado = async (simulado) => {
    try {
      const res = await axios.get(`${API}/study/simulados/${simulado.simulado_id}`, { withCredentials: true });
      setCurrentSimulado(res.data);
      setSimuladoAnswers({});
      setSimuladoCurrentQ(0);
      setSimuladoMarked(new Set());
      setSimuladoTimer(0);
      setSimuladoTimerRunning(true);
      setSimuladoResult(null);
      setSimuladoMode("taking");
    } catch { toast.error("Erro ao carregar simulado"); }
  };

  const handleSubmitSimulado = async () => {
    if (!currentSimulado) return;
    setSimuladoSubmitting(true);
    setSimuladoTimerRunning(false);
    try {
      const answersArr = Object.entries(simuladoAnswers).map(([idx, ans]) => ({
        question_idx: parseInt(idx), selected_answer: ans
      }));
      const res = await axios.post(`${API}/study/simulados/${currentSimulado.simulado_id}/submit`, {
        answers: answersArr, time_spent_seconds: simuladoTimer
      }, { withCredentials: true });
      setSimuladoResult(res.data);
      setSimuladoMode("results");
      toast.success(`Simulado finalizado! Nota: ${res.data.score}% (+${res.data.xp_earned} XP)`);
      fetchSimulados();
      fetchAllData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao submeter simulado");
    } finally { setSimuladoSubmitting(false); }
  };

  const handleViewResults = async (simulado) => {
    try {
      const [simR, resultsR] = await Promise.all([
        axios.get(`${API}/study/simulados/${simulado.simulado_id}`, { withCredentials: true }),
        axios.get(`${API}/study/simulados/${simulado.simulado_id}/results`, { withCredentials: true })
      ]);
      setCurrentSimulado(simR.data);
      setSimuladoResult(resultsR.data?.[0] || null);
      setSimuladoMode("results");
    } catch { toast.error("Erro ao carregar resultados"); }
  };

  const handleViewSimulado = async (simulado) => {
    try {
      const res = await axios.get(`${API}/study/simulados/${simulado.simulado_id}`, { withCredentials: true });
      setCurrentSimulado(res.data);
      setSimuladoCurrentQ(0);
      setSimuladoMode("viewing");
    } catch { toast.error("Erro ao carregar simulado"); }
  };

  const handleDeleteSimulado = async (simuladoId) => {
    try {
      await axios.delete(`${API}/study/simulados/${simuladoId}`, { withCredentials: true });
      toast.success("Simulado excluído!"); fetchSimulados();
    } catch { toast.error("Erro ao excluir simulado"); }
  };

  const handleExitSimulado = () => {
    setSimuladoTimerRunning(false);
    setCurrentSimulado(null);
    setSimuladoMode(null);
    setSimuladoResult(null);
    setSimuladoAnswers({});
    setSimuladoCurrentQ(0);
    setSimuladoMarked(new Set());
    setSimuladoTimer(0);
    setShowGabarito(false);
  };

  const handleAnalyzeContentPdf = async () => {
    if (!contentPdfFile) { toast.error("Selecione um arquivo PDF"); return; }
    setContentPdfAnalyzing(true);
    setContentPdfResult(null);
    try {
      const formData = new FormData();
      formData.append("file", contentPdfFile);
      if (selectedNotebook) formData.append("notebook_id", selectedNotebook.notebook_id);
      formData.append("generate_notes", contentPdfOptions.generate_notes);
      formData.append("generate_flashcards", contentPdfOptions.generate_flashcards);
      formData.append("generate_quiz", contentPdfOptions.generate_quiz);
      formData.append("num_flashcards", contentPdfOptions.num_flashcards);
      formData.append("num_quiz_questions", contentPdfOptions.num_quiz_questions);

      const res = await axios.post(`${API}/study/content/analyze-pdf`, formData, {
        withCredentials: true, headers: { "Content-Type": "multipart/form-data" }, timeout: 120000
      });
      setContentPdfResult(res.data);
      toast.success(res.data.message || "Conteúdo analisado com sucesso!");
      fetchAllData();
      if (selectedNotebook) fetchNotebookData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao analisar PDF");
    } finally { setContentPdfAnalyzing(false); }
  };

  // CRUD Handlers
  const handleCreateArea = async () => {
    if (!areaForm.name) { toast.error("Digite o nome da área"); return; }
    try {
      await axios.post(`${API}/study/areas`, areaForm, { withCredentials: true });
      toast.success("Área criada!"); setShowAreaDialog(false); setAreaForm({ name: "", description: "", color: "#007AFF", icon: "book" }); fetchAllData();
    } catch { toast.error("Erro ao criar área"); }
  };

  const handleDeleteArea = async (areaId) => {
    try { await axios.delete(`${API}/study/areas/${areaId}`, { withCredentials: true }); toast.success("Área removida"); setSelectedArea(null); fetchAllData(); } catch { toast.error("Erro ao remover área"); }
  };

  const handleCreateProgram = async () => {
    if (!programForm.name || !selectedArea) { toast.error("Selecione área e digite o nome"); return; }
    try {
      await axios.post(`${API}/study/programs`, { ...programForm, area_id: selectedArea.area_id }, { withCredentials: true });
      toast.success("Programa criado!"); setShowProgramDialog(false); setProgramForm({ name: "", description: "", color: "#007AFF", icon: "book", target_date: "" }); fetchAllData();
    } catch { toast.error("Erro ao criar programa"); }
  };

  const handleDeleteProgram = async (programId) => {
    try { await axios.delete(`${API}/study/programs/${programId}`, { withCredentials: true }); toast.success("Programa removido"); setSelectedProgram(null); fetchAllData(); } catch { toast.error("Erro ao remover programa"); }
  };

  // ========== EDITAL IMPORT HANDLERS ==========
  const handleImportEdital = async () => {
    if (!editalFile) { toast.error("Selecione um arquivo PDF do edital"); return; }
    if (!selectedArea) { toast.error("Selecione uma área primeiro"); return; }
    setEditalImporting(true);
    try {
      const formData = new FormData();
      formData.append("file", editalFile);
      formData.append("area_id", selectedArea.area_id);
      if (editalForm.target_date) formData.append("target_date", editalForm.target_date);
      formData.append("hours_per_day", editalForm.hours_per_day.toString());
      formData.append("days_per_week", editalForm.days_per_week.toString());

      const res = await axios.post(`${API}/study/programs/import-edital`, formData, {
        withCredentials: true, headers: { "Content-Type": "multipart/form-data" }, timeout: 120000
      });
      toast.success(res.data.message || "Programa criado com sucesso!");
      setEditalResult(res.data);
      // Setup editable disciplines
      const discs = (res.data.disciplinas || []).map(d => ({
        ...d, user_difficulty: d.dificuldade || "media"
      }));
      setEditedDisciplinas(discs);
      setEditedProgramName(res.data.program?.name || "");
      setEditalEditMode(true);
      setShowEditalDialog(false);
      setShowEditalResultDialog(true);
      setEditalFile(null);
      setEditalForm({ target_date: "", hours_per_day: 4, days_per_week: 5 });
      fetchAllData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao importar edital");
    } finally { setEditalImporting(false); }
  };

  const handleSaveDisciplinas = async () => {
    if (!editalResult?.program?.program_id) return;
    setSavingDisciplinas(true);
    try {
      const payload = {
        program_name: editedProgramName,
        disciplinas: editedDisciplinas.map(d => ({
          notebook_id: d.notebook_id,
          weight: d.weight,
          dificuldade: d.dificuldade,
          user_difficulty: d.user_difficulty,
          name: d.name
        })),
        regenerate_schedule: true,
        hours_per_day: editalResult.program?.edital_data?.hours_per_day || 4,
        days_per_week: editalResult.program?.edital_data?.days_per_week || 5
      };
      const res = await axios.post(`${API}/study/programs/${editalResult.program.program_id}/update-disciplinas`, payload, { withCredentials: true });
      toast.success(res.data.message || "Disciplinas atualizadas!");
      setEditalEditMode(false);
      fetchAllData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao salvar alterações");
    } finally { setSavingDisciplinas(false); }
  };

  const handleViewCronograma = async (programId) => {
    setCronogramaLoading(true);
    setShowCronogramaDialog(true);
    setStudyIndicators(null);
    try {
      const [cronRes, indRes] = await Promise.all([
        axios.get(`${API}/study/programs/${programId}/cronograma`, { withCredentials: true }),
        axios.get(`${API}/study/programs/${programId}/study-indicators`, { withCredentials: true }).catch(() => ({ data: null }))
      ]);
      setCronogramaData(cronRes.data);
      setStudyIndicators(indRes.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao carregar cronograma");
      setShowCronogramaDialog(false);
    } finally { setCronogramaLoading(false); }
  };

  // ========== EDITAL VERTICALIZADO ==========
  const handleViewVerticalizado = async (programId) => {
    setVerticalizadoLoading(true);
    setShowVerticalizadoDialog(true);
    setExpandedDisciplinas(new Set());
    try {
      const res = await axios.get(`${API}/study/programs/${programId}/edital-verticalizado`, { withCredentials: true });
      setVerticalizadoData(res.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao carregar edital verticalizado");
      setShowVerticalizadoDialog(false);
    } finally { setVerticalizadoLoading(false); }
  };

  const toggleDisciplinaExpanded = (idx) => {
    setExpandedDisciplinas(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const handleGenerateSimuladoFromEdital = async () => {
    if (!editalSimuladoForm.title) { toast.error("Digite o título do simulado"); return; }
    setEditalSimuladoGenerating(true);
    try {
      const prog = cronogramaData?.program || editalResult?.program;
      const concurso = prog?.edital_data?.concurso;
      const payload = {
        title: editalSimuladoForm.title,
        banca: concurso?.banca || "",
        disciplina: editalSimuladoForm.disciplina || "",
        concurso: concurso?.nome || "",
        question_type: editalSimuladoForm.question_type,
        num_questions: editalSimuladoForm.num_questions,
        difficulty: editalSimuladoForm.difficulty,
        program_id: prog?.program_id
      };
      await axios.post(`${API}/study/simulados/generate`, payload, { withCredentials: true, timeout: 120000 });
      toast.success("Simulado gerado com sucesso!");
      setShowSimuladoFromEdital(false);
      setEditalSimuladoForm({ title: "", disciplina: "", question_type: "multipla_escolha", num_questions: 10, difficulty: "medio" });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao gerar simulado");
    } finally { setEditalSimuladoGenerating(false); }
  };

  // ========== MULTI-CARGO EDITAL IMPORT ==========
  const handleAnalyzeEdital = async () => {
    if (!editalFile) { toast.error("Selecione um arquivo PDF do edital"); return; }
    if (!selectedArea) { toast.error("Selecione uma área primeiro"); return; }
    setEditalAnalyzing(true);
    try {
      const formData = new FormData();
      formData.append("file", editalFile);

      const res = await axios.post(`${API}/study/programs/analyze-edital`, formData, {
        withCredentials: true, headers: { "Content-Type": "multipart/form-data" }, timeout: 120000
      });
      setEditalAnalysis(res.data);
      
      if (res.data.multiple_cargos && res.data.cargos?.length > 1) {
        // Multiple cargos - show selection
        setShowEditalDialog(false);
        setShowCargoSelection(true);
        toast.success(`${res.data.cargos.length} cargos encontrados! Selecione o seu.`);
      } else {
        // Single cargo - proceed directly
        await handleCreateFromCargo(res.data.analysis_id, 0);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao analisar edital");
    } finally { setEditalAnalyzing(false); }
  };

  const handleCreateFromCargo = async (analysisId, cargoIdx) => {
    setCreatingFromCargo(true);
    try {
      const res = await axios.post(`${API}/study/programs/import-edital-with-cargo`, {
        analysis_id: analysisId || editalAnalysis?.analysis_id,
        cargo_index: cargoIdx,
        area_id: selectedArea.area_id,
        target_date: editalForm.target_date || null,
        hours_per_day: editalForm.hours_per_day,
        days_per_week: editalForm.days_per_week
      }, { withCredentials: true, timeout: 120000 });
      
      toast.success(res.data.message || "Programa criado com sucesso!");
      setEditalResult(res.data);
      const discs = (res.data.disciplinas || []).map(d => ({ ...d, user_difficulty: d.dificuldade || "media" }));
      setEditedDisciplinas(discs);
      setEditedProgramName(res.data.program?.name || "");
      setEditalEditMode(true);
      setShowCargoSelection(false);
      setShowEditalDialog(false);
      setShowEditalResultDialog(true);
      setEditalFile(null);
      setEditalForm({ target_date: "", hours_per_day: 4, days_per_week: 5 });
      setEditalAnalysis(null);
      fetchAllData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao criar programa");
    } finally { setCreatingFromCargo(false); }
  };

  // ========== MIND MAP HANDLERS ==========
  const handleGenerateMindmap = async () => {
    setMindmapGenerating(true);
    try {
      let res;
      if (mindmapFile) {
        const formData = new FormData();
        formData.append("file", mindmapFile);
        if (mindmapTopic) formData.append("topic", mindmapTopic);
        if (selectedNotebook) formData.append("notebook_id", selectedNotebook.notebook_id);
        res = await axios.post(`${API}/study/mindmap/generate`, formData, {
          withCredentials: true, headers: { "Content-Type": "multipart/form-data" }, timeout: 120000
        });
      } else {
        const formData = new FormData();
        if (mindmapTopic) formData.append("topic", mindmapTopic);
        if (selectedNotebook) formData.append("notebook_id", selectedNotebook.notebook_id);
        res = await axios.post(`${API}/study/mindmap/generate`, formData, {
          withCredentials: true, headers: { "Content-Type": "multipart/form-data" }, timeout: 120000
        });
      }
      setMindmapData(res.data.mindmap);
      setViewingMindmap(res.data.mindmap);
      setShowMindmapDialog(false);
      setShowMindmapView(true);
      toast.success("Mapa mental gerado!");
      setMindmapTopic("");
      setMindmapFile(null);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao gerar mapa mental");
    } finally { setMindmapGenerating(false); }
  };

  // ========== PROGRESS HISTORY ==========
  const handleViewProgress = async (programId) => {
    setProgressLoading(true);
    setShowProgressDialog(true);
    try {
      const res = await axios.get(`${API}/study/programs/${programId}/progress-history?days=30`, { withCredentials: true });
      setProgressHistory(res.data);
    } catch (err) {
      toast.error("Erro ao carregar progresso");
      setShowProgressDialog(false);
    } finally { setProgressLoading(false); }
  };

  // ========== EXPORT CRONOGRAMA AS PDF ==========
  const handleExportCronograma = async (format = 'pdf') => {
    try {
      const element = cronogramaRef.current;
      if (!element) { toast.error("Erro ao capturar cronograma"); return; }
      
      toast.info("Gerando exportação...");
      const canvas = await html2canvas(element, {
        backgroundColor: '#0A0A0A',
        scale: 2,
        useCORS: true
      });
      
      if (format === 'image') {
        const link = document.createElement('a');
        link.download = `cronograma_${cronogramaData?.program?.name || 'estudo'}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
        toast.success("Imagem exportada!");
      } else {
        const imgData = canvas.toDataURL('image/png');
        const imgWidth = 210; // A4 width in mm
        const imgHeight = (canvas.height * imgWidth) / canvas.width;
        const pdf = new jsPDF('p', 'mm', 'a4');
        
        let position = 0;
        const pageHeight = 297; // A4 height
        
        while (position < imgHeight) {
          if (position > 0) pdf.addPage();
          pdf.addImage(imgData, 'PNG', 0, -position, imgWidth, imgHeight);
          position += pageHeight;
        }
        
        pdf.save(`cronograma_${cronogramaData?.program?.name || 'estudo'}.pdf`);
        toast.success("PDF exportado!");
      }
    } catch (err) {
      console.error(err);
      toast.error("Erro ao exportar");
    }
  };

  // ========== SCHEDULE REMINDERS ==========
  const handleCreateReminders = async (programId) => {
    try {
      const res = await axios.post(`${API}/study/programs/${programId}/create-reminders`, {
        minutes_before: 5
      }, { withCredentials: true });
      toast.success(res.data.message || "Lembretes criados!");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao criar lembretes");
    }
  };


  // ========== REDAÇÃO HANDLERS ==========
  const handleRedacaoCorrection = async () => {
    if (!redacaoFile) { toast.error("Selecione um arquivo"); return; }
    setRedacaoLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", redacaoFile);
      const res = await axios.post(`${API}/study/redacao/correct`, formData, {
        withCredentials: true, headers: { "Content-Type": "multipart/form-data" }, timeout: 120000
      });
      setRedacaoCorrection(res.data.correction);
      setShowRedacaoResult(true);
      setRedacaoFile(null);
      toast.success("Redação corrigida!");
      fetchRedacaoHistory();
    } catch (err) { toast.error(err.response?.data?.detail || "Erro ao corrigir redação"); }
    finally { setRedacaoLoading(false); }
  };

  const fetchRedacaoHistory = async () => {
    try {
      const res = await axios.get(`${API}/study/redacao/history`, { withCredentials: true });
      setRedacaoHistory(Array.isArray(res.data) ? res.data : []);
    } catch {}
  };

  const handleRandomTheme = async () => {
    setThemeLoading(true);
    try {
      const res = await axios.post(`${API}/study/redacao/random-theme`, {}, { withCredentials: true });
      setRandomTheme(res.data.theme);
    } catch { toast.error("Erro ao sortear tema"); }
    finally { setThemeLoading(false); }
  };


  const handleCreateNotebook = async () => {
    if (!notebookForm.name) { toast.error("Digite o nome"); return; }
    const areaId = selectedArea?.area_id || areas[0]?.area_id;
    if (!areaId) { toast.error("Crie uma área primeiro"); return; }
    try {
      await axios.post(`${API}/study/notebooks`, {
        ...notebookForm, area_id: areaId, program_id: selectedProgram?.program_id || null
      }, { withCredentials: true });
      toast.success("Matéria criada!"); setShowNotebookDialog(false); setNotebookForm({ name: "", description: "", color: "#007AFF", tags: [] }); fetchAllData();
    } catch { toast.error("Erro ao criar matéria"); }
  };

  const handleDeleteNotebook = async (notebookId) => {
    try { await axios.delete(`${API}/study/notebooks/${notebookId}`, { withCredentials: true }); toast.success("Matéria removida"); setSelectedNotebook(null); fetchAllData(); } catch { toast.error("Erro ao remover"); }
  };

  const handleCreateNote = async () => {
    if (!noteForm.title || !selectedNotebook) { toast.error("Preencha o título"); return; }
    try {
      await axios.post(`${API}/study/notes`, { ...noteForm, notebook_id: selectedNotebook.notebook_id }, { withCredentials: true });
      toast.success("Nota criada!"); setShowNoteDialog(false); setNoteForm({ title: "", content: "", tags: [], links: [] }); fetchNotebookData();
    } catch { toast.error("Erro ao criar nota"); }
  };

  const handleDeleteNote = async (noteId) => {
    try { await axios.delete(`${API}/study/notes/${noteId}`, { withCredentials: true }); toast.success("Nota removida"); fetchNotebookData(); } catch { toast.error("Erro ao remover"); }
  };

  const handleCreateTask = async () => {
    if (!taskForm.title) { toast.error("Digite o título"); return; }
    try {
      await axios.post(`${API}/study/tasks`, { ...taskForm, notebook_id: selectedNotebook?.notebook_id || null }, { withCredentials: true });
      toast.success("Tarefa criada!"); setShowTaskDialog(false); setTaskForm({ title: "", description: "", task_type: "reading", recurrence: "once", deadline: "", priority: "medium", estimated_minutes: 30 }); fetchAllData();
    } catch { toast.error("Erro ao criar tarefa"); }
  };

  const handleToggleTask = async (taskId, completed) => {
    try { await axios.patch(`${API}/study/tasks/${taskId}`, { completed }, { withCredentials: true }); toast.success(completed ? "Tarefa concluída! +XP" : "Tarefa desmarcada"); fetchAllData(); } catch { toast.error("Erro"); }
  };

  const handleDeleteTask = async (taskId) => {
    try { await axios.delete(`${API}/study/tasks/${taskId}`, { withCredentials: true }); toast.success("Removida"); fetchAllData(); } catch { toast.error("Erro"); }
  };

  const handleCreateFlashcard = async () => {
    if (!flashcardForm.front || !flashcardForm.back || !selectedNotebook) { toast.error("Preencha frente e verso"); return; }
    try {
      await axios.post(`${API}/study/flashcards`, { ...flashcardForm, notebook_id: selectedNotebook.notebook_id }, { withCredentials: true });
      toast.success("Flashcard criado!"); setShowFlashcardDialog(false); setFlashcardForm({ front: "", back: "", deck_name: "Geral" }); fetchNotebookData();
    } catch { toast.error("Erro"); }
  };

  const handleGenerateFlashcards = async (noteId) => {
    setGeneratingFlashcards(true);
    try {
      const res = await axios.post(`${API}/study/flashcards/generate`, { note_id: noteId, count: 5 }, { withCredentials: true });
      toast.success(`${res.data.flashcards?.length || 0} flashcards gerados!`); fetchNotebookData();
    } catch { toast.error("Erro ao gerar flashcards"); } finally { setGeneratingFlashcards(false); }
  };

  const handleReviewFlashcard = async (quality) => {
    if (!currentFlashcard) return;
    try {
      await axios.post(`${API}/study/flashcards/${currentFlashcard.flashcard_id}/review`, { quality }, { withCredentials: true });
      const dueCards = flashcards.filter(f => f.next_review <= new Date().toISOString().split('T')[0]);
      const idx = dueCards.findIndex(f => f.flashcard_id === currentFlashcard.flashcard_id);
      if (idx < dueCards.length - 1) { setCurrentFlashcard(dueCards[idx + 1]); setShowAnswer(false); }
      else { setCurrentFlashcard(null); setShowReviewDialog(false); toast.success("Revisão concluída!"); }
      fetchNotebookData();
    } catch { toast.error("Erro"); }
  };

  const handleLogSession = async () => {
    if (!selectedNotebook) { toast.error("Selecione um caderno"); return; }
    try {
      await axios.post(`${API}/study/sessions`, { ...sessionForm, notebook_id: selectedNotebook.notebook_id, date: new Date().toISOString().split('T')[0] }, { withCredentials: true });
      toast.success("Sessão registrada! +XP"); setShowSessionDialog(false); setSessionForm({ duration_minutes: 30, notes: "" }); fetchAllData();
    } catch { toast.error("Erro"); }
  };

  const handleGenerateQuiz = async () => {
    if (!selectedNotebook) { toast.error("Selecione um caderno"); return; }
    setGeneratingQuiz(true);
    try {
      await axios.post(`${API}/study/quizzes/generate`, { notebook_id: selectedNotebook.notebook_id, count: 5 }, { withCredentials: true });
      toast.success("Quiz gerado!"); fetchNotebookData();
    } catch { toast.error("Erro. Adicione notas primeiro."); } finally { setGeneratingQuiz(false); }
  };

  const startQuiz = (quiz) => { setCurrentQuiz(quiz); setQuizAnswers([]); setQuizResult(null); setShowQuizDialog(true); };

  const handleQuizAnswer = (qIdx, answer) => {
    setQuizAnswers(prev => {
      const existing = prev.find(a => a.question_idx === qIdx);
      if (existing) return prev.map(a => a.question_idx === qIdx ? { ...a, selected_answer: answer } : a);
      return [...prev, { question_idx: qIdx, selected_answer: answer }];
    });
  };

  const submitQuiz = async () => {
    if (!currentQuiz) return;
    try {
      const res = await axios.post(`${API}/study/quizzes/${currentQuiz.quiz_id}/attempt`, { answers: quizAnswers }, { withCredentials: true });
      setQuizResult(res.data); toast.success(`Quiz finalizado! ${(res.data.score ?? 0).toFixed(0)}%`); fetchAllData();
    } catch { toast.error("Erro"); }
  };

  const startReview = () => {
    const dueCards = flashcards.filter(f => f.next_review <= new Date().toISOString().split('T')[0]);
    if (dueCards.length === 0) { toast.info("Nenhum cartão para revisar hoje!"); return; }
    setCurrentFlashcard(dueCards[0]); setShowAnswer(false); setShowReviewDialog(true);
  };

  const addTag = (setter, tags) => { if (newTag && !tags.includes(newTag)) { setter(prev => ({ ...prev, tags: [...prev.tags, newTag] })); setNewTag(""); } };
  const removeTag = (setter, tag) => { setter(prev => ({ ...prev, tags: prev.tags.filter(t => t !== tag) })); };
  const addLink = () => { if (newLink.title && newLink.url) { setNoteForm(prev => ({ ...prev, links: [...prev.links, { ...newLink }] })); setNewLink({ title: "", url: "" }); } };

  // Navigate into program
  const navigateToProgram = (program) => {
    setSelectedProgram(program);
    setSelectedNotebook(null);
    setActiveTab("materias");
  };

  // Navigate into notebook
  const navigateToNotebook = (notebook) => {
    setSelectedNotebook(notebook);
    setActiveTab("conteudo");
  };

  if (loading && !user) {
    return <div className="min-h-screen bg-[#050505] flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-[#007AFF]" /></div>;
  }

  const dueFlashcardsCount = flashcards.filter(f => f.next_review <= new Date().toISOString().split('T')[0]).length;
  const pendingTasksCount = tasks.filter(t => !t.completed && !t.completed_today).length;
  const totalQuestions = questionStats?.total_questions || 0;
  const accuracy = questionStats?.accuracy || 0;
  const focusToday = focusStats?.today?.total_minutes || 0;

  // Filtered data
  const areaPrograms = selectedArea ? programs.filter(p => p.area_id === selectedArea.area_id) : [];
  const programNotebooks = selectedProgram ? notebooks.filter(n => n.program_id === selectedProgram.program_id) : [];
  const areaNotebooksNoProgram = selectedArea ? notebooks.filter(n => n.area_id === selectedArea.area_id && !n.program_id) : [];

  return (
    <div className="min-h-screen bg-[#050505] text-white flex">
      <Sidebar user={user} />
      <main className="flex-1 md:ml-64 p-3 md:p-6 pb-24 md:pb-8 pt-[72px] md:pt-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-3">
          <div>
            <h1 className="text-2xl md:text-3xl font-heading text-[#00F0FF]">Área de Estudos</h1>
            <p className="text-[#A1A1AA] text-sm">Organize, estude e evolua com inteligência</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <ExportButtons module="study" />
            <Badge className="bg-orange-500/20 text-orange-400"><Flame className="w-3 h-3 mr-1" />{streak.current_streak || 0} dias</Badge>
            <Badge className="bg-purple-500/20 text-purple-400"><Trophy className="w-3 h-3 mr-1" />Recorde: {streak.best_streak || 0}</Badge>
            <Badge className="bg-blue-500/20 text-blue-400"><Hash className="w-3 h-3 mr-1" />{totalQuestions} questões</Badge>
          </div>
        </div>

        {/* Motivational Quote - Daily, resets at 5AM */}
        {motivationalQuote && motivationalQuote.quote && (
          <Card className="bg-gradient-to-r from-[#0A0A0A] to-[#1a1a2e] border-[#27272A] p-4 mb-4">
            <div className="flex items-center gap-3">
              <Sparkles className="w-5 h-5 text-[#00F0FF] flex-shrink-0" />
              <p className="text-sm md:text-base italic text-white flex-1">{motivationalQuote.quote}</p>
            </div>
          </Card>
        )}

        {/* Breadcrumb */}
        {(selectedArea || selectedProgram || selectedNotebook) && (
          <div className="flex items-center gap-1 mb-4 text-sm flex-wrap">
            <Button variant="link" className="text-[#A1A1AA] p-0 h-auto" onClick={() => { setSelectedArea(null); setSelectedProgram(null); setSelectedNotebook(null); setActiveTab("dashboard"); }}>
              Início
            </Button>
            {selectedArea && (
              <>
                <ChevronRight className="w-3 h-3 text-[#A1A1AA]" />
                <Button variant="link" className="text-[#A1A1AA] p-0 h-auto" onClick={() => { setSelectedProgram(null); setSelectedNotebook(null); setActiveTab("programas"); }}>
                  {selectedArea.name}
                </Button>
              </>
            )}
            {selectedProgram && (
              <>
                <ChevronRight className="w-3 h-3 text-[#A1A1AA]" />
                <Button variant="link" className="text-[#A1A1AA] p-0 h-auto" onClick={() => { setSelectedNotebook(null); setActiveTab("materias"); }}>
                  {selectedProgram.name}
                </Button>
              </>
            )}
            {selectedNotebook && (
              <>
                <ChevronRight className="w-3 h-3 text-[#A1A1AA]" />
                <span className="text-white font-medium">{selectedNotebook.name}</span>
              </>
            )}
          </div>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="bg-[#121212] border border-[#27272A] overflow-x-auto flex-nowrap w-full justify-start gap-0">
            <TabsTrigger value="dashboard" className="text-xs md:text-sm">Dashboard</TabsTrigger>
            <TabsTrigger value="programas" className="text-xs md:text-sm">Programas</TabsTrigger>
            <TabsTrigger value="materias" className="text-xs md:text-sm">Matérias</TabsTrigger>
            <TabsTrigger value="conteudo" className="text-xs md:text-sm">Conteúdo</TabsTrigger>
            <TabsTrigger value="tarefas" className="text-xs md:text-sm">Tarefas</TabsTrigger>
            <TabsTrigger value="simulados" className="text-xs md:text-sm">Simulados</TabsTrigger>
            <TabsTrigger value="redacao" className="text-xs md:text-sm">Redação</TabsTrigger>
            <TabsTrigger value="foco" className="text-xs md:text-sm">Foco</TabsTrigger>
          </TabsList>

          {/* ========== DASHBOARD TAB ========== */}
          <TabsContent value="dashboard" className="space-y-4">
            {/* ===== UNIFIED STUDY DASHBOARD ===== */}
            <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
              {[
                { 
                  label: "Tempo Total", 
                  value: stats?.total_study_time_hours || overallStudyStats?.totals?.tempo_total_horas || 0, 
                  unit: "h", 
                  icon: <Clock className="w-5 h-5" />,
                  color: "from-cyan-600 to-cyan-400",
                  bgColor: "bg-cyan-500/10",
                  textColor: "text-cyan-400"
                },
                { 
                  label: "Questões", 
                  value: totalQuestions || overallStudyStats?.totals?.questoes_total || 0, 
                  unit: "", 
                  sub: `${accuracy || overallStudyStats?.totals?.acuracia_geral || 0}% acerto`,
                  icon: <Target className="w-5 h-5" />,
                  color: "from-purple-600 to-purple-400",
                  bgColor: "bg-purple-500/10",
                  textColor: "text-purple-400"
                },
                { 
                  label: "Acurácia Geral", 
                  value: accuracy || overallStudyStats?.totals?.acuracia_geral || 0, 
                  unit: "%", 
                  icon: <TrendingUp className="w-5 h-5" />,
                  color: "from-green-600 to-green-400",
                  bgColor: "bg-green-500/10",
                  textColor: (accuracy || overallStudyStats?.totals?.acuracia_geral || 0) >= 70 ? "text-green-400" : (accuracy || overallStudyStats?.totals?.acuracia_geral || 0) >= 50 ? "text-yellow-400" : "text-red-400"
                },
                { 
                  label: "Foco Hoje", 
                  value: focusToday || 0, 
                  unit: "min", 
                  icon: <Timer className="w-5 h-5" />,
                  color: "from-red-600 to-red-400",
                  bgColor: "bg-red-500/10",
                  textColor: "text-red-400"
                },
                { 
                  label: "Flashcards", 
                  value: stats?.flashcards?.due_today || 0, 
                  unit: "", 
                  sub: "p/ revisar",
                  icon: <Brain className="w-5 h-5" />,
                  color: "from-yellow-600 to-yellow-400",
                  bgColor: "bg-yellow-500/10",
                  textColor: "text-yellow-400"
                },
                { 
                  label: "Disciplinas", 
                  value: overallStudyStats?.totals?.disciplinas_ativas || 0, 
                  unit: "", 
                  sub: "ativas",
                  icon: <BookOpen className="w-5 h-5" />,
                  color: "from-blue-600 to-blue-400",
                  bgColor: "bg-blue-500/10",
                  textColor: "text-blue-400"
                }
              ].map((stat, idx) => (
                <Card key={idx} className="bg-[#0A0A0A] border-[#27272A] p-3 relative overflow-hidden group hover:border-[#3F3F46] transition-colors">
                  <div className={`absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r ${stat.color}`} />
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-[9px] uppercase tracking-wider text-[#71717A] mb-0.5">{stat.label}</p>
                      <p className={`text-xl md:text-2xl font-bold ${stat.textColor} font-data`}>
                        {stat.value}{stat.unit}
                      </p>
                      {stat.sub && <p className="text-[10px] text-[#52525B]">{stat.sub}</p>}
                    </div>
                    <div className={`${stat.bgColor} p-1.5 rounded-lg ${stat.textColor}`}>
                      {stat.icon}
                    </div>
                  </div>
                </Card>
              ))}
            </div>

            {/* Charts Grid */}
            {overallStudyStats && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
                {/* Focus Sessions Trend */}
                {overallStudyStats.focus_daily && overallStudyStats.focus_daily.some(d => d.minutos > 0) && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2"><Timer className="w-4 h-4 text-red-400" />Sessões de Foco (7 dias)</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={180}>
                        <BarChart data={overallStudyStats.focus_daily}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                          <XAxis dataKey="day" tick={{ fill: '#71717A', fontSize: 11 }} />
                          <YAxis tick={{ fill: '#71717A', fontSize: 10 }} unit="min" />
                          <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A', color: '#fff', fontSize: 11 }} formatter={(v) => `${v} min`} />
                          <Bar dataKey="minutos" fill="#EF4444" name="Minutos" radius={[3, 3, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}

                {/* Question Accuracy Trend */}
                {overallStudyStats.question_daily && overallStudyStats.question_daily.some(d => d.questoes > 0) && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2"><BarChart3 className="w-4 h-4 text-purple-400" />Questões (7 dias)</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={180}>
                        <LineChart data={overallStudyStats.question_daily}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                          <XAxis dataKey="day" tick={{ fill: '#71717A', fontSize: 11 }} />
                          <YAxis tick={{ fill: '#71717A', fontSize: 10 }} />
                          <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A', color: '#fff', fontSize: 11 }} />
                          <Line type="monotone" dataKey="questoes" stroke="#A855F7" strokeWidth={2} name="Questões" dot={{ r: 3 }} />
                          <Line type="monotone" dataKey="acertos" stroke="#39FF14" strokeWidth={2} name="Acertos" dot={{ r: 3 }} />
                          <Legend />
                        </LineChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}

                {/* Discipline Distribution - Donut Chart */}
                {overallStudyStats.disciplinas && overallStudyStats.disciplinas.length > 0 && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2"><BookOpen className="w-4 h-4 text-blue-400" />Distribuição por Disciplina</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={200}>
                        <PieChart>
                          <Pie
                            data={overallStudyStats.disciplinas.slice(0, 6).map((d, i) => ({
                              name: d.nome?.length > 15 ? d.nome.substring(0, 15) + '...' : d.nome,
                              value: d.tempo_horas || 1
                            }))}
                            cx="50%" cy="50%"
                            innerRadius={50} outerRadius={75}
                            paddingAngle={3}
                            dataKey="value"
                          >
                            {overallStudyStats.disciplinas.slice(0, 6).map((_, i) => (
                              <Cell key={i} fill={['#007AFF', '#A855F7', '#39FF14', '#00F0FF', '#FF6B6B', '#FFD700'][i]} />
                            ))}
                          </Pie>
                          <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A', color: '#fff', fontSize: 11 }} formatter={(v) => `${v}h`} />
                          <Legend wrapperStyle={{ fontSize: 10 }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}

                {/* Radar Chart - Performance */}
                {overallStudyStats.disciplinas && overallStudyStats.disciplinas.length > 2 && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2"><TrendingUp className="w-4 h-4 text-green-400" />Desempenho por Disciplina</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={200}>
                        <RadarChart data={overallStudyStats.disciplinas.slice(0, 6).map(d => ({
                          nome: d.nome?.length > 10 ? d.nome.substring(0, 10) + '...' : d.nome,
                          horas: d.tempo_horas || 0,
                          questoes: Math.min(d.questoes || 0, 100),
                          acuracia: d.acuracia || 0
                        }))}>
                          <PolarGrid stroke="#27272A" />
                          <PolarAngleAxis dataKey="nome" tick={{ fill: '#71717A', fontSize: 9 }} />
                          <PolarRadiusAxis tick={{ fill: '#52525B', fontSize: 8 }} />
                          <Radar name="Horas" dataKey="horas" stroke="#007AFF" fill="#007AFF" fillOpacity={0.2} />
                          <Radar name="Acurácia" dataKey="acuracia" stroke="#39FF14" fill="#39FF14" fillOpacity={0.15} />
                          <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A', color: '#fff', fontSize: 11 }} />
                          <Legend wrapperStyle={{ fontSize: 10 }} />
                        </RadarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}
              </div>
            )}

            {/* Areas Grid */}
            <Card className="bg-[#0A0A0A] border-[#27272A]">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2"><Layers className="w-4 h-4 text-[#007AFF]" />Áreas de Estudo</CardTitle>
                  <Dialog open={showAreaDialog} onOpenChange={setShowAreaDialog}>
                    <DialogTrigger asChild><Button size="sm" className="bg-[#007AFF] h-8 text-xs"><Plus className="w-3 h-3 mr-1" />Nova Área</Button></DialogTrigger>
                    <DialogContent className="bg-[#0A0A0A] border-[#27272A]">
                      <DialogHeader><DialogTitle>Nova Área de Estudo</DialogTitle></DialogHeader>
                      <div className="space-y-4 py-4">
                        <div><Label>Nome</Label><Input value={areaForm.name} onChange={e => setAreaForm({...areaForm, name: e.target.value})} placeholder="Ex: Faculdade" className="bg-[#121212] border-[#27272A]" /></div>
                        <div><Label>Descrição</Label><Input value={areaForm.description} onChange={e => setAreaForm({...areaForm, description: e.target.value})} placeholder="Opcional" className="bg-[#121212] border-[#27272A]" /></div>
                        <div><Label>Cor</Label><Input type="color" value={areaForm.color} onChange={e => setAreaForm({...areaForm, color: e.target.value})} className="bg-[#121212] border-[#27272A] h-10" /></div>
                        <Button onClick={handleCreateArea} className="w-full bg-[#007AFF]">Criar Área</Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {areas.map(area => {
                    const AreaIcon = areaIcons[area.icon] || Folder;
                    const areaProgs = programs.filter(p => p.area_id === area.area_id);
                    const areaNbs = notebooks.filter(n => n.area_id === area.area_id);
                    return (
                      <div key={area.area_id} onClick={() => { setSelectedArea(area); setSelectedProgram(null); setSelectedNotebook(null); setActiveTab("programas"); }}
                        className="p-4 rounded-lg cursor-pointer transition-all hover:scale-[1.02] hover:bg-[#121212] group"
                        style={{ backgroundColor: `${area.color}10`, borderLeft: `3px solid ${area.color}` }}>
                        <AreaIcon className="w-7 h-7 mb-2" style={{ color: area.color }} />
                        <h4 className="font-medium text-sm">{area.name}</h4>
                        <p className="text-xs text-[#A1A1AA]">{areaProgs.length} programas · {areaNbs.length} matérias</p>
                        <ChevronRight className="w-4 h-4 text-[#A1A1AA] mt-2 group-hover:translate-x-1 transition-transform" />
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Quick Actions + AI Chat */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="space-y-4">
                <QuestionLogger notebooks={notebooks} onLog={fetchAllData} />
                <PomodoroTimer notebooks={notebooks} onComplete={fetchAllData} />
              </div>
              <StudyAIChat notebooks={notebooks} selectedNotebook={selectedNotebook} />
            </div>

            {/* Tasks Summary */}
            {pendingTasksCount > 0 && (
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2"><Target className="w-4 h-4 text-red-400" />Tarefas Pendentes ({pendingTasksCount})</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {tasks.filter(t => !t.completed && !t.completed_today).slice(0, 5).map(task => (
                      <div key={task.task_id} className="flex items-center justify-between bg-[#121212] p-3 rounded-lg">
                        <div className="flex items-center gap-3">
                          <button onClick={() => handleToggleTask(task.task_id, true)} className="w-5 h-5 rounded border-2 border-[#27272A] hover:border-green-500 shrink-0" />
                          <div>
                            <p className="text-sm font-medium">{task.title}</p>
                            <div className="flex gap-1 mt-1">
                              <Badge variant="outline" className="text-[10px] h-5">{taskTypeLabels[task.task_type]}</Badge>
                              {task.deadline && <Badge variant="outline" className="text-[10px] h-5 border-purple-500 text-purple-400">{task.deadline}</Badge>}
                            </div>
                          </div>
                        </div>
                        <Badge className={`text-[10px] ${task.priority === 'high' ? 'bg-red-500/20 text-red-400' : task.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-green-500/20 text-green-400'}`}>{task.priority}</Badge>
                      </div>
                    ))}
                    {pendingTasksCount > 5 && (
                      <Button variant="link" onClick={() => setActiveTab("tarefas")} className="text-[#007AFF] text-xs">Ver todas ({pendingTasksCount})</Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ========== PROGRAMAS TAB ========== */}
          <TabsContent value="programas" className="space-y-4">
            {/* Area selector */}
            <div className="flex flex-wrap gap-2 mb-2">
              {areas.map(area => (
                <Button key={area.area_id} variant={selectedArea?.area_id === area.area_id ? "default" : "outline"} size="sm"
                  onClick={() => { setSelectedArea(area); setSelectedProgram(null); setSelectedNotebook(null); }}
                  style={{ backgroundColor: selectedArea?.area_id === area.area_id ? area.color : 'transparent', borderColor: area.color }}
                  className="text-xs h-8">{area.name}</Button>
              ))}
            </div>

            {selectedArea ? (
              <>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                  <div>
                    <h2 className="text-lg font-bold">{selectedArea.name}</h2>
                    <p className="text-xs text-[#A1A1AA]">{selectedArea.description || 'Programas e cursos desta área'}</p>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <Dialog open={showEditalDialog} onOpenChange={setShowEditalDialog}>
                      <DialogTrigger asChild><Button size="sm" className="bg-purple-600 hover:bg-purple-700 h-8 text-xs"><FileUp className="w-3 h-3 mr-1" />Importar Edital</Button></DialogTrigger>
                      <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-lg">
                        <DialogHeader>
                          <DialogTitle className="flex items-center gap-2"><FileUp className="w-5 h-5 text-purple-400" />Importar Edital de Concurso</DialogTitle>
                          <DialogDescription>Faça upload do PDF do edital e a IA criará um programa de estudos completo com disciplinas, pesos e cronograma.</DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                          <div>
                            <Label className="text-sm font-medium">PDF do Edital *</Label>
                            <div className={`mt-1 border-2 border-dashed rounded-lg p-6 text-center transition-colors ${editalFile ? 'border-purple-500 bg-purple-500/10' : 'border-[#27272A] hover:border-[#3F3F46]'}`}>
                              {editalFile ? (
                                <div className="flex items-center justify-center gap-2">
                                  <FileText className="w-5 h-5 text-purple-400" />
                                  <span className="text-sm text-purple-300">{editalFile.name}</span>
                                  <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setEditalFile(null)}><XCircle className="w-4 h-4 text-red-400" /></Button>
                                </div>
                              ) : (
                                <label className="cursor-pointer">
                                  <Upload className="w-8 h-8 mx-auto text-[#A1A1AA] mb-2" />
                                  <p className="text-sm text-[#A1A1AA]">Clique para selecionar o PDF</p>
                                  <p className="text-xs text-[#52525B] mt-1">Máximo 20MB</p>
                                  <input type="file" accept=".pdf" className="hidden" onChange={e => setEditalFile(e.target.files?.[0] || null)} />
                                </label>
                              )}
                            </div>
                          </div>
                          <div>
                            <Label className="text-sm font-medium">Data da Prova (opcional)</Label>
                            <Input type="date" value={editalForm.target_date} onChange={e => setEditalForm({...editalForm, target_date: e.target.value})} className="bg-[#121212] border-[#27272A] mt-1" />
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <Label className="text-sm font-medium">Horas por dia</Label>
                              <Select value={String(editalForm.hours_per_day)} onValueChange={v => setEditalForm({...editalForm, hours_per_day: parseFloat(v)})}>
                                <SelectTrigger className="bg-[#121212] border-[#27272A] mt-1"><SelectValue /></SelectTrigger>
                                <SelectContent className="bg-[#0A0A0A] border-[#27272A]">
                                  {[1,2,3,4,5,6,7,8,10,12].map(h => <SelectItem key={h} value={String(h)}>{h}h</SelectItem>)}
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <Label className="text-sm font-medium">Dias por semana</Label>
                              <Select value={String(editalForm.days_per_week)} onValueChange={v => setEditalForm({...editalForm, days_per_week: parseInt(v)})}>
                                <SelectTrigger className="bg-[#121212] border-[#27272A] mt-1"><SelectValue /></SelectTrigger>
                                <SelectContent className="bg-[#0A0A0A] border-[#27272A]">
                                  {[3,4,5,6,7].map(d => <SelectItem key={d} value={String(d)}>{d} dias</SelectItem>)}
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                          <div className="bg-[#121212] border border-[#27272A] rounded-lg p-3">
                            <p className="text-xs text-[#A1A1AA]"><Sparkles className="w-3 h-3 inline mr-1 text-purple-400" />A IA vai analisar o edital e criar automaticamente:</p>
                            <ul className="text-xs text-[#A1A1AA] mt-2 space-y-1 ml-4 list-disc">
                              <li>Todas as disciplinas com pesos e tópicos</li>
                              <li>Cronograma semanal otimizado</li>
                              <li>Estratégia de estudo personalizada</li>
                              <li>Distribuição de tempo por matéria</li>
                            </ul>
                          </div>
                          <Button onClick={handleAnalyzeEdital} disabled={!editalFile || editalImporting || editalAnalyzing} className="w-full bg-purple-600 hover:bg-purple-700">
                            {(editalImporting || editalAnalyzing) ? (
                              <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Analisando edital... (pode levar até 1 min)</>
                            ) : (
                              <><Sparkles className="w-4 h-4 mr-2" />Gerar Programa de Estudos</>
                            )}
                          </Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                    <Dialog open={showProgramDialog} onOpenChange={setShowProgramDialog}>
                      <DialogTrigger asChild><Button size="sm" className="bg-[#007AFF] h-8 text-xs"><Plus className="w-3 h-3 mr-1" />Novo Programa</Button></DialogTrigger>
                      <DialogContent className="bg-[#0A0A0A] border-[#27272A]">
                        <DialogHeader><DialogTitle>Novo Programa em {selectedArea.name}</DialogTitle><DialogDescription>Ex: Curso de Direito, Concurso TRF5, Certificação AWS</DialogDescription></DialogHeader>
                        <div className="space-y-4 py-4">
                          <div><Label>Nome</Label><Input value={programForm.name} onChange={e => setProgramForm({...programForm, name: e.target.value})} placeholder="Ex: Curso de Direito" className="bg-[#121212] border-[#27272A]" /></div>
                          <div><Label>Descrição</Label><Input value={programForm.description} onChange={e => setProgramForm({...programForm, description: e.target.value})} placeholder="Opcional" className="bg-[#121212] border-[#27272A]" /></div>
                          <div><Label>Data meta (opcional)</Label><Input type="date" value={programForm.target_date} onChange={e => setProgramForm({...programForm, target_date: e.target.value})} className="bg-[#121212] border-[#27272A]" /></div>
                          <div><Label>Cor</Label><Input type="color" value={programForm.color} onChange={e => setProgramForm({...programForm, color: e.target.value})} className="bg-[#121212] border-[#27272A] h-10" /></div>
                          <Button onClick={handleCreateProgram} className="w-full bg-[#007AFF]">Criar Programa</Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                    <Button variant="outline" size="sm" className="border-red-500 text-red-500 h-8 text-xs" onClick={() => handleDeleteArea(selectedArea.area_id)}><Trash2 className="w-3 h-3" /></Button>
                  </div>
                </div>

                {/* Programs Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {areaPrograms.map(prog => {
                    const pctCorrect = prog.total_questions > 0 ? Math.round((prog.correct_questions / prog.total_questions) * 100) : 0;
                    const isEditalProgram = prog.source_type === "edital_import";
                    return (
                      <Card key={prog.program_id} className={`bg-[#0A0A0A] border-[#27272A] cursor-pointer hover:scale-[1.02] transition-all group ${isEditalProgram ? 'border-l-2 border-l-purple-500' : ''}`} onClick={() => navigateToProgram(prog)}>
                        <CardHeader className="pb-2">
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: prog.color }} />
                              <CardTitle className="text-base">{prog.name}</CardTitle>
                            </div>
                            <div className="flex items-center gap-1">
                              {isEditalProgram && (
                                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={e => { e.stopPropagation(); handleViewCronograma(prog.program_id); }} title="Ver Cronograma">
                                  <LayoutGrid className="w-3 h-3 text-purple-400" />
                                </Button>
                              )}
                              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={e => { e.stopPropagation(); handleDeleteProgram(prog.program_id); }}><Trash2 className="w-3 h-3 text-red-500" /></Button>
                            </div>
                          </div>
                          {isEditalProgram && (
                            <Badge variant="outline" className="text-[10px] border-purple-500 text-purple-400 w-fit"><FileUp className="w-3 h-3 mr-1" />Gerado via Edital</Badge>
                          )}
                          {prog.description && <CardDescription className="text-xs mt-1">{prog.description}</CardDescription>}
                        </CardHeader>
                        <CardContent className="pt-0">
                          <div className="grid grid-cols-3 gap-2 text-center text-xs mb-3">
                            <div><p className="text-[#A1A1AA]">Matérias</p><p className="font-bold text-white">{prog.notebooks_count || 0}</p></div>
                            <div><p className="text-[#A1A1AA]">Questões</p><p className="font-bold text-purple-400">{prog.total_questions || 0}</p></div>
                            <div><p className="text-[#A1A1AA]">Acerto</p><p className={`font-bold ${pctCorrect >= 70 ? 'text-green-400' : pctCorrect >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{pctCorrect}%</p></div>
                          </div>
                          {prog.target_date && (
                            <Badge variant="outline" className="text-[10px] border-purple-500 text-purple-400"><Calendar className="w-3 h-3 mr-1" />Meta: {prog.target_date}</Badge>
                          )}
                          <div className="flex items-center justify-between mt-2">
                            {isEditalProgram && (
                              <div className="flex items-center gap-2">
                                <span className="text-[10px] text-purple-400 cursor-pointer hover:underline" onClick={e => { e.stopPropagation(); handleViewCronograma(prog.program_id); }}>Ver cronograma</span>
                                <span className="text-[10px] text-blue-400 cursor-pointer hover:underline" onClick={e => { e.stopPropagation(); handleViewVerticalizado(prog.program_id); }}>Edital verticalizado</span>
                              </div>
                            )}
                            <span className="text-xs text-[#A1A1AA] group-hover:text-white transition-colors flex items-center gap-1 ml-auto">Ver matérias <ChevronRight className="w-3 h-3" /></span>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>

                {areaPrograms.length === 0 && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardContent className="text-center py-10">
                      <FolderOpen className="w-10 h-10 mx-auto text-[#A1A1AA] mb-3" />
                      <h3 className="font-medium mb-1">Nenhum programa ainda</h3>
                      <p className="text-sm text-[#A1A1AA]">Crie um programa para organizar suas matérias</p>
                    </CardContent>
                  </Card>
                )}

                {/* Loose notebooks (without program) */}
                {areaNotebooksNoProgram.length > 0 && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardHeader className="pb-2"><CardTitle className="text-sm text-[#A1A1AA]">Matérias avulsas (sem programa)</CardTitle></CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        {areaNotebooksNoProgram.map(nb => (
                          <div key={nb.notebook_id} className="p-3 bg-[#121212] rounded-lg cursor-pointer hover:bg-[#1A1A1A] transition-colors" onClick={() => navigateToNotebook(nb)}>
                            <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full" style={{ backgroundColor: nb.color }} /><span className="text-sm font-medium">{nb.name}</span></div>
                            <p className="text-xs text-[#A1A1AA] mt-1">{Math.round((nb.total_study_time_minutes || 0) / 60)}h · {nb.total_questions || 0}q</p>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </>
            ) : (
              <Card className="bg-[#0A0A0A] border-[#27272A]"><CardContent className="text-center py-10"><Folder className="w-10 h-10 mx-auto text-[#A1A1AA] mb-3" /><h3 className="font-medium mb-1">Selecione uma Área</h3><p className="text-sm text-[#A1A1AA]">Escolha uma área acima para ver os programas</p></CardContent></Card>
            )}
          </TabsContent>

          {/* ========== MATERIAS TAB ========== */}
          <TabsContent value="materias" className="space-y-4">
            {selectedProgram ? (
              <>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                  <div>
                    <h2 className="text-lg font-bold" style={{ color: selectedProgram.color }}>{selectedProgram.name}</h2>
                    <p className="text-xs text-[#A1A1AA]">{selectedProgram.description || 'Matérias e disciplinas'}</p>
                  </div>
                  <div className="flex gap-2">
                    <Dialog open={showNotebookDialog} onOpenChange={setShowNotebookDialog}>
                      <DialogTrigger asChild><Button size="sm" className="bg-[#007AFF] h-8 text-xs"><Plus className="w-3 h-3 mr-1" />Nova Matéria</Button></DialogTrigger>
                      <DialogContent className="bg-[#0A0A0A] border-[#27272A]">
                        <DialogHeader><DialogTitle>Nova Matéria em {selectedProgram.name}</DialogTitle></DialogHeader>
                        <div className="space-y-4 py-4">
                          <div><Label>Nome</Label><Input value={notebookForm.name} onChange={e => setNotebookForm({...notebookForm, name: e.target.value})} placeholder="Ex: Direito Civil" className="bg-[#121212] border-[#27272A]" /></div>
                          <div><Label>Descrição</Label><Input value={notebookForm.description} onChange={e => setNotebookForm({...notebookForm, description: e.target.value})} placeholder="Opcional" className="bg-[#121212] border-[#27272A]" /></div>
                          <div><Label>Cor</Label><Input type="color" value={notebookForm.color} onChange={e => setNotebookForm({...notebookForm, color: e.target.value})} className="bg-[#121212] border-[#27272A] h-10" /></div>
                          <Button onClick={handleCreateNotebook} className="w-full bg-[#007AFF]">Criar Matéria</Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {programNotebooks.map(nb => {
                    const pct = nb.total_questions > 0 ? Math.round((nb.correct_questions / nb.total_questions) * 100) : 0;
                    return (
                      <Card key={nb.notebook_id} className={`bg-[#0A0A0A] border-[#27272A] cursor-pointer hover:scale-[1.02] transition-all ${selectedNotebook?.notebook_id === nb.notebook_id ? 'ring-2 ring-[#007AFF]' : ''}`} onClick={() => navigateToNotebook(nb)}>
                        <CardHeader className="pb-2">
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full" style={{ backgroundColor: nb.color }} /><CardTitle className="text-base">{nb.name}</CardTitle></div>
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={e => { e.stopPropagation(); handleDeleteNotebook(nb.notebook_id); }}><Trash2 className="w-3 h-3 text-red-500" /></Button>
                          </div>
                          {nb.description && <CardDescription className="text-xs">{nb.description}</CardDescription>}
                        </CardHeader>
                        <CardContent className="pt-0">
                          <div className="flex items-center gap-3 text-xs text-[#A1A1AA]">
                            <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{Math.round((nb.total_study_time_minutes || 0) / 60)}h</span>
                            <span className="flex items-center gap-1"><Hash className="w-3 h-3" />{nb.total_questions || 0}q</span>
                            {pct > 0 && <span className={`font-medium ${pct >= 70 ? 'text-green-400' : pct >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{pct}%</span>}
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>

                {programNotebooks.length === 0 && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]"><CardContent className="text-center py-10"><BookOpen className="w-10 h-10 mx-auto text-[#A1A1AA] mb-3" /><h3 className="font-medium mb-1">Nenhuma matéria ainda</h3><p className="text-sm text-[#A1A1AA]">Adicione matérias a este programa</p></CardContent></Card>
                )}
              </>
            ) : (
              <Card className="bg-[#0A0A0A] border-[#27272A]"><CardContent className="text-center py-10"><FolderOpen className="w-10 h-10 mx-auto text-[#A1A1AA] mb-3" /><h3 className="font-medium mb-1">Selecione um Programa</h3><p className="text-sm text-[#A1A1AA]">Vá até a aba "Programas" e selecione um</p></CardContent></Card>
            )}
          </TabsContent>

          {/* ========== CONTEUDO TAB ========== */}
          <TabsContent value="conteudo" className="space-y-4">
            {selectedNotebook ? (
              <>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                  <div>
                    <h2 className="text-lg font-bold" style={{ color: selectedNotebook.color }}>{selectedNotebook.name}</h2>
                    <div className="flex gap-2 mt-1">
                      <Badge variant="outline" className="text-[10px]"><Clock className="w-3 h-3 mr-1" />{Math.round((selectedNotebook.total_study_time_minutes || 0) / 60)}h</Badge>
                      <Badge variant="outline" className="text-[10px]"><Hash className="w-3 h-3 mr-1" />{selectedNotebook.total_questions || 0} questões</Badge>
                    </div>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <Dialog open={showNoteDialog} onOpenChange={setShowNoteDialog}>
                      <DialogTrigger asChild><Button size="sm" variant="outline" className="h-8 text-xs"><PenTool className="w-3 h-3 mr-1" />Nota</Button></DialogTrigger>
                      <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-2xl max-h-[90vh] overflow-y-auto">
                        <DialogHeader><DialogTitle>Nova Nota</DialogTitle></DialogHeader>
                        <div className="space-y-4 py-4">
                          <div><Label>Título</Label><Input value={noteForm.title} onChange={e => setNoteForm({...noteForm, title: e.target.value})} placeholder="Título" className="bg-[#121212] border-[#27272A]" /></div>
                          <div><Label>Conteúdo</Label><Textarea value={noteForm.content} onChange={e => setNoteForm({...noteForm, content: e.target.value})} placeholder="Escreva..." className="bg-[#121212] border-[#27272A] min-h-[150px]" /></div>
                          <div>
                            <Label>Tags</Label>
                            <div className="flex gap-2 mb-2"><Input value={newTag} onChange={e => setNewTag(e.target.value)} placeholder="Tag" className="bg-[#121212] border-[#27272A]" /><Button onClick={() => addTag(setNoteForm, noteForm.tags)} variant="outline"><Plus className="w-4 h-4" /></Button></div>
                            <div className="flex flex-wrap gap-1">{noteForm.tags.map((tag, i) => <Badge key={i} variant="secondary" className="cursor-pointer" onClick={() => removeTag(setNoteForm, tag)}>{tag} ×</Badge>)}</div>
                          </div>
                          <div>
                            <Label>Links</Label>
                            <div className="flex gap-2 mb-2"><Input value={newLink.title} onChange={e => setNewLink({...newLink, title: e.target.value})} placeholder="Título" className="bg-[#121212] border-[#27272A] flex-1" /><Input value={newLink.url} onChange={e => setNewLink({...newLink, url: e.target.value})} placeholder="URL" className="bg-[#121212] border-[#27272A] flex-1" /><Button onClick={addLink} variant="outline"><Plus className="w-4 h-4" /></Button></div>
                            {noteForm.links.map((lnk, i) => <div key={i} className="flex items-center gap-2 bg-[#121212] p-2 rounded text-sm"><Link className="w-3 h-3 text-[#007AFF]" />{lnk.title}<Button variant="ghost" size="icon" className="h-5 w-5 ml-auto" onClick={() => setNoteForm(prev => ({ ...prev, links: prev.links.filter((_, j) => j !== i) }))}><Trash2 className="w-3 h-3 text-red-500" /></Button></div>)}
                          </div>
                          <Button onClick={handleCreateNote} className="w-full bg-[#007AFF]">Salvar Nota</Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                    <Dialog open={showFlashcardDialog} onOpenChange={setShowFlashcardDialog}>
                      <DialogTrigger asChild><Button size="sm" variant="outline" className="h-8 text-xs"><Brain className="w-3 h-3 mr-1" />Flashcard</Button></DialogTrigger>
                      <DialogContent className="bg-[#0A0A0A] border-[#27272A]">
                        <DialogHeader><DialogTitle>Novo Flashcard</DialogTitle></DialogHeader>
                        <div className="space-y-4 py-4">
                          <div><Label>Deck</Label><Input value={flashcardForm.deck_name} onChange={e => setFlashcardForm({...flashcardForm, deck_name: e.target.value})} placeholder="Nome do deck" className="bg-[#121212] border-[#27272A]" /></div>
                          <div><Label>Frente (Pergunta)</Label><Textarea value={flashcardForm.front} onChange={e => setFlashcardForm({...flashcardForm, front: e.target.value})} placeholder="Pergunta" className="bg-[#121212] border-[#27272A]" /></div>
                          <div><Label>Verso (Resposta)</Label><Textarea value={flashcardForm.back} onChange={e => setFlashcardForm({...flashcardForm, back: e.target.value})} placeholder="Resposta" className="bg-[#121212] border-[#27272A]" /></div>
                          <Button onClick={handleCreateFlashcard} className="w-full bg-[#007AFF]">Criar</Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                    <Button size="sm" onClick={startReview} className="bg-yellow-600 h-8 text-xs" disabled={dueFlashcardsCount === 0}><Brain className="w-3 h-3 mr-1" />{dueFlashcardsCount} Revisar</Button>
                    <Button size="sm" onClick={handleGenerateQuiz} className="bg-purple-600 h-8 text-xs" disabled={generatingQuiz}>
                      {generatingQuiz ? <Loader2 className="w-3 h-3 animate-spin" /> : <><Sparkles className="w-3 h-3 mr-1" />Quiz IA</>}
                    </Button>
                    <Button size="sm" variant="outline" className="h-8 text-xs border-green-500/30 text-green-400 hover:bg-green-500/10" onClick={() => setShowMindmapDialog(true)}>
                      <Network className="w-3 h-3 mr-1" />Mapa Mental
                    </Button>
                    <Dialog open={showContentPdfDialog} onOpenChange={(open) => { setShowContentPdfDialog(open); if (!open) { setContentPdfResult(null); setContentPdfFile(null); } }}>
                      <DialogTrigger asChild><Button size="sm" variant="outline" className="h-8 text-xs border-orange-500/30 text-orange-400 hover:bg-orange-500/10"><Upload className="w-3 h-3 mr-1" />PDF → Estudo</Button></DialogTrigger>
                      <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-lg max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                          <DialogTitle className="flex items-center gap-2"><Sparkles className="w-5 h-5 text-orange-400" />Analisar Conteúdo PDF</DialogTitle>
                          <DialogDescription>Envie um PDF de conteúdo e a IA gerará materiais de estudo automaticamente</DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4">
                          <div>
                            <Label>Arquivo PDF *</Label>
                            <Input type="file" accept=".pdf" onChange={e => setContentPdfFile(e.target.files[0])}
                              className="bg-[#121212] border-[#27272A] file:bg-orange-500 file:text-white file:border-0 file:rounded file:px-3 file:py-1 file:mr-3 file:cursor-pointer" />
                          </div>
                          <div className="space-y-3">
                            <Label className="text-sm font-medium">O que gerar:</Label>
                            <div className="grid grid-cols-1 gap-2">
                              <label className="flex items-center gap-3 p-3 rounded-lg bg-[#121212] border border-[#27272A] cursor-pointer hover:border-[#3F3F46]">
                                <input type="checkbox" checked={contentPdfOptions.generate_notes} onChange={e => setContentPdfOptions({...contentPdfOptions, generate_notes: e.target.checked})} className="rounded" />
                                <FileText className="w-4 h-4 text-blue-400" />
                                <div><p className="text-sm font-medium">Revisão / Resumo</p><p className="text-xs text-[#A1A1AA]">Resumo completo com pontos-chave</p></div>
                              </label>
                              <label className="flex items-center gap-3 p-3 rounded-lg bg-[#121212] border border-[#27272A] cursor-pointer hover:border-[#3F3F46]">
                                <input type="checkbox" checked={contentPdfOptions.generate_flashcards} onChange={e => setContentPdfOptions({...contentPdfOptions, generate_flashcards: e.target.checked})} className="rounded" />
                                <Brain className="w-4 h-4 text-yellow-400" />
                                <div className="flex-1">
                                  <p className="text-sm font-medium">Flashcards</p>
                                  <p className="text-xs text-[#A1A1AA]">Cartões de memorização</p>
                                </div>
                                <Input type="number" min={1} max={50} value={contentPdfOptions.num_flashcards} onChange={e => setContentPdfOptions({...contentPdfOptions, num_flashcards: parseInt(e.target.value) || 5})}
                                  className="w-16 h-7 text-xs bg-[#0A0A0A] border-[#27272A]" />
                              </label>
                              <label className="flex items-center gap-3 p-3 rounded-lg bg-[#121212] border border-[#27272A] cursor-pointer hover:border-[#3F3F46]">
                                <input type="checkbox" checked={contentPdfOptions.generate_quiz} onChange={e => setContentPdfOptions({...contentPdfOptions, generate_quiz: e.target.checked})} className="rounded" />
                                <ListChecks className="w-4 h-4 text-purple-400" />
                                <div className="flex-1">
                                  <p className="text-sm font-medium">Quiz</p>
                                  <p className="text-xs text-[#A1A1AA]">Questões sobre o conteúdo</p>
                                </div>
                                <Input type="number" min={1} max={30} value={contentPdfOptions.num_quiz_questions} onChange={e => setContentPdfOptions({...contentPdfOptions, num_quiz_questions: parseInt(e.target.value) || 5})}
                                  className="w-16 h-7 text-xs bg-[#0A0A0A] border-[#27272A]" />
                              </label>
                            </div>
                          </div>
                          <Button onClick={handleAnalyzeContentPdf} className="w-full bg-orange-500 hover:bg-orange-600" disabled={contentPdfAnalyzing || !contentPdfFile}>
                            {contentPdfAnalyzing ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Analisando conteúdo...</> : <><Sparkles className="w-4 h-4 mr-2" />Analisar e Gerar Materiais</>}
                          </Button>
                          {contentPdfResult && (
                            <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                              <p className="text-green-400 font-medium text-sm mb-2 flex items-center gap-1"><CheckCircle2 className="w-4 h-4" />Conteúdo processado!</p>
                              <div className="space-y-1 text-xs text-[#A1A1AA]">
                                {contentPdfResult.note && <p>✅ Revisão criada: {contentPdfResult.note.title}</p>}
                                {contentPdfResult.flashcards_count && <p>✅ {contentPdfResult.flashcards_count} flashcards gerados</p>}
                                {contentPdfResult.quiz && <p>✅ Quiz criado: {contentPdfResult.quiz.title}</p>}
                                <p className="text-yellow-400">+{contentPdfResult.xp_earned} XP</p>
                              </div>
                            </div>
                          )}
                        </div>
                      </DialogContent>
                    </Dialog>
                    <Dialog open={showSessionDialog} onOpenChange={setShowSessionDialog}>
                      <DialogTrigger asChild><Button size="sm" className="bg-green-600 h-8 text-xs"><Timer className="w-3 h-3 mr-1" />Sessão</Button></DialogTrigger>
                      <DialogContent className="bg-[#0A0A0A] border-[#27272A]">
                        <DialogHeader><DialogTitle>Registrar Sessão</DialogTitle></DialogHeader>
                        <div className="space-y-4 py-4">
                          <div><Label>Duração (min)</Label><Input type="number" value={sessionForm.duration_minutes} onChange={e => setSessionForm({...sessionForm, duration_minutes: Number(e.target.value)})} className="bg-[#121212] border-[#27272A]" /></div>
                          <div><Label>Notas</Label><Textarea value={sessionForm.notes} onChange={e => setSessionForm({...sessionForm, notes: e.target.value})} placeholder="O que estudou?" className="bg-[#121212] border-[#27272A]" /></div>
                          <Button onClick={handleLogSession} className="w-full bg-green-600">Registrar (+XP)</Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>

                {/* Conteúdo Programático with Progress Tracking */}
                {selectedNotebook?.conteudo_programatico?.length > 0 && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <BookOpen className="w-4 h-4 text-purple-400" />Conteúdo Programático
                        <Badge variant="outline" className="text-[10px] ml-auto">
                          {Object.keys(topicProgress).filter(k => topicProgress[k]?.studied).length}/{selectedNotebook.conteudo_programatico.reduce((a, item) => a + 1 + (item.subtopicos?.length || 0), 0)} concluídos
                        </Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {selectedNotebook.conteudo_programatico.map((item, idx) => {
                          const topicKey = String(idx);
                          const tp = topicProgress[topicKey] || {};
                          return (
                            <div key={idx} className="border border-[#27272A] rounded-lg overflow-hidden">
                              <div className="flex items-center gap-2 px-3 py-2 bg-[#121212]">
                                <button
                                  onClick={() => toggleTopicProgress(topicKey, 'studied')}
                                  className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${tp.studied ? 'bg-green-500 border-green-500' : 'border-[#52525B] hover:border-green-500'}`}
                                >
                                  {tp.studied && <CheckCircle2 className="w-3 h-3 text-white" />}
                                </button>
                                <span className={`text-xs font-medium flex-1 ${tp.studied ? 'text-green-400 line-through' : 'text-white'}`}>{idx + 1}. {item.assunto}</span>
                                <div className="flex gap-1">
                                  <button
                                    onClick={() => toggleTopicProgress(topicKey, 'reviewed')}
                                    title="Revisado"
                                    className={`px-1.5 py-0.5 rounded text-[9px] border transition-colors ${tp.reviewed ? 'bg-blue-500/20 border-blue-500 text-blue-400' : 'border-[#3F3F46] text-[#71717A] hover:border-blue-500'}`}
                                  >🔄</button>
                                  <button
                                    onClick={() => toggleTopicProgress(topicKey, 'mastered')}
                                    title="Dominado"
                                    className={`px-1.5 py-0.5 rounded text-[9px] border transition-colors ${tp.mastered ? 'bg-yellow-500/20 border-yellow-500 text-yellow-400' : 'border-[#3F3F46] text-[#71717A] hover:border-yellow-500'}`}
                                  >⭐</button>
                                </div>
                              </div>
                              {item.subtopicos?.length > 0 && (
                                <div className="px-3 py-2 space-y-1.5 bg-[#0A0A0A]">
                                  {item.subtopicos.map((sub, si) => {
                                    const subKey = `${idx}_${si}`;
                                    const stp = topicProgress[subKey] || {};
                                    return (
                                      <div key={si} className="flex items-center gap-2 ml-4">
                                        <button
                                          onClick={() => toggleTopicProgress(subKey, 'studied')}
                                          className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors ${stp.studied ? 'bg-green-500 border-green-500' : 'border-[#52525B] hover:border-green-500'}`}
                                        >
                                          {stp.studied && <CheckCircle2 className="w-2.5 h-2.5 text-white" />}
                                        </button>
                                        <span className={`text-[11px] flex-1 ${stp.studied ? 'text-green-400/70 line-through' : 'text-[#A1A1AA]'}`}>{sub}</span>
                                        <div className="flex gap-0.5">
                                          <button
                                            onClick={() => toggleTopicProgress(subKey, 'reviewed')}
                                            className={`px-1 py-0.5 rounded text-[8px] border ${stp.reviewed ? 'bg-blue-500/20 border-blue-500 text-blue-400' : 'border-[#27272A] text-[#52525B]'}`}
                                          >🔄</button>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                      {/* Quick Action Buttons for Content */}
                      <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-[#27272A]">
                        <Button size="sm" onClick={handleGenerateQuiz} className="bg-purple-600 h-7 text-[10px]" disabled={generatingQuiz}>
                          {generatingQuiz ? <Loader2 className="w-3 h-3 animate-spin" /> : <><Sparkles className="w-3 h-3 mr-1" />Gerar Questões</>}
                        </Button>
                        <Button size="sm" variant="outline" className="h-7 text-[10px] border-yellow-500/30 text-yellow-400" onClick={() => {
                          if (notes.length > 0) handleGenerateFlashcards(notes[0].note_id);
                          else toast.info("Crie uma nota primeiro para gerar flashcards");
                        }} disabled={generatingFlashcards}>
                          <Brain className="w-3 h-3 mr-1" />Gerar Flashcards
                        </Button>
                        <Button size="sm" variant="outline" className="h-7 text-[10px] border-green-500/30 text-green-400" onClick={() => setShowMindmapDialog(true)}>
                          <Network className="w-3 h-3 mr-1" />Mapa Mental
                        </Button>
                        <Button size="sm" variant="outline" className="h-7 text-[10px] border-blue-500/30 text-blue-400" onClick={() => {
                          const simForm = { title: `Simulado - ${selectedNotebook.name}`, disciplina: selectedNotebook.name, question_type: "multipla_escolha", num_questions: 10, difficulty: "medio" };
                          setGenerateForm(simForm);
                          setShowGenerateDialog(true);
                        }}>
                          <ClipboardList className="w-3 h-3 mr-1" />Gerar Simulado
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Notes */}
                <Card className="bg-[#0A0A0A] border-[#27272A]">
                  <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><PenTool className="w-4 h-4 text-blue-400" />Notas ({notes.length})</CardTitle></CardHeader>
                  <CardContent>
                    {notes.length === 0 ? <p className="text-center text-[#A1A1AA] py-6 text-sm">Nenhuma nota. Crie a primeira!</p> : (
                      <div className="space-y-3">
                        {notes.map(note => (
                          <div key={note.note_id} className="bg-[#121212] p-3 rounded-lg">
                            <div className="flex items-start justify-between mb-1">
                              <h4 className="font-medium text-sm">{note.title}</h4>
                              <div className="flex gap-1">
                                <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => handleGenerateFlashcards(note.note_id)} disabled={generatingFlashcards}>
                                  {generatingFlashcards ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3 text-yellow-500" />}
                                </Button>
                                <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => handleDeleteNote(note.note_id)}><Trash2 className="w-3 h-3 text-red-500" /></Button>
                              </div>
                            </div>
                            <p className="text-xs text-[#A1A1AA] whitespace-pre-wrap line-clamp-3">{note.content}</p>
                            {note.tags?.length > 0 && <div className="flex flex-wrap gap-1 mt-2">{note.tags.map((t, i) => <Badge key={i} variant="outline" className="text-[10px] h-5">{t}</Badge>)}</div>}
                            {note.links?.length > 0 && <div className="flex flex-wrap gap-2 mt-2">{note.links.map((lnk, i) => <a key={i} href={lnk.url} target="_blank" rel="noopener noreferrer" className="text-[10px] text-[#007AFF] hover:underline flex items-center gap-1"><Link className="w-3 h-3" />{lnk.title}</a>)}</div>}
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Flashcards */}
                {flashcards.length > 0 && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Brain className="w-4 h-4 text-yellow-400" />Flashcards ({flashcards.length})</CardTitle></CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {flashcards.slice(0, 6).map(card => {
                          const isDue = card.next_review <= new Date().toISOString().split('T')[0];
                          return (
                            <div key={card.flashcard_id} className={`bg-[#121212] p-3 rounded-lg text-sm ${isDue ? 'ring-1 ring-yellow-500/50' : ''}`}>
                              <div className="flex items-center justify-between mb-1"><Badge variant="outline" className="text-[10px]">{card.deck_name}</Badge>{isDue && <Badge className="bg-yellow-500/20 text-yellow-400 text-[10px]">Revisar</Badge>}</div>
                              <p className="font-medium line-clamp-1">{card.front}</p>
                              <p className="text-xs text-[#A1A1AA] line-clamp-1 mt-1">{card.back}</p>
                            </div>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Quizzes */}
                {quizzes.length > 0 && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><FileText className="w-4 h-4 text-purple-400" />Quizzes ({quizzes.length})</CardTitle></CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {quizzes.map(quiz => (
                          <div key={quiz.quiz_id} className="bg-[#121212] p-3 rounded-lg flex items-center justify-between">
                            <div>
                              <p className="text-sm font-medium">{quiz.title}</p>
                              <p className="text-xs text-[#A1A1AA]">{quiz.questions?.length || 0} questões{quiz.ai_generated ? ' · IA' : ''}</p>
                            </div>
                            <Button size="sm" onClick={() => startQuiz(quiz)} className="bg-purple-600 h-7 text-xs"><Play className="w-3 h-3 mr-1" />Iniciar</Button>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Review Dialog */}
                <Dialog open={showReviewDialog} onOpenChange={setShowReviewDialog}>
                  <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-lg">
                    <DialogHeader><DialogTitle>Revisão Espaçada</DialogTitle><DialogDescription>Avalie sua lembrança</DialogDescription></DialogHeader>
                    {currentFlashcard && (
                      <div className="py-4">
                        <Card className="bg-[#121212] border-[#27272A] min-h-[180px] flex flex-col justify-center">
                          <CardContent className="p-6 text-center">
                            <p className="text-lg">{currentFlashcard.front}</p>
                            {showAnswer && <div className="mt-4 pt-4 border-t border-[#27272A]"><p className="text-[#00F0FF]">{currentFlashcard.back}</p></div>}
                          </CardContent>
                        </Card>
                        {!showAnswer ? (
                          <Button onClick={() => setShowAnswer(true)} className="w-full mt-4 bg-[#007AFF]">Mostrar Resposta</Button>
                        ) : (
                          <div className="mt-4 space-y-2">
                            <p className="text-center text-xs text-[#A1A1AA]">Como foi?</p>
                            <div className="grid grid-cols-4 gap-2">
                              <Button onClick={() => handleReviewFlashcard(0)} variant="outline" className="border-red-500 text-red-500 text-xs">Esqueci</Button>
                              <Button onClick={() => handleReviewFlashcard(2)} variant="outline" className="border-yellow-500 text-yellow-500 text-xs">Difícil</Button>
                              <Button onClick={() => handleReviewFlashcard(4)} variant="outline" className="border-green-500 text-green-500 text-xs">Bom</Button>
                              <Button onClick={() => handleReviewFlashcard(5)} variant="outline" className="border-[#00F0FF] text-[#00F0FF] text-xs">Fácil</Button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </DialogContent>
                </Dialog>

                {/* Quiz Dialog */}
                <Dialog open={showQuizDialog} onOpenChange={setShowQuizDialog}>
                  <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-2xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader><DialogTitle>{currentQuiz?.title}</DialogTitle></DialogHeader>
                    {currentQuiz && !quizResult && (
                      <div className="py-4 space-y-4">
                        {currentQuiz.questions?.map((q, idx) => (
                          <div key={idx} className="bg-[#121212] p-4 rounded-lg">
                            <p className="font-medium mb-2 text-sm">{idx + 1}. {q.question}</p>
                            <div className="space-y-2">
                              {q.options?.map((option, oi) => {
                                const letter = option.charAt(0);
                                const isSel = quizAnswers.find(a => a.question_idx === idx)?.selected_answer === letter;
                                return <button key={oi} onClick={() => handleQuizAnswer(idx, letter)} className={`w-full text-left p-2 rounded-lg text-sm transition-all ${isSel ? 'bg-[#007AFF] text-white' : 'bg-[#0A0A0A] hover:bg-[#27272A]'}`}>{option}</button>;
                              })}
                            </div>
                          </div>
                        ))}
                        <Button onClick={submitQuiz} className="w-full bg-purple-600" disabled={quizAnswers.length < (currentQuiz.questions?.length || 0)}>Finalizar</Button>
                      </div>
                    )}
                    {quizResult && (
                      <div className="py-4 space-y-4">
                        <div className="text-center">
                          <div className="text-4xl font-bold text-[#00F0FF] mb-1">{(quizResult.score ?? 0).toFixed(0)}%</div>
                          <p className="text-[#A1A1AA] text-sm">{quizResult.correct_count ?? 0}/{quizResult.total_questions ?? 0} · +{quizResult.xp_earned ?? 0} XP</p>
                        </div>
                        <div className="space-y-3">
                          {quizResult.answers?.map((ans, idx) => (
                            <div key={idx} className={`p-3 rounded-lg text-sm ${ans.correct ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'}`}>
                              <div className="flex items-center gap-2 mb-1">{ans.correct ? <CheckCircle2 className="w-4 h-4 text-green-500" /> : <XCircle className="w-4 h-4 text-red-500" />}<span className="font-medium">Questão {idx + 1}</span></div>
                              {!ans.correct && <p className="text-xs text-[#A1A1AA]">Correta: {ans.correct_answer}</p>}
                              {ans.explanation && <p className="text-xs text-[#A1A1AA] mt-1">{ans.explanation}</p>}
                            </div>
                          ))}
                        </div>
                        <Button onClick={() => { setShowQuizDialog(false); setQuizResult(null); }} className="w-full">Fechar</Button>
                      </div>
                    )}
                  </DialogContent>
                </Dialog>
              </>
            ) : (
              <Card className="bg-[#0A0A0A] border-[#27272A]"><CardContent className="text-center py-10"><BookMarked className="w-10 h-10 mx-auto text-[#A1A1AA] mb-3" /><h3 className="font-medium mb-1">Selecione uma Matéria</h3><p className="text-sm text-[#A1A1AA]">Navegue pelas áreas e programas para acessar uma matéria</p></CardContent></Card>
            )}
          </TabsContent>

          {/* ========== TAREFAS TAB ========== */}
          <TabsContent value="tarefas" className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold">Tarefas de Estudo</h2>
              <Dialog open={showTaskDialog} onOpenChange={setShowTaskDialog}>
                <DialogTrigger asChild><Button size="sm" className="bg-[#007AFF] h-8 text-xs"><Plus className="w-3 h-3 mr-1" />Nova Tarefa</Button></DialogTrigger>
                <DialogContent className="bg-[#0A0A0A] border-[#27272A]">
                  <DialogHeader><DialogTitle>Nova Tarefa</DialogTitle></DialogHeader>
                  <div className="space-y-4 py-4">
                    <div><Label>Título</Label><Input value={taskForm.title} onChange={e => setTaskForm({...taskForm, title: e.target.value})} placeholder="Ex: Ler capítulo 5" className="bg-[#121212] border-[#27272A]" /></div>
                    <div><Label>Descrição</Label><Textarea value={taskForm.description} onChange={e => setTaskForm({...taskForm, description: e.target.value})} placeholder="Detalhes" className="bg-[#121212] border-[#27272A]" /></div>
                    <div className="grid grid-cols-2 gap-3">
                      <div><Label>Tipo</Label>
                        <Select value={taskForm.task_type} onValueChange={v => setTaskForm({...taskForm, task_type: v})}><SelectTrigger className="bg-[#121212] border-[#27272A]"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(taskTypeLabels).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select>
                      </div>
                      <div><Label>Prioridade</Label>
                        <Select value={taskForm.priority} onValueChange={v => setTaskForm({...taskForm, priority: v})}><SelectTrigger className="bg-[#121212] border-[#27272A]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="low">Baixa</SelectItem><SelectItem value="medium">Média</SelectItem><SelectItem value="high">Alta</SelectItem></SelectContent></Select>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div><Label>Recorrência</Label>
                        <Select value={taskForm.recurrence} onValueChange={v => setTaskForm({...taskForm, recurrence: v})}><SelectTrigger className="bg-[#121212] border-[#27272A]"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(recurrenceLabels).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select>
                      </div>
                      <div><Label>Prazo</Label><Input type="date" value={taskForm.deadline} onChange={e => setTaskForm({...taskForm, deadline: e.target.value})} className="bg-[#121212] border-[#27272A]" /></div>
                    </div>
                    <Button onClick={handleCreateTask} className="w-full bg-[#007AFF]">Criar</Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><AlertCircle className="w-4 h-4 text-yellow-500" />Pendentes ({tasks.filter(t => !t.completed_today).length})</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {tasks.filter(t => !t.completed_today).map(task => (
                      <div key={task.task_id} className="bg-[#121212] p-3 rounded-lg">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-2">
                            <button onClick={() => handleToggleTask(task.task_id, true)} className="mt-0.5 w-4 h-4 rounded border-2 border-[#27272A] hover:border-green-500 shrink-0" />
                            <div>
                              <h4 className="text-sm font-medium">{task.title}</h4>
                              <div className="flex flex-wrap gap-1 mt-1">
                                <Badge variant="outline" className="text-[10px] h-5">{taskTypeLabels[task.task_type]}</Badge>
                                <Badge className={`text-[10px] h-5 ${task.priority === 'high' ? 'bg-red-500/20 text-red-400' : task.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-green-500/20 text-green-400'}`}>{task.priority}</Badge>
                                {task.recurrence !== "once" && <Badge variant="outline" className="text-[10px] h-5 border-blue-500 text-blue-400"><Repeat className="w-2 h-2 mr-1" />{recurrenceLabels[task.recurrence]}</Badge>}
                                {task.deadline && <Badge variant="outline" className="text-[10px] h-5 border-purple-500 text-purple-400">{task.deadline}</Badge>}
                              </div>
                            </div>
                          </div>
                          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => handleDeleteTask(task.task_id)}><Trash2 className="w-3 h-3 text-red-500" /></Button>
                        </div>
                      </div>
                    ))}
                    {tasks.filter(t => !t.completed_today).length === 0 && <p className="text-center text-[#A1A1AA] py-6 text-sm">Nenhuma tarefa pendente 🎉</p>}
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-green-500" />Concluídas ({tasks.filter(t => t.completed_today).length})</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {tasks.filter(t => t.completed_today).slice(0, 10).map(task => (
                      <div key={task.task_id} className="bg-[#121212] p-3 rounded-lg opacity-60">
                        <div className="flex items-center gap-2">
                          <button onClick={() => task.recurrence === 'once' ? handleToggleTask(task.task_id, false) : null} className={`w-4 h-4 rounded border-2 border-green-500 bg-green-500 flex items-center justify-center shrink-0 ${task.recurrence !== 'once' ? 'cursor-default' : ''}`}><CheckCircle2 className="w-2 h-2 text-white" /></button>
                          <span className={`text-sm ${task.recurrence === 'once' ? 'line-through' : ''}`}>{task.title}</span>
                        </div>
                      </div>
                    ))}
                    {tasks.filter(t => t.completed_today).length === 0 && <p className="text-center text-[#A1A1AA] py-6 text-sm">Nenhuma concluída hoje</p>}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* ========== SIMULADOS TAB ========== */}
          <TabsContent value="simulados" className="space-y-4">
            {simuladoMode === "taking" && currentSimulado ? (
              /* TAKING SIMULADO VIEW */
              <div className="space-y-4">
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Button variant="ghost" size="icon" onClick={() => { if (window.confirm("Deseja sair do simulado? Seu progresso será perdido.")) handleExitSimulado(); }}>
                      <ArrowLeft className="w-5 h-5" />
                    </Button>
                    <div>
                      <h3 className="text-lg font-bold">{currentSimulado.title}</h3>
                      <p className="text-xs text-[#A1A1AA]">
                        {currentSimulado.banca && <span className="mr-2">{currentSimulado.banca}</span>}
                        {currentSimulado.disciplina && <span className="mr-2">• {currentSimulado.disciplina}</span>}
                        Questão {simuladoCurrentQ + 1} de {currentSimulado.questions?.length || 0}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className="text-[#00F0FF] border-[#00F0FF] font-mono text-base px-3 py-1">
                      <Timer className="w-4 h-4 mr-1" />{formatTimer(simuladoTimer)}
                    </Badge>
                    <Badge variant="outline" className="text-green-400 border-green-400">
                      {Object.keys(simuladoAnswers).length}/{currentSimulado.questions?.length || 0}
                    </Badge>
                  </div>
                </div>

                {/* Question */}
                {currentSimulado.questions && currentSimulado.questions[simuladoCurrentQ] && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardContent className="p-6">
                      <div className="flex items-start justify-between mb-4">
                        <Badge className={`${simuladoMarked.has(simuladoCurrentQ) ? 'bg-yellow-500/20 text-yellow-400' : 'bg-[#1A1A2E] text-[#A1A1AA]'}`}>
                          Questão {currentSimulado.questions[simuladoCurrentQ].question_number || simuladoCurrentQ + 1}
                          {currentSimulado.questions[simuladoCurrentQ].disciplina && ` • ${currentSimulado.questions[simuladoCurrentQ].disciplina}`}
                        </Badge>
                        <Button variant="ghost" size="sm" onClick={() => {
                          const newMarked = new Set(simuladoMarked);
                          if (newMarked.has(simuladoCurrentQ)) newMarked.delete(simuladoCurrentQ);
                          else newMarked.add(simuladoCurrentQ);
                          setSimuladoMarked(newMarked);
                        }} className={simuladoMarked.has(simuladoCurrentQ) ? "text-yellow-400" : "text-[#A1A1AA]"}>
                          <Flag className="w-4 h-4 mr-1" />{simuladoMarked.has(simuladoCurrentQ) ? "Marcada" : "Marcar"}
                        </Button>
                      </div>

                      {/* Texto Base / Texto de Apoio */}
                      {currentSimulado.questions[simuladoCurrentQ].texto_base && (
                        <div className="mb-5 p-4 rounded-lg bg-[#121212] border border-[#27272A] border-l-4 border-l-[#007AFF]">
                          <p className="text-xs text-[#007AFF] font-semibold uppercase tracking-wide mb-2 flex items-center gap-1">
                            <BookOpen className="w-3 h-3" />Texto Base
                          </p>
                          <p className="text-[#D4D4D8] text-sm leading-relaxed whitespace-pre-wrap">
                            {currentSimulado.questions[simuladoCurrentQ].texto_base}
                          </p>
                        </div>
                      )}

                      <p className="text-white text-base leading-relaxed mb-6 whitespace-pre-wrap">
                        {currentSimulado.questions[simuladoCurrentQ].question_text}
                      </p>

                      <div className="space-y-3">
                        {(currentSimulado.questions[simuladoCurrentQ].options || []).map((opt, optIdx) => {
                          const letter = opt.match(/^([A-E]\))/)?.[1]?.replace(")", "") || (currentSimulado.questions[simuladoCurrentQ].type === "certo_errado" ? opt : String.fromCharCode(65 + optIdx));
                          const isSelected = simuladoAnswers[simuladoCurrentQ] === letter;
                          return (
                            <button key={optIdx} onClick={() => setSimuladoAnswers({ ...simuladoAnswers, [simuladoCurrentQ]: letter })}
                              className={`w-full text-left p-4 rounded-lg border transition-all ${isSelected ? 'border-[#007AFF] bg-[#007AFF]/10 text-white' : 'border-[#27272A] bg-[#121212] text-[#A1A1AA] hover:border-[#3F3F46]'}`}>
                              <span className={`font-bold mr-3 ${isSelected ? 'text-[#007AFF]' : ''}`}>{letter})</span>
                              {opt.replace(/^[A-E]\)\s*/, "")}
                            </button>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Navigation */}
                <div className="flex items-center justify-between">
                  <Button variant="outline" onClick={() => setSimuladoCurrentQ(Math.max(0, simuladoCurrentQ - 1))} disabled={simuladoCurrentQ === 0}
                    className="border-[#27272A]"><ChevronLeft className="w-4 h-4 mr-1" />Anterior</Button>

                  <div className="flex gap-1 flex-wrap justify-center max-w-md">
                    {(currentSimulado.questions || []).map((_, idx) => (
                      <button key={idx} onClick={() => setSimuladoCurrentQ(idx)}
                        className={`w-8 h-8 rounded text-xs font-bold transition-all ${
                          idx === simuladoCurrentQ ? 'bg-[#007AFF] text-white' :
                          simuladoAnswers[idx] !== undefined ? 'bg-green-500/20 text-green-400 border border-green-500/30' :
                          simuladoMarked.has(idx) ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
                          'bg-[#121212] text-[#A1A1AA] border border-[#27272A]'
                        }`}>{idx + 1}</button>
                    ))}
                  </div>

                  {simuladoCurrentQ < (currentSimulado.questions?.length || 1) - 1 ? (
                    <Button variant="outline" onClick={() => setSimuladoCurrentQ(simuladoCurrentQ + 1)}
                      className="border-[#27272A]">Próxima<ChevronRight className="w-4 h-4 ml-1" /></Button>
                  ) : (
                    <Button onClick={() => {
                      const unanswered = (currentSimulado.questions?.length || 0) - Object.keys(simuladoAnswers).length;
                      const msg = unanswered > 0 ? `Você tem ${unanswered} questão(ões) sem resposta. Deseja finalizar?` : "Deseja finalizar o simulado?";
                      if (window.confirm(msg)) handleSubmitSimulado();
                    }} className="bg-green-600 hover:bg-green-700" disabled={simuladoSubmitting}>
                      {simuladoSubmitting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <StopCircle className="w-4 h-4 mr-1" />}
                      Finalizar
                    </Button>
                  )}
                </div>

                {/* Legend */}
                <div className="flex items-center gap-4 justify-center text-xs text-[#A1A1AA]">
                  <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-[#007AFF]" />Atual</span>
                  <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-green-500/20 border border-green-500/30" />Respondida</span>
                  <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-yellow-500/20 border border-yellow-500/30" />Marcada</span>
                  <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-[#121212] border border-[#27272A]" />Não respondida</span>
                </div>
              </div>

            ) : simuladoMode === "viewing" && currentSimulado ? (
              /* VIEWING MODE - Browse questions with option to show/hide gabarito */
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Button variant="ghost" size="icon" onClick={handleExitSimulado}><ArrowLeft className="w-5 h-5" /></Button>
                    <div>
                      <h3 className="text-lg font-bold">{currentSimulado.title}</h3>
                      <p className="text-xs text-[#A1A1AA]">
                        {currentSimulado.banca && <span className="mr-2">{currentSimulado.banca}</span>}
                        {currentSimulado.disciplina && <span>• {currentSimulado.disciplina}</span>}
                        <span className="ml-2">• {currentSimulado.questions?.length || 0} questões</span>
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant={showGabarito ? "default" : "outline"}
                      size="sm"
                      onClick={() => setShowGabarito(!showGabarito)}
                      className={showGabarito ? "bg-green-600 hover:bg-green-700 text-white" : "border-[#27272A] text-[#A1A1AA] hover:text-white"}
                    >
                      {showGabarito ? <EyeOff className="w-4 h-4 mr-1" /> : <Eye className="w-4 h-4 mr-1" />}
                      {showGabarito ? "Ocultar Gabarito" : "Ver Gabarito"}
                    </Button>
                    <Button onClick={() => handleStartSimulado(currentSimulado)} className="bg-[#007AFF]">
                      <Play className="w-4 h-4 mr-1" />Iniciar Simulado
                    </Button>
                  </div>
                </div>

                <div className="space-y-4">
                  {(currentSimulado.questions || []).map((q, idx) => (
                    <Card key={idx} className="bg-[#0A0A0A] border-[#27272A]">
                      <CardContent className="p-5">
                        <div className="flex items-start justify-between mb-3">
                          <Badge className="bg-[#1A1A2E] text-[#A1A1AA]">
                            Questão {q.question_number || idx + 1}
                            {q.disciplina && ` • ${q.disciplina}`}
                          </Badge>
                          {q.difficulty && <Badge variant="outline" className="text-xs border-[#27272A]">{q.difficulty}</Badge>}
                        </div>
                        {q.texto_base && (
                          <div className="mb-3 p-3 rounded-lg bg-[#121212] border border-[#27272A] border-l-4 border-l-[#007AFF]">
                            <p className="text-xs text-[#007AFF] font-semibold uppercase tracking-wide mb-1 flex items-center gap-1">
                              <BookOpen className="w-3 h-3" />Texto Base
                            </p>
                            <p className="text-[#D4D4D8] text-xs leading-relaxed whitespace-pre-wrap">{q.texto_base}</p>
                          </div>
                        )}
                        <p className="text-white text-sm leading-relaxed mb-4 whitespace-pre-wrap">{q.question_text}</p>
                        <div className="space-y-2 mb-4">
                          {(q.options || []).map((opt, optIdx) => {
                            const letter = opt.match(/^([A-E]\))/)?.[1]?.replace(")", "") || (q.type === "certo_errado" ? opt : String.fromCharCode(65 + optIdx));
                            const isCorrect = letter === q.correct_answer || opt === q.correct_answer;
                            return (
                              <div key={optIdx} className={`p-3 rounded-lg border text-sm ${showGabarito && isCorrect ? 'border-green-500/40 bg-green-500/10 text-green-300' : 'border-[#27272A] bg-[#121212] text-[#A1A1AA]'}`}>
                                <span className={`font-bold mr-2 ${showGabarito && isCorrect ? 'text-green-400' : ''}`}>{letter})</span>
                                {opt.replace(/^[A-E]\)\s*/, "")}
                                {showGabarito && isCorrect && <CheckCircle2 className="w-4 h-4 inline ml-2 text-green-400" />}
                              </div>
                            );
                          })}
                        </div>
                        {showGabarito && q.explanation && (
                          <div className="bg-[#1A1A2E] p-3 rounded-lg border border-[#27272A]">
                            <p className="text-xs text-[#A1A1AA] font-medium mb-1 flex items-center gap-1"><Lightbulb className="w-3 h-3 text-yellow-400" />Explicação</p>
                            <p className="text-sm text-[#D4D4D8]">{q.explanation}</p>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>

                <div className="flex gap-3 justify-center">
                  <Button variant="outline" onClick={handleExitSimulado} className="border-[#27272A]"><ArrowLeft className="w-4 h-4 mr-1" />Voltar</Button>
                  <Button onClick={() => handleStartSimulado(currentSimulado)} className="bg-[#007AFF]"><Play className="w-4 h-4 mr-1" />Iniciar Simulado</Button>
                </div>
              </div>

            ) : simuladoMode === "results" && simuladoResult ? (
              /* RESULTS VIEW */
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <Button variant="ghost" size="icon" onClick={handleExitSimulado}><ArrowLeft className="w-5 h-5" /></Button>
                  <div>
                    <h3 className="text-lg font-bold">{currentSimulado?.title || "Resultado"}</h3>
                    <p className="text-xs text-[#A1A1AA]">
                      {currentSimulado?.banca && <span className="mr-2">{currentSimulado.banca}</span>}
                      Resultado do Simulado
                    </p>
                  </div>
                </div>

                {/* Score Cards */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardContent className="p-4 text-center">
                      <p className="text-xs text-[#A1A1AA] mb-1">Nota</p>
                      <p className={`text-3xl font-bold ${simuladoResult.score >= 70 ? 'text-green-400' : simuladoResult.score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{simuladoResult.score}%</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardContent className="p-4 text-center">
                      <p className="text-xs text-[#A1A1AA] mb-1">Acertos</p>
                      <p className="text-2xl font-bold text-green-400">{simuladoResult.correct_count}</p>
                      <p className="text-xs text-[#A1A1AA]">de {simuladoResult.total_questions}</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardContent className="p-4 text-center">
                      <p className="text-xs text-[#A1A1AA] mb-1">Erros</p>
                      <p className="text-2xl font-bold text-red-400">{(simuladoResult.total_answered || 0) - (simuladoResult.correct_count || 0)}</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardContent className="p-4 text-center">
                      <p className="text-xs text-[#A1A1AA] mb-1">Em branco</p>
                      <p className="text-2xl font-bold text-[#A1A1AA]">{simuladoResult.unanswered || 0}</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardContent className="p-4 text-center">
                      <p className="text-xs text-[#A1A1AA] mb-1">Tempo</p>
                      <p className="text-2xl font-bold text-[#00F0FF]">{formatTimer(simuladoResult.time_spent_seconds || 0)}</p>
                    </CardContent>
                  </Card>
                </div>

                {/* By Disciplina */}
                {simuladoResult.by_disciplina && Object.keys(simuladoResult.by_disciplina).length > 0 && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><BarChart3 className="w-4 h-4 text-purple-400" />Desempenho por Disciplina</CardTitle></CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {Object.entries(simuladoResult.by_disciplina).map(([disc, data]) => (
                          <div key={disc}>
                            <div className="flex justify-between text-sm mb-1">
                              <span>{disc}</span>
                              <span className={data.accuracy >= 70 ? 'text-green-400' : data.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'}>
                                {data.correct}/{data.total} ({data.accuracy}%)
                              </span>
                            </div>
                            <Progress value={data.accuracy} className="h-2" />
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* XP Earned */}
                {simuladoResult.xp_earned > 0 && (
                  <div className="text-center py-2">
                    <Badge className="bg-yellow-500/20 text-yellow-400 text-base px-4 py-2">
                      <Zap className="w-4 h-4 mr-1" />+{simuladoResult.xp_earned} XP ganhos!
                    </Badge>
                  </div>
                )}

                {/* Correction - Question by Question */}
                <Card className="bg-[#0A0A0A] border-[#27272A]">
                  <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><ListChecks className="w-4 h-4 text-[#007AFF]" />Gabarito Comentado</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {(simuladoResult.answers || []).map((ans, idx) => (
                        <div key={idx} className={`p-4 rounded-lg border ${ans.is_correct ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5'}`}>
                          <div className="flex items-start justify-between mb-2">
                            <Badge className={ans.is_correct ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
                              {ans.is_correct ? <CheckCircle2 className="w-3 h-3 mr-1" /> : <XCircle className="w-3 h-3 mr-1" />}
                              Questão {ans.question_number}
                            </Badge>
                            {ans.disciplina && <span className="text-xs text-[#A1A1AA]">{ans.disciplina}</span>}
                          </div>
                          {currentSimulado?.questions?.[ans.question_idx]?.texto_base && (
                            <div className="mb-2 p-2 rounded bg-[#121212] border border-[#27272A] border-l-2 border-l-[#007AFF]">
                              <p className="text-[10px] text-[#007AFF] font-semibold uppercase tracking-wide mb-1">Texto Base</p>
                              <p className="text-[#A1A1AA] text-xs leading-relaxed whitespace-pre-wrap line-clamp-4">{currentSimulado.questions[ans.question_idx].texto_base}</p>
                            </div>
                          )}
                          <p className="text-sm text-white mb-2 whitespace-pre-wrap line-clamp-3">
                            {currentSimulado?.questions?.[ans.question_idx]?.question_text}
                          </p>
                          <div className="flex items-center gap-4 text-sm">
                            <span className={ans.is_correct ? 'text-green-400' : 'text-red-400'}>
                              Sua resposta: <b>{ans.selected_answer}</b>
                            </span>
                            {!ans.is_correct && <span className="text-green-400">Correta: <b>{ans.correct_answer}</b></span>}
                          </div>
                          {ans.explanation && <p className="text-xs text-[#A1A1AA] mt-2 italic">{ans.explanation}</p>}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                <div className="flex gap-3 justify-center">
                  <Button variant="outline" onClick={handleExitSimulado} className="border-[#27272A]"><ArrowLeft className="w-4 h-4 mr-1" />Voltar</Button>
                  <Button onClick={() => handleStartSimulado(currentSimulado)} className="bg-[#007AFF]"><Repeat className="w-4 h-4 mr-1" />Refazer</Button>
                </div>
              </div>

            ) : (
              /* SIMULADOS LIST VIEW */
              <div className="space-y-4">
                {/* Header */}
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <h3 className="text-lg font-bold flex items-center gap-2"><ClipboardList className="w-5 h-5 text-[#007AFF]" />Simulados</h3>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => setShowSimuladoStatsView(!showSimuladoStatsView)} className="border-[#27272A]">
                      <BarChart3 className="w-4 h-4 mr-1" />Estatísticas
                    </Button>
                    <Dialog open={showImportPdfDialog} onOpenChange={setShowImportPdfDialog}>
                      <DialogTrigger asChild>
                        <Button size="sm" variant="outline" className="border-[#27272A]"><Upload className="w-4 h-4 mr-1" />Importar PDF</Button>
                      </DialogTrigger>
                      <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-lg max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                          <DialogTitle>Importar Simulado de PDF</DialogTitle>
                          <DialogDescription>Faça upload de um caderno de questões ou gabarito em PDF</DialogDescription>
                        </DialogHeader>
                        <div className="space-y-3">
                          <div>
                            <Label>Arquivo PDF *</Label>
                            <Input type="file" accept=".pdf" onChange={e => setImportFile(e.target.files[0])}
                              className="bg-[#121212] border-[#27272A] file:bg-[#007AFF] file:text-white file:border-0 file:rounded file:px-3 file:py-1 file:mr-3 file:cursor-pointer" />
                          </div>
                          <div><Label>Título</Label><Input value={importForm.title} onChange={e => setImportForm({...importForm, title: e.target.value})} className="bg-[#121212] border-[#27272A]" /></div>
                          <div className="grid grid-cols-2 gap-3">
                            <div><Label>Banca</Label><Input value={importForm.banca} onChange={e => setImportForm({...importForm, banca: e.target.value})} placeholder="Ex: CESPE, FCC" className="bg-[#121212] border-[#27272A]" /></div>
                            <div><Label>Concurso</Label><Input value={importForm.concurso} onChange={e => setImportForm({...importForm, concurso: e.target.value})} placeholder="Ex: TRF5, INSS" className="bg-[#121212] border-[#27272A]" /></div>
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            <div><Label>Disciplina</Label><Input value={importForm.disciplina} onChange={e => setImportForm({...importForm, disciplina: e.target.value})} placeholder="Ex: Direito Civil" className="bg-[#121212] border-[#27272A]" /></div>
                            <div><Label>Tipo de Questão</Label>
                              <Select value={importForm.question_type} onValueChange={v => setImportForm({...importForm, question_type: v})}>
                                <SelectTrigger className="bg-[#121212] border-[#27272A]"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="multipla_escolha">Múltipla Escolha (A-E)</SelectItem>
                                  <SelectItem value="certo_errado">Certo ou Errado</SelectItem>
                                  <SelectItem value="misto">Misto</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                          <p className="text-xs text-[#A1A1AA]">A IA irá analisar o PDF e extrair automaticamente as questões e gabarito.</p>
                          <Button onClick={handleImportPdf} className="w-full bg-[#007AFF]" disabled={simuladoImporting || !importFile}>
                            {simuladoImporting ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Processando PDF...</> : <><Upload className="w-4 h-4 mr-2" />Importar e Gerar Simulado</>}
                          </Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                    <Dialog open={showGenerateDialog} onOpenChange={setShowGenerateDialog}>
                      <DialogTrigger asChild>
                        <Button size="sm" className="bg-[#007AFF]"><Sparkles className="w-4 h-4 mr-1" />Gerar com IA</Button>
                      </DialogTrigger>
                      <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-lg max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                          <DialogTitle>Gerar Simulado com IA</DialogTitle>
                          <DialogDescription>A IA gerará questões originais baseadas nos parâmetros</DialogDescription>
                        </DialogHeader>
                        <div className="space-y-3">
                          <div><Label>Título *</Label><Input value={generateForm.title} onChange={e => setGenerateForm({...generateForm, title: e.target.value})} placeholder="Ex: Simulado Direito Civil - CESPE" className="bg-[#121212] border-[#27272A]" /></div>
                          <div className="grid grid-cols-2 gap-3">
                            <div><Label>Banca</Label>
                              <Select value={generateForm.banca} onValueChange={v => setGenerateForm({...generateForm, banca: v})}>
                                <SelectTrigger className="bg-[#121212] border-[#27272A]"><SelectValue placeholder="Selecione" /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="CESPE/CEBRASPE">CESPE/CEBRASPE</SelectItem>
                                  <SelectItem value="FCC">FCC</SelectItem>
                                  <SelectItem value="FGV">FGV</SelectItem>
                                  <SelectItem value="VUNESP">VUNESP</SelectItem>
                                  <SelectItem value="CESGRANRIO">CESGRANRIO</SelectItem>
                                  <SelectItem value="IBFC">IBFC</SelectItem>
                                  <SelectItem value="AOCP">AOCP</SelectItem>
                                  <SelectItem value="CONSULPLAN">CONSULPLAN</SelectItem>
                                  <SelectItem value="Outra">Outra</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div><Label>Disciplina</Label><Input value={generateForm.disciplina} onChange={e => setGenerateForm({...generateForm, disciplina: e.target.value})} placeholder="Ex: Direito Constitucional" className="bg-[#121212] border-[#27272A]" /></div>
                          </div>
                          <div><Label>Concurso</Label><Input value={generateForm.concurso} onChange={e => setGenerateForm({...generateForm, concurso: e.target.value})} placeholder="Ex: TRF 5ª Região, INSS, Receita Federal" className="bg-[#121212] border-[#27272A]" /></div>
                          <div className="grid grid-cols-3 gap-3">
                            <div><Label>Nº Questões</Label><Input type="number" min={1} value={generateForm.num_questions} onChange={e => setGenerateForm({...generateForm, num_questions: parseInt(e.target.value) || 1})} className="bg-[#121212] border-[#27272A]" /></div>
                            <div><Label>Tipo</Label>
                              <Select value={generateForm.question_type} onValueChange={v => setGenerateForm({...generateForm, question_type: v})}>
                                <SelectTrigger className="bg-[#121212] border-[#27272A]"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="multipla_escolha">Múltipla Escolha</SelectItem>
                                  <SelectItem value="certo_errado">Certo/Errado</SelectItem>
                                  <SelectItem value="misto">Misto</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div><Label>Dificuldade</Label>
                              <Select value={generateForm.difficulty} onValueChange={v => setGenerateForm({...generateForm, difficulty: v})}>
                                <SelectTrigger className="bg-[#121212] border-[#27272A]"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="facil">Fácil</SelectItem>
                                  <SelectItem value="medio">Médio</SelectItem>
                                  <SelectItem value="dificil">Difícil</SelectItem>
                                  <SelectItem value="misto">Misto</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                          <Button onClick={handleGenerateSimulado} className="w-full bg-[#007AFF]" disabled={simuladoGenerating || !generateForm.title}>
                            {simuladoGenerating ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Gerando questões...</> : <><Sparkles className="w-4 h-4 mr-2" />Gerar Simulado</>}
                          </Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>

                {/* Stats Overview */}
                {showSimuladoStatsView && simuladoStats && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><TrendingUp className="w-4 h-4 text-[#00F0FF]" />Estatísticas Gerais</CardTitle></CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                        <div className="text-center p-3 bg-[#121212] rounded-lg">
                          <p className="text-2xl font-bold text-[#007AFF]">{simuladoStats.total_simulados}</p>
                          <p className="text-xs text-[#A1A1AA]">Simulados</p>
                        </div>
                        <div className="text-center p-3 bg-[#121212] rounded-lg">
                          <p className="text-2xl font-bold text-[#00F0FF]">{simuladoStats.total_attempts}</p>
                          <p className="text-xs text-[#A1A1AA]">Tentativas</p>
                        </div>
                        <div className="text-center p-3 bg-[#121212] rounded-lg">
                          <p className={`text-2xl font-bold ${simuladoStats.accuracy_rate >= 70 ? 'text-green-400' : simuladoStats.accuracy_rate >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                            {simuladoStats.accuracy_rate}%
                          </p>
                          <p className="text-xs text-[#A1A1AA]">Taxa de Acerto</p>
                        </div>
                        <div className="text-center p-3 bg-[#121212] rounded-lg">
                          <p className="text-2xl font-bold text-purple-400">{simuladoStats.total_questions_answered}</p>
                          <p className="text-xs text-[#A1A1AA]">Questões</p>
                        </div>
                      </div>
                      {simuladoStats.by_banca && Object.keys(simuladoStats.by_banca).length > 0 && (
                        <div>
                          <p className="text-xs text-[#A1A1AA] mb-2 font-medium">Por Banca:</p>
                          <div className="space-y-2">
                            {Object.entries(simuladoStats.by_banca).map(([b, d]) => (
                              <div key={b} className="flex justify-between items-center text-sm">
                                <span>{b}</span>
                                <span className={d.accuracy >= 70 ? 'text-green-400' : d.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'}>{d.accuracy}% ({d.attempts} tent.)</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {simuladoStats.by_disciplina && Object.keys(simuladoStats.by_disciplina).length > 0 && (
                        <div className="mt-3">
                          <p className="text-xs text-[#A1A1AA] mb-2 font-medium">Por Disciplina:</p>
                          <div className="space-y-2">
                            {Object.entries(simuladoStats.by_disciplina).map(([d, data]) => (
                              <div key={d}>
                                <div className="flex justify-between text-sm mb-1"><span>{d}</span><span className={data.accuracy >= 70 ? 'text-green-400' : data.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'}>{data.accuracy}%</span></div>
                                <Progress value={data.accuracy} className="h-1.5" />
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Simulados Grid */}
                {simulados.length === 0 ? (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardContent className="p-12 text-center">
                      <ClipboardList className="w-12 h-12 text-[#3F3F46] mx-auto mb-4" />
                      <h4 className="text-lg font-medium mb-2">Nenhum simulado ainda</h4>
                      <p className="text-sm text-[#A1A1AA] mb-4">Importe um PDF com questões ou gere um simulado com IA</p>
                      <div className="flex gap-3 justify-center">
                        <Button variant="outline" onClick={() => setShowImportPdfDialog(true)} className="border-[#27272A]"><Upload className="w-4 h-4 mr-1" />Importar PDF</Button>
                        <Button onClick={() => setShowGenerateDialog(true)} className="bg-[#007AFF]"><Sparkles className="w-4 h-4 mr-1" />Gerar com IA</Button>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {simulados.map(sim => (
                      <Card key={sim.simulado_id} className="bg-[#0A0A0A] border-[#27272A] hover:border-[#3F3F46] transition-all">
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex-1 min-w-0">
                              <h4 className="font-medium text-sm truncate">{sim.title}</h4>
                              <div className="flex flex-wrap gap-1 mt-1">
                                {sim.banca && <Badge variant="outline" className="text-xs border-[#007AFF]/30 text-[#007AFF]">{sim.banca}</Badge>}
                                {sim.disciplina && <Badge variant="outline" className="text-xs border-purple-500/30 text-purple-400">{sim.disciplina}</Badge>}
                                {sim.concurso && <Badge variant="outline" className="text-xs border-[#00F0FF]/30 text-[#00F0FF]">{sim.concurso}</Badge>}
                              </div>
                            </div>
                            <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0" onClick={() => handleDeleteSimulado(sim.simulado_id)}><Trash2 className="w-3 h-3 text-red-500" /></Button>
                          </div>

                          <div className="flex items-center gap-3 text-xs text-[#A1A1AA] mb-3">
                            <span className="flex items-center gap-1"><ListChecks className="w-3 h-3" />{sim.questions_count} questões</span>
                            <span className="flex items-center gap-1"><CircleDot className="w-3 h-3" />{sim.source_type === "pdf_import" ? "PDF" : "IA"}</span>
                            {sim.attempts_count > 0 && <span className="flex items-center gap-1"><RotateCcw className="w-3 h-3" />{sim.attempts_count}x</span>}
                          </div>

                          {sim.best_score > 0 && (
                            <div className="mb-3">
                              <div className="flex justify-between text-xs mb-1">
                                <span className="text-[#A1A1AA]">Melhor nota</span>
                                <span className={sim.best_score >= 70 ? 'text-green-400' : sim.best_score >= 50 ? 'text-yellow-400' : 'text-red-400'}>{sim.best_score}%</span>
                              </div>
                              <Progress value={sim.best_score} className="h-1.5" />
                            </div>
                          )}

                          <div className="flex gap-2">
                            <Button size="sm" className="flex-1 bg-[#007AFF] text-xs" onClick={() => handleStartSimulado(sim)}>
                              <Play className="w-3 h-3 mr-1" />{sim.attempts_count > 0 ? "Refazer" : "Iniciar"}
                            </Button>
                            <Button size="sm" variant="outline" className="border-[#27272A] text-xs" onClick={() => handleViewSimulado(sim)}>
                              <Eye className="w-3 h-3 mr-1" />Ver
                            </Button>
                            {sim.attempts_count > 0 && (
                              <Button size="sm" variant="outline" className="border-[#27272A] text-xs" onClick={() => handleViewResults(sim)}>
                                <BarChart3 className="w-3 h-3 mr-1" />Resultado
                              </Button>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}
          </TabsContent>

          {/* ========== FOCO TAB ========== */}
          <TabsContent value="foco" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="space-y-4">
                <PomodoroTimer notebooks={notebooks} onComplete={fetchAllData} />
                <QuestionLogger notebooks={notebooks} onLog={fetchAllData} />
              </div>
              <div className="space-y-4">
                <StudyAIChat notebooks={notebooks} selectedNotebook={selectedNotebook} />
              </div>
            </div>

            {/* Focus Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardContent className="p-4 text-center">
                  <p className="text-xs text-[#A1A1AA] mb-1">Hoje</p>
                  <p className="text-2xl font-bold text-red-400">{focusStats?.today?.total_minutes || 0}min</p>
                  <p className="text-xs text-[#A1A1AA]">{focusStats?.today?.sessions || 0} sessões</p>
                </CardContent>
              </Card>
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardContent className="p-4 text-center">
                  <p className="text-xs text-[#A1A1AA] mb-1">Esta Semana</p>
                  <p className="text-2xl font-bold text-[#00F0FF]">{focusStats?.week?.total_minutes || 0}min</p>
                  <p className="text-xs text-[#A1A1AA]">{focusStats?.week?.sessions || 0} sessões</p>
                </CardContent>
              </Card>
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardContent className="p-4 text-center">
                  <p className="text-xs text-[#A1A1AA] mb-1">Total</p>
                  <p className="text-2xl font-bold text-green-400">{focusStats?.all_time?.total_hours || 0}h</p>
                  <p className="text-xs text-[#A1A1AA]">{focusStats?.all_time?.sessions || 0} sessões</p>
                </CardContent>
              </Card>
            </div>

            {/* Question Stats */}
            {questionStats && totalQuestions > 0 && (
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><BarChart3 className="w-4 h-4 text-purple-400" />Estatísticas de Questões</CardTitle></CardHeader>
                <CardContent>
                  <div className="grid grid-cols-4 gap-3 text-center">
                    <div><p className="text-2xl font-bold text-white">{totalQuestions}</p><p className="text-xs text-[#A1A1AA]">Total</p></div>
                    <div><p className="text-2xl font-bold text-green-400">{questionStats.correct || 0}</p><p className="text-xs text-[#A1A1AA]">Acertos</p></div>
                    <div><p className="text-2xl font-bold text-red-400">{questionStats.incorrect || 0}</p><p className="text-xs text-[#A1A1AA]">Erros</p></div>
                    <div><p className={`text-2xl font-bold ${accuracy >= 70 ? 'text-green-400' : accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{accuracy}%</p><p className="text-xs text-[#A1A1AA]">Acerto</p></div>
                  </div>
                  <Progress value={accuracy} className="mt-3 h-2" />
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ===== REDAÇÃO TAB ===== */}
          <TabsContent value="redacao" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Enviar Redação */}
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2"><PenTool className="w-4 h-4 text-purple-400" />Corrigir Redação com IA</CardTitle>
                  <CardDescription className="text-xs">Envie sua redação (PDF, imagem ou texto) para correção detalhada</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className={`border-2 border-dashed rounded-lg p-6 text-center ${redacaoFile ? 'border-purple-500 bg-purple-500/10' : 'border-[#27272A]'}`}>
                    {redacaoFile ? (
                      <div className="flex items-center justify-center gap-2">
                        <FileText className="w-5 h-5 text-purple-400" />
                        <span className="text-sm text-purple-300">{redacaoFile.name}</span>
                        <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => setRedacaoFile(null)}><XCircle className="w-4 h-4 text-red-400" /></Button>
                      </div>
                    ) : (
                      <label className="cursor-pointer">
                        <Upload className="w-8 h-8 mx-auto text-[#A1A1AA] mb-2" />
                        <p className="text-sm text-[#A1A1AA]">Clique para selecionar arquivo</p>
                        <p className="text-xs text-[#52525B]">PDF, imagem ou texto</p>
                        <input type="file" accept=".pdf,.txt,.doc,.docx,image/*" className="hidden" onChange={e => setRedacaoFile(e.target.files?.[0] || null)} />
                      </label>
                    )}
                  </div>
                  <Button onClick={handleRedacaoCorrection} disabled={!redacaoFile || redacaoLoading} className="w-full bg-purple-600 hover:bg-purple-700">
                    {redacaoLoading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Corrigindo...</> : <><Sparkles className="w-4 h-4 mr-2" />Corrigir Redação</>}
                  </Button>
                </CardContent>
              </Card>

              {/* Sortear Tema */}
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2"><Lightbulb className="w-4 h-4 text-yellow-400" />Sortear Tema de Redação</CardTitle>
                  <CardDescription className="text-xs">Temas com probabilidade de cair em concursos</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button onClick={handleRandomTheme} disabled={themeLoading} className="w-full bg-yellow-600 hover:bg-yellow-700 text-black">
                    {themeLoading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Sorteando...</> : <><Zap className="w-4 h-4 mr-2" />Sortear Tema</>}
                  </Button>
                  {randomTheme && (
                    <div className="bg-[#121212] p-4 rounded-lg space-y-3">
                      <h3 className="font-bold text-sm text-yellow-400">{randomTheme.tema}</h3>
                      <div className="flex gap-2 flex-wrap">
                        <Badge variant="outline" className="text-[10px] border-purple-500 text-purple-400">{randomTheme.tipo_texto}</Badge>
                        <Badge variant="outline" className="text-[10px] border-blue-500 text-blue-400">{randomTheme.banca_relacionada}</Badge>
                        <Badge variant="outline" className="text-[10px] border-orange-500 text-orange-400">{randomTheme.nivel_dificuldade}</Badge>
                      </div>
                      <p className="text-xs text-[#A1A1AA]">{randomTheme.contexto}</p>
                      {randomTheme.textos_motivadores?.length > 0 && (
                        <div className="bg-[#0A0A0A] p-3 rounded border border-[#27272A]">
                          <p className="text-[10px] text-[#52525B] mb-1">Textos Motivadores:</p>
                          {randomTheme.textos_motivadores.map((t, i) => <p key={i} className="text-xs text-[#A1A1AA] italic mb-1">"{t}"</p>)}
                        </div>
                      )}
                      {randomTheme.dicas?.length > 0 && (
                        <div>
                          <p className="text-[10px] text-[#52525B] mb-1">Dicas:</p>
                          {randomTheme.dicas.map((d, i) => <p key={i} className="text-xs text-green-300">✓ {d}</p>)}
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Resultado da Correção */}
            {showRedacaoResult && redacaoCorrection && (
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-green-400" />Resultado da Correção</CardTitle>
                  <div className="flex items-center gap-3 mt-2">
                    <div className="text-3xl font-bold text-[#00F0FF]">{redacaoCorrection.nota_geral}/{redacaoCorrection.nota_maxima}</div>
                    <Badge className="bg-purple-500/20 text-purple-300">{redacaoCorrection.nivel}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-2">
                    {(redacaoCorrection.competencias || []).map((c, i) => (
                      <Card key={i} className="bg-[#121212] border-[#27272A] p-3">
                        <p className="text-[10px] text-[#A1A1AA] mb-1">{c.nome}</p>
                        <p className="text-lg font-bold text-[#00F0FF]">{c.nota}/{c.nota_maxima}</p>
                        <p className="text-[10px] text-[#52525B] mt-1">{c.comentario}</p>
                      </Card>
                    ))}
                  </div>
                  {redacaoCorrection.pontos_fortes?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-green-400 mb-1">✅ Pontos Fortes</p>
                      {redacaoCorrection.pontos_fortes.map((p, i) => <p key={i} className="text-xs text-[#A1A1AA]">• {p}</p>)}
                    </div>
                  )}
                  {redacaoCorrection.pontos_melhorar?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-orange-400 mb-1">🔧 Pontos a Melhorar</p>
                      {redacaoCorrection.pontos_melhorar.map((p, i) => <p key={i} className="text-xs text-[#A1A1AA]">• {p}</p>)}
                    </div>
                  )}
                  {redacaoCorrection.erros_gramaticais?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-red-400 mb-1">📝 Erros Gramaticais</p>
                      {redacaoCorrection.erros_gramaticais.map((e, i) => (
                        <div key={i} className="bg-[#121212] p-2 rounded mb-1">
                          <p className="text-xs text-red-300 line-through">{e.trecho}</p>
                          <p className="text-xs text-green-300">{e.correcao}</p>
                          <p className="text-[10px] text-[#52525B]">{e.explicacao}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  {redacaoCorrection.dicas_estrategicas?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-blue-400 mb-1">💡 Dicas Estratégicas</p>
                      {redacaoCorrection.dicas_estrategicas.map((d, i) => <p key={i} className="text-xs text-[#A1A1AA]">• {d}</p>)}
                    </div>
                  )}
                  <Button variant="outline" size="sm" onClick={() => setShowRedacaoResult(false)}>Fechar</Button>
                </CardContent>
              </Card>
            )}

            {/* Histórico */}
            <Card className="bg-[#0A0A0A] border-[#27272A]">
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2"><BookMarked className="w-4 h-4 text-[#00F0FF]" />Histórico de Correções</CardTitle>
              </CardHeader>
              <CardContent>
                {redacaoHistory.length === 0 ? (
                  <div className="text-center py-6">
                    <PenTool className="w-8 h-8 text-[#52525B] mx-auto mb-2" />
                    <p className="text-sm text-[#A1A1AA]">Nenhuma correção ainda</p>
                    <Button variant="link" size="sm" onClick={fetchRedacaoHistory} className="text-[#00F0FF] mt-1">Carregar histórico</Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {redacaoHistory.map(r => (
                      <div key={r.correction_id} className="flex items-center gap-3 p-2 bg-[#121212] rounded-lg cursor-pointer hover:bg-[#1A1A2E]" onClick={() => { setRedacaoCorrection(r.correction); setShowRedacaoResult(true); }}>
                        <FileText className="w-4 h-4 text-purple-400" />
                        <div className="flex-1">
                          <p className="text-sm">{r.filename}</p>
                          <p className="text-[10px] text-[#52525B]">{new Date(r.created_at).toLocaleDateString('pt-BR')}</p>
                        </div>
                        <span className="text-sm font-bold text-[#00F0FF]">{r.correction?.nota_geral}/{r.correction?.nota_maxima}</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

        </Tabs>

        {/* ========== EDITAL RESULT DIALOG (Editable) ========== */}
        <Dialog open={showEditalResultDialog} onOpenChange={setShowEditalResultDialog}>
          <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-green-400" />Programa Criado com Sucesso!</DialogTitle>
              <DialogDescription>Revise e personalize as disciplinas antes de finalizar.</DialogDescription>
            </DialogHeader>
            {editalResult && (
              <div className="space-y-4 py-2">
                {/* Editable Program Name */}
                <div>
                  <Label className="text-sm font-medium">Nome do Programa</Label>
                  <Input value={editedProgramName} onChange={e => setEditedProgramName(e.target.value)} className="bg-[#121212] border-[#27272A] mt-1" placeholder="Nome do programa de estudos" />
                </div>

                {/* Concurso Info */}
                {editalResult.concurso && (
                  <Card className="bg-[#121212] border-[#27272A]">
                    <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><GraduationCap className="w-4 h-4 text-purple-400" />Informações do Concurso</CardTitle></CardHeader>
                    <CardContent className="text-xs space-y-1">
                      {editalResult.concurso.nome && <p><span className="text-[#A1A1AA]">Concurso:</span> <span className="text-white font-medium">{editalResult.concurso.nome}</span></p>}
                      {editalResult.concurso.orgao && <p><span className="text-[#A1A1AA]">Órgão:</span> <span className="text-white">{editalResult.concurso.orgao}</span></p>}
                      {editalResult.concurso.banca && <p><span className="text-[#A1A1AA]">Banca:</span> <span className="text-white">{editalResult.concurso.banca}</span></p>}
                      {editalResult.concurso.cargo && <p><span className="text-[#A1A1AA]">Cargo:</span> <span className="text-white">{editalResult.concurso.cargo}</span></p>}
                      {editalResult.concurso.vagas && <p><span className="text-[#A1A1AA]">Vagas:</span> <span className="text-white">{editalResult.concurso.vagas}</span></p>}
                      {editalResult.concurso.remuneracao && <p><span className="text-[#A1A1AA]">Remuneração:</span> <span className="text-green-400 font-medium">{editalResult.concurso.remuneracao}</span></p>}
                    </CardContent>
                  </Card>
                )}

                {/* Editable Disciplines */}
                <Card className="bg-[#121212] border-[#27272A]">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm flex items-center gap-2"><BookOpen className="w-4 h-4 text-blue-400" />{editedDisciplinas.length} Disciplinas</CardTitle>
                      <Badge variant="outline" className="text-[10px] border-purple-500 text-purple-400"><Edit3 className="w-3 h-3 mr-1" />Editável</Badge>
                    </div>
                    <p className="text-[10px] text-[#A1A1AA]">Ajuste pesos, dificuldade e sua dificuldade pessoal para personalizar o cronograma.</p>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {editedDisciplinas.map((disc, i) => (
                        <div key={i} className="p-3 bg-[#0A0A0A] rounded-lg border border-[#27272A] space-y-2">
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: disc.color || '#007AFF' }} />
                            <Input value={disc.name} onChange={e => { const u = [...editedDisciplinas]; u[i] = {...u[i], name: e.target.value}; setEditedDisciplinas(u); }}
                              className="bg-[#121212] border-[#27272A] h-7 text-xs font-medium flex-1" />
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <Label className="text-[10px] text-[#A1A1AA]">Peso (edital)</Label>
                              <Select value={String(disc.weight || 1)} onValueChange={v => { const u = [...editedDisciplinas]; u[i] = {...u[i], weight: parseInt(v)}; setEditedDisciplinas(u); }}>
                                <SelectTrigger className="bg-[#121212] border-[#27272A] h-7 text-xs"><SelectValue /></SelectTrigger>
                                <SelectContent className="bg-[#0A0A0A] border-[#27272A]">
                                  {[1,2,3,4,5].map(w => <SelectItem key={w} value={String(w)}>Peso {w}</SelectItem>)}
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <Label className="text-[10px] text-[#A1A1AA]">Minha dificuldade</Label>
                              <Select value={disc.user_difficulty || disc.dificuldade || "media"} onValueChange={v => { const u = [...editedDisciplinas]; u[i] = {...u[i], user_difficulty: v, dificuldade: v}; setEditedDisciplinas(u); }}>
                                <SelectTrigger className="bg-[#121212] border-[#27272A] h-7 text-xs"><SelectValue /></SelectTrigger>
                                <SelectContent className="bg-[#0A0A0A] border-[#27272A]">
                                  <SelectItem value="baixa">Fácil</SelectItem>
                                  <SelectItem value="media">Normal</SelectItem>
                                  <SelectItem value="alta">Difícil</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                          {disc.num_questoes_edital > 0 && <p className="text-[10px] text-[#52525B]">{disc.num_questoes_edital} questões no edital</p>}
                          {disc.conteudo_programatico?.length > 0 ? (
                            <details className="mt-1">
                              <summary className="text-[10px] text-purple-400 cursor-pointer hover:underline">{disc.conteudo_programatico.length} assuntos no conteúdo programático</summary>
                              <div className="mt-1 space-y-1 ml-1">
                                {disc.conteudo_programatico.map((item, ci) => (
                                  <div key={ci} className="pl-2 border-l border-purple-500/30">
                                    <p className="text-[10px] font-medium text-[#A1A1AA]">{ci + 1}. {item.assunto}</p>
                                    {item.subtopicos?.length > 0 && (
                                      <div className="flex flex-wrap gap-0.5 ml-2 mt-0.5">
                                        {item.subtopicos.map((sub, si) => <Badge key={si} variant="outline" className="text-[8px] border-[#27272A] text-[#52525B]">{sub}</Badge>)}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </details>
                          ) : disc.topicos?.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {disc.topicos.map((t, ti) => <Badge key={ti} variant="outline" className="text-[9px] border-[#27272A] text-[#71717A]">{t}</Badge>)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Strategy */}
                {editalResult.estrategia && (
                  <Card className="bg-[#121212] border-[#27272A]">
                    <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Target className="w-4 h-4 text-green-400" />Estratégia de Estudo</CardTitle></CardHeader>
                    <CardContent className="text-xs space-y-2">
                      {editalResult.estrategia.resumo && <p className="text-[#A1A1AA]">{editalResult.estrategia.resumo}</p>}
                      {editalResult.estrategia.dicas_gerais?.length > 0 && (
                        <ul className="list-disc ml-4 text-[#A1A1AA] space-y-1">
                          {editalResult.estrategia.dicas_gerais.map((d, i) => <li key={i}>{d}</li>)}
                        </ul>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Action Buttons */}
                <div className="space-y-2">
                  <Button onClick={handleSaveDisciplinas} disabled={savingDisciplinas} className="w-full bg-purple-600 hover:bg-purple-700">
                    {savingDisciplinas ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Salvando e regenerando cronograma...</> : <><CheckCircle2 className="w-4 h-4 mr-2" />Salvar Personalizações e Regenerar Cronograma</>}
                  </Button>
                  <Button variant="outline" onClick={() => { setShowEditalResultDialog(false); if (editalResult.program) handleViewCronograma(editalResult.program.program_id); }} className="w-full border-[#27272A]">
                    <LayoutGrid className="w-4 h-4 mr-2" />Ver Cronograma Atual
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* ========== CRONOGRAMA DIALOG (Enhanced with Indicators + Simulado) ========== */}
        <Dialog open={showCronogramaDialog} onOpenChange={setShowCronogramaDialog}>
          <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><LayoutGrid className="w-5 h-5 text-purple-400" />Cronograma de Estudos</DialogTitle>
              <DialogDescription>{cronogramaData?.program?.name || 'Programa de Estudos'}</DialogDescription>
            </DialogHeader>
            {cronogramaLoading ? (
              <div className="flex flex-col items-center justify-center py-10">
                <Loader2 className="w-8 h-8 animate-spin text-purple-400 mb-3" />
                <p className="text-sm text-[#A1A1AA]">Carregando cronograma...</p>
              </div>
            ) : cronogramaData && (
              <div className="space-y-4 py-2">
                {/* Action Buttons */}
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" className="border-[#27272A] text-xs" onClick={() => handleExportCronograma('pdf')}>
                    <Download className="w-3 h-3 mr-1" />Exportar PDF
                  </Button>
                  <Button variant="outline" size="sm" className="border-[#27272A] text-xs" onClick={() => handleExportCronograma('image')}>
                    <Image className="w-3 h-3 mr-1" />Exportar Imagem
                  </Button>
                  <Button variant="outline" size="sm" className="border-[#27272A] text-xs" onClick={() => handleCreateReminders(cronogramaData.program?.program_id)}>
                    <BellRing className="w-3 h-3 mr-1" />Ativar Lembretes
                  </Button>
                  {cronogramaData.program?.program_id && (
                    <Button variant="outline" size="sm" className="border-[#27272A] text-xs" onClick={() => handleViewProgress(cronogramaData.program.program_id)}>
                      <TrendingUp className="w-3 h-3 mr-1" />Comparar Progresso
                    </Button>
                  )}
                  {cronogramaData.program?.source_type === "edital_import" && cronogramaData.program?.program_id && (
                    <Button variant="outline" size="sm" className="border-purple-500/30 text-purple-400 text-xs" onClick={() => { setShowCronogramaDialog(false); handleViewVerticalizado(cronogramaData.program.program_id); }}>
                      <Layers className="w-3 h-3 mr-1" />Edital Verticalizado
                    </Button>
                  )}
                </div>

                <div ref={cronogramaRef}>
                {/* Study Indicators per Discipline */}
                {studyIndicators?.indicators?.length > 0 && (
                  <Card className="bg-[#121212] border-[#27272A]">
                    <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><BarChart3 className="w-4 h-4 text-green-400" />Indicadores de Estudo por Matéria</CardTitle></CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {studyIndicators.indicators.map((ind, i) => (
                          <div key={i} className="p-3 bg-[#0A0A0A] rounded-lg border border-[#27272A]">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: ind.color }} />
                                <span className="text-xs font-medium">{ind.name}</span>
                              </div>
                              <div className="flex gap-1">
                                <Badge variant="outline" className="text-[10px] border-yellow-500 text-yellow-400">P{ind.weight}</Badge>
                                {ind.user_difficulty === "alta" && <Badge variant="outline" className="text-[10px] border-red-500 text-red-400">Difícil</Badge>}
                              </div>
                            </div>
                            <div className="grid grid-cols-5 gap-2 text-center">
                              <div>
                                <p className="text-lg font-bold text-white">{ind.study_hours}h</p>
                                <p className="text-[9px] text-[#71717A]">Estudado</p>
                              </div>
                              <div>
                                <p className="text-lg font-bold text-purple-400">{ind.total_questions_answered}</p>
                                <p className="text-[9px] text-[#71717A]">Questões</p>
                              </div>
                              <div>
                                <p className={`text-lg font-bold ${ind.accuracy >= 70 ? 'text-green-400' : ind.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{ind.accuracy}%</p>
                                <p className="text-[9px] text-[#71717A]">Acerto</p>
                              </div>
                              <div>
                                <p className="text-lg font-bold text-blue-400">{ind.flashcards_total}</p>
                                <p className="text-[9px] text-[#71717A]">Flashcards</p>
                              </div>
                              <div>
                                <p className="text-lg font-bold text-[#A1A1AA]">{ind.notes_count}</p>
                                <p className="text-[9px] text-[#71717A]">Notas</p>
                              </div>
                            </div>
                            <div className="mt-2">
                              <div className="flex justify-between text-[10px] mb-1">
                                <span className="text-[#71717A]">Progresso questões</span>
                                <span className="text-[#A1A1AA]">{ind.question_progress}%</span>
                              </div>
                              <Progress value={ind.question_progress} className="h-1.5" />
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Weight Distribution */}
                <Card className="bg-[#121212] border-[#27272A]">
                  <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Scale className="w-4 h-4 text-yellow-400" />Distribuição por Peso</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {(cronogramaData.disciplinas || []).map((disc, i) => (
                        <div key={i} className="flex items-center gap-3">
                          <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: disc.color }} />
                          <span className="text-xs font-medium w-40 truncate">{disc.disciplina}</span>
                          <div className="flex-1">
                            <div className="h-3 bg-[#27272A] rounded-full overflow-hidden">
                              <div className="h-full rounded-full transition-all" style={{ width: `${disc.percentual}%`, backgroundColor: disc.color }} />
                            </div>
                          </div>
                          <span className="text-xs text-[#A1A1AA] w-12 text-right">{disc.percentual}%</span>
                          <Badge variant="outline" className={`text-[10px] w-14 justify-center ${disc.dificuldade === 'alta' ? 'border-red-500 text-red-400' : disc.dificuldade === 'media' ? 'border-yellow-500 text-yellow-400' : 'border-green-500 text-green-400'}`}>{disc.dificuldade}</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Conteúdo Programático por Disciplina */}
                {(cronogramaData.disciplinas || []).some(d => d.conteudo_programatico?.length > 0 || d.topicos?.length > 0) && (
                  <Card className="bg-[#121212] border-[#27272A]">
                    <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><BookOpen className="w-4 h-4 text-purple-400" />Conteúdo Programático por Disciplina</CardTitle></CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {(cronogramaData.disciplinas || []).map((disc, i) => {
                          const hasConteudo = disc.conteudo_programatico?.length > 0;
                          const hasTopicos = disc.topicos?.length > 0;
                          if (!hasConteudo && !hasTopicos) return null;
                          const isExpanded = expandedDisciplinas.has(`cron_${i}`);
                          return (
                            <div key={i} className="border border-[#27272A] rounded-lg overflow-hidden">
                              <button
                                className="w-full flex items-center justify-between px-3 py-2 bg-[#1A1A1A] hover:bg-[#222] transition-colors"
                                onClick={() => toggleDisciplinaExpanded(`cron_${i}`)}
                              >
                                <div className="flex items-center gap-2">
                                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: disc.color }} />
                                  <span className="text-xs font-medium text-white">{disc.disciplina}</span>
                                  <Badge variant="outline" className="text-[9px] border-[#3F3F46] text-[#A1A1AA]">
                                    {hasConteudo ? `${disc.conteudo_programatico.length} assuntos` : `${disc.topicos.length} tópicos`}
                                  </Badge>
                                </div>
                                {isExpanded ? <ChevronUp className="w-3 h-3 text-[#A1A1AA]" /> : <ChevronDown className="w-3 h-3 text-[#A1A1AA]" />}
                              </button>
                              {isExpanded && (
                                <div className="p-3 space-y-2">
                                  {hasConteudo ? (
                                    disc.conteudo_programatico.map((item, j) => (
                                      <div key={j} className="pl-2 border-l-2 border-[#27272A]">
                                        <p className="text-xs font-medium text-white mb-1">{j + 1}. {item.assunto}</p>
                                        {item.subtopicos?.length > 0 && (
                                          <div className="flex flex-wrap gap-1 ml-3">
                                            {item.subtopicos.map((sub, k) => (
                                              <Badge key={k} variant="outline" className="text-[9px] border-[#27272A] text-[#71717A]">{sub}</Badge>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    ))
                                  ) : (
                                    <div className="flex flex-wrap gap-1">
                                      {disc.topicos.map((t, j) => (
                                        <Badge key={j} variant="outline" className="text-[9px] border-[#27272A] text-[#71717A]">{t}</Badge>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Weekly Schedule */}
                <Card className="bg-[#121212] border-[#27272A]">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm flex items-center gap-2"><Calendar className="w-4 h-4 text-blue-400" />Cronograma Semanal</CardTitle>
                      <div className="flex gap-2">
                        <Badge className="bg-blue-500/20 text-blue-400 text-[9px]">📖 Teoria</Badge>
                        <Badge className="bg-purple-500/20 text-purple-400 text-[9px]">📝 Questões</Badge>
                        <Badge className="bg-green-500/20 text-green-400 text-[9px]">🔄 Revisão</Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {(cronogramaData.cronograma || []).map((day, di) => (
                        <div key={di} className="border border-[#27272A] rounded-lg overflow-hidden">
                          <div className="flex items-center justify-between bg-[#1A1A1A] px-3 py-2">
                            <span className="text-sm font-bold text-white">{day.day_label}</span>
                            <Badge variant="outline" className="text-[10px] border-[#3F3F46] text-[#A1A1AA]">
                              <Clock className="w-3 h-3 mr-1" />{Math.floor(day.total_minutes / 60)}h{day.total_minutes % 60 > 0 ? `${day.total_minutes % 60}min` : ''}
                            </Badge>
                          </div>
                          <div className="p-2 space-y-1">
                            {(day.blocos || []).map((bloco, bi) => (
                              <div key={bi} className={`flex items-start gap-2 p-2 rounded-md ${
                                (bloco.tipo_estudo || '').includes('Teoria') ? 'bg-blue-950/30 border border-blue-500/10' :
                                (bloco.tipo_estudo || '').includes('Questões') ? 'bg-purple-950/30 border border-purple-500/10' :
                                (bloco.tipo_estudo || '').includes('Revisão') ? 'bg-green-950/30 border border-green-500/10' :
                                'bg-[#0A0A0A]'
                              }`}>
                                <div className="w-1.5 min-h-[2rem] rounded-full flex-shrink-0 mt-0.5" style={{ backgroundColor: bloco.disciplina_color || '#007AFF' }} />
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs font-medium text-white truncate">{bloco.disciplina_nome || bloco.notebook_id}</p>
                                  <p className={`text-[10px] font-medium ${
                                    (bloco.tipo_estudo || '').includes('Teoria') ? 'text-blue-400' :
                                    (bloco.tipo_estudo || '').includes('Questões') ? 'text-purple-400' :
                                    (bloco.tipo_estudo || '').includes('Revisão') ? 'text-green-400' :
                                    'text-[#A1A1AA]'
                                  }`}>{bloco.tipo_estudo || 'Teoria + Questões'}</p>
                                  {bloco.assuntos_foco && bloco.assuntos_foco.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-1">
                                      {bloco.assuntos_foco.map((assunto, ai) => (
                                        <Badge key={ai} variant="outline" className="text-[9px] border-[#3F3F46] text-[#71717A]">{assunto}</Badge>
                                      ))}
                                    </div>
                                  )}
                                </div>
                                <div className="text-right flex-shrink-0">
                                  <p className="text-xs text-[#A1A1AA]">{bloco.start_time} - {bloco.end_time}</p>
                                  <Badge variant="outline" className={`text-[10px] ${bloco.prioridade === 'alta' ? 'border-red-500 text-red-400' : bloco.prioridade === 'media' ? 'border-yellow-500 text-yellow-400' : 'border-green-500 text-green-400'}`}>{bloco.prioridade}</Badge>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Strategy */}
                {cronogramaData.estrategia && cronogramaData.estrategia.resumo && (
                  <Card className="bg-[#121212] border-[#27272A]">
                    <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Lightbulb className="w-4 h-4 text-yellow-400" />Estratégia Recomendada</CardTitle></CardHeader>
                    <CardContent className="text-xs space-y-2">
                      <p className="text-[#A1A1AA]">{cronogramaData.estrategia.resumo}</p>
                      {cronogramaData.estrategia.fase_1 && <p><span className="text-blue-400 font-medium">Fase 1:</span> <span className="text-[#A1A1AA]">{cronogramaData.estrategia.fase_1}</span></p>}
                      {cronogramaData.estrategia.fase_2 && <p><span className="text-yellow-400 font-medium">Fase 2:</span> <span className="text-[#A1A1AA]">{cronogramaData.estrategia.fase_2}</span></p>}
                      {cronogramaData.estrategia.fase_3 && <p><span className="text-green-400 font-medium">Fase 3:</span> <span className="text-[#A1A1AA]">{cronogramaData.estrategia.fase_3}</span></p>}
                      {cronogramaData.estrategia.materias_prioritarias?.length > 0 && (
                        <div className="mt-2">
                          <p className="text-red-400 font-medium mb-1">Matérias Prioritárias:</p>
                          <div className="flex flex-wrap gap-1">
                            {cronogramaData.estrategia.materias_prioritarias.map((m, i) => (
                              <Badge key={i} variant="outline" className="text-[10px] border-red-500 text-red-400">{m}</Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Action: Generate Simulado from Edital */}
                </div>{/* end cronogramaRef */}
                {cronogramaData.program?.source_type === "edital_import" && (
                  <Button onClick={() => {
                    const concurso = cronogramaData.program?.edital_data?.concurso;
                    setEditalSimuladoForm({
                      title: `Simulado - ${concurso?.nome || cronogramaData.program?.name || 'Concurso'}`,
                      disciplina: "", question_type: "multipla_escolha", num_questions: 10, difficulty: "medio"
                    });
                    setShowSimuladoFromEdital(true);
                  }} className="w-full bg-blue-600 hover:bg-blue-700">
                    <ClipboardList className="w-4 h-4 mr-2" />Gerar Simulado deste Concurso
                  </Button>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* ========== SIMULADO FROM EDITAL DIALOG ========== */}
        <Dialog open={showSimuladoFromEdital} onOpenChange={setShowSimuladoFromEdital}>
          <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><ClipboardList className="w-5 h-5 text-blue-400" />Gerar Simulado do Concurso</DialogTitle>
              <DialogDescription>
                {cronogramaData?.program?.edital_data?.concurso?.banca && `Banca: ${cronogramaData.program.edital_data.concurso.banca}`}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <Label className="text-sm">Título do Simulado</Label>
                <Input value={editalSimuladoForm.title} onChange={e => setEditalSimuladoForm({...editalSimuladoForm, title: e.target.value})}
                  className="bg-[#121212] border-[#27272A] mt-1" />
              </div>
              <div>
                <Label className="text-sm">Disciplina (opcional)</Label>
                <Select value={editalSimuladoForm.disciplina} onValueChange={v => setEditalSimuladoForm({...editalSimuladoForm, disciplina: v})}>
                  <SelectTrigger className="bg-[#121212] border-[#27272A] mt-1"><SelectValue placeholder="Todas as disciplinas" /></SelectTrigger>
                  <SelectContent className="bg-[#0A0A0A] border-[#27272A]">
                    <SelectItem value=" ">Todas as disciplinas</SelectItem>
                    {(cronogramaData?.notebooks || []).map(nb => (
                      <SelectItem key={nb.notebook_id} value={nb.name}>{nb.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <Label className="text-[10px]">Tipo</Label>
                  <Select value={editalSimuladoForm.question_type} onValueChange={v => setEditalSimuladoForm({...editalSimuladoForm, question_type: v})}>
                    <SelectTrigger className="bg-[#121212] border-[#27272A] h-8 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#0A0A0A] border-[#27272A]">
                      <SelectItem value="multipla_escolha">Múlt. Escolha</SelectItem>
                      <SelectItem value="certo_errado">Certo/Errado</SelectItem>
                      <SelectItem value="misto">Misto</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-[10px]">Questões</Label>
                  <Select value={String(editalSimuladoForm.num_questions)} onValueChange={v => setEditalSimuladoForm({...editalSimuladoForm, num_questions: parseInt(v)})}>
                    <SelectTrigger className="bg-[#121212] border-[#27272A] h-8 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#0A0A0A] border-[#27272A]">
                      {[5,10,15,20,30].map(n => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-[10px]">Dificuldade</Label>
                  <Select value={editalSimuladoForm.difficulty} onValueChange={v => setEditalSimuladoForm({...editalSimuladoForm, difficulty: v})}>
                    <SelectTrigger className="bg-[#121212] border-[#27272A] h-8 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#0A0A0A] border-[#27272A]">
                      <SelectItem value="facil">Fácil</SelectItem>
                      <SelectItem value="medio">Médio</SelectItem>
                      <SelectItem value="dificil">Difícil</SelectItem>
                      <SelectItem value="misto">Misto</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button onClick={handleGenerateSimuladoFromEdital} disabled={editalSimuladoGenerating || !editalSimuladoForm.title} className="w-full bg-blue-600 hover:bg-blue-700">
                {editalSimuladoGenerating ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Gerando simulado...</> : <><Sparkles className="w-4 h-4 mr-2" />Gerar Simulado com IA</>}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* ========== CARGO SELECTION DIALOG ========== */}
        <Dialog open={showCargoSelection} onOpenChange={setShowCargoSelection}>
          <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><FileUp className="w-5 h-5 text-purple-400" />Selecione o Cargo</DialogTitle>
              <DialogDescription>
                {editalAnalysis?.concurso?.nome && <span className="text-purple-300">{editalAnalysis.concurso.nome}</span>}
                {editalAnalysis?.concurso?.banca && <span className="text-[#A1A1AA]"> | Banca: {editalAnalysis.concurso.banca}</span>}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <p className="text-xs text-[#A1A1AA]">Este edital possui {editalAnalysis?.cargos?.length || 0} cargos. Selecione o cargo desejado:</p>
              {(editalAnalysis?.cargos || []).map((cargo, idx) => (
                <Card key={idx} className={`bg-[#121212] border-[#27272A] p-4 cursor-pointer hover:border-purple-500 transition-colors ${selectedCargoIndex === idx ? 'border-purple-500 bg-purple-500/10' : ''}`}
                  onClick={() => setSelectedCargoIndex(idx)}>
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-medium text-sm text-white">{cargo.nome}</h3>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {cargo.vagas && <Badge variant="outline" className="text-[10px] border-green-500 text-green-400">Vagas: {cargo.vagas}</Badge>}
                        {cargo.remuneracao && <Badge variant="outline" className="text-[10px] border-yellow-500 text-yellow-400">{cargo.remuneracao}</Badge>}
                        {cargo.escolaridade && <Badge variant="outline" className="text-[10px] border-blue-500 text-blue-400">{cargo.escolaridade}</Badge>}
                      </div>
                      <p className="text-xs text-[#A1A1AA] mt-2">{(cargo.disciplinas || []).length} disciplinas</p>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(cargo.disciplinas || []).slice(0, 5).map((d, di) => (
                          <Badge key={di} variant="outline" className="text-[9px] border-[#3F3F46] text-[#A1A1AA]">
                            {d.nome} {d.peso ? `(P${d.peso})` : ''}
                          </Badge>
                        ))}
                        {(cargo.disciplinas || []).length > 5 && <Badge variant="outline" className="text-[9px] border-[#3F3F46] text-[#52525B]">+{(cargo.disciplinas || []).length - 5}</Badge>}
                      </div>
                    </div>
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${selectedCargoIndex === idx ? 'border-purple-500 bg-purple-500' : 'border-[#3F3F46]'}`}>
                      {selectedCargoIndex === idx && <CheckCircle2 className="w-3 h-3 text-white" />}
                    </div>
                  </div>
                </Card>
              ))}
              
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-sm font-medium">Horas por dia</Label>
                  <Select value={String(editalForm.hours_per_day)} onValueChange={v => setEditalForm({...editalForm, hours_per_day: parseFloat(v)})}>
                    <SelectTrigger className="bg-[#121212] border-[#27272A] mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#0A0A0A] border-[#27272A]">
                      {[1,2,3,4,5,6,7,8,10,12].map(h => <SelectItem key={h} value={String(h)}>{h}h</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-sm font-medium">Dias por semana</Label>
                  <Select value={String(editalForm.days_per_week)} onValueChange={v => setEditalForm({...editalForm, days_per_week: parseInt(v)})}>
                    <SelectTrigger className="bg-[#121212] border-[#27272A] mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#0A0A0A] border-[#27272A]">
                      {[3,4,5,6,7].map(d => <SelectItem key={d} value={String(d)}>{d} dias</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <Button onClick={() => handleCreateFromCargo(editalAnalysis?.analysis_id, selectedCargoIndex)} disabled={creatingFromCargo} className="w-full bg-purple-600 hover:bg-purple-700">
                {creatingFromCargo ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Criando programa...</> : <><Sparkles className="w-4 h-4 mr-2" />Gerar Programa para este Cargo</>}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* ========== MIND MAP GENERATOR DIALOG ========== */}
        <Dialog open={showMindmapDialog} onOpenChange={setShowMindmapDialog}>
          <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Network className="w-5 h-5 text-green-400" />Gerar Mapa Mental</DialogTitle>
              <DialogDescription>A IA irá criar um mapa mental estruturado</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <Label className="text-sm">Tópico ou Assunto</Label>
                <Input value={mindmapTopic} onChange={e => setMindmapTopic(e.target.value)} placeholder="Ex: Direito Constitucional - Direitos Fundamentais" className="bg-[#121212] border-[#27272A] mt-1" />
              </div>
              <div>
                <Label className="text-sm">Ou envie um arquivo (PDF/Imagem)</Label>
                <div className={`mt-1 border-2 border-dashed rounded-lg p-4 text-center ${mindmapFile ? 'border-green-500 bg-green-500/10' : 'border-[#27272A]'}`}>
                  {mindmapFile ? (
                    <div className="flex items-center justify-center gap-2">
                      <FileText className="w-4 h-4 text-green-400" />
                      <span className="text-xs text-green-300">{mindmapFile.name}</span>
                      <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => setMindmapFile(null)}><XCircle className="w-3 h-3 text-red-400" /></Button>
                    </div>
                  ) : (
                    <label className="cursor-pointer">
                      <Upload className="w-6 h-6 mx-auto text-[#A1A1AA] mb-1" />
                      <p className="text-xs text-[#A1A1AA]">Clique para selecionar</p>
                      <input type="file" accept=".pdf,image/*" className="hidden" onChange={e => setMindmapFile(e.target.files?.[0] || null)} />
                    </label>
                  )}
                </div>
              </div>
              <Button onClick={handleGenerateMindmap} disabled={mindmapGenerating || (!mindmapTopic && !mindmapFile && !selectedNotebook)} className="w-full bg-green-600 hover:bg-green-700">
                {mindmapGenerating ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Gerando mapa mental...</> : <><Network className="w-4 h-4 mr-2" />Gerar Mapa Mental</>}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* ========== MIND MAP VIEW DIALOG ========== */}
        <Dialog open={showMindmapView} onOpenChange={setShowMindmapView}>
          <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Network className="w-5 h-5 text-green-400" />Mapa Mental: {viewingMindmap?.title || ''}</DialogTitle>
            </DialogHeader>
            {viewingMindmap && (
              <div className="py-4">
                {/* Central Node */}
                <div className="text-center mb-6">
                  <div className="inline-block bg-gradient-to-r from-purple-600 to-blue-600 px-6 py-3 rounded-xl">
                    <h2 className="text-lg font-bold text-white">{viewingMindmap.title}</h2>
                  </div>
                </div>
                {/* Branches */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {(viewingMindmap.nodes || []).map((node, i) => (
                    <Card key={i} className="bg-[#121212] border-[#27272A] overflow-hidden">
                      <div className="h-1" style={{ backgroundColor: node.color || '#007AFF' }} />
                      <CardContent className="p-4">
                        <h3 className="font-bold text-sm mb-2" style={{ color: node.color || '#007AFF' }}>{node.label}</h3>
                        {(node.children || []).map((child, ci) => (
                          <div key={ci} className="ml-3 mb-2">
                            <div className="flex items-start gap-2">
                              <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ backgroundColor: node.color || '#007AFF' }} />
                              <div>
                                <p className="text-xs font-medium text-white">{child.label}</p>
                                {(child.children || []).map((sub, si) => (
                                  <p key={si} className="text-[10px] text-[#A1A1AA] ml-3 mt-0.5">• {sub.label}</p>
                                ))}
                              </div>
                            </div>
                          </div>
                        ))}
                      </CardContent>
                    </Card>
                  ))}
                </div>
                <div className="flex gap-2 mt-4">
                  <Button variant="outline" size="sm" className="border-[#27272A]" onClick={async () => {
                    try {
                      const el = document.querySelector('[data-mindmap-content]');
                      if (!el) return;
                      const canvas = await html2canvas(el, { backgroundColor: '#0A0A0A', scale: 2 });
                      const link = document.createElement('a');
                      link.download = `mapa_mental_${viewingMindmap?.title || 'estudo'}.png`;
                      link.href = canvas.toDataURL('image/png');
                      link.click();
                      toast.success("Imagem exportada!");
                    } catch { toast.error("Erro ao exportar"); }
                  }}><Download className="w-3 h-3 mr-1" />Exportar Imagem</Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* ========== PROGRESS COMPARISON DIALOG ========== */}
        <Dialog open={showProgressDialog} onOpenChange={setShowProgressDialog}>
          <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><TrendingUp className="w-5 h-5 text-blue-400" />Comparador de Progresso</DialogTitle>
              <DialogDescription>Evolução das disciplinas nos últimos 30 dias</DialogDescription>
            </DialogHeader>
            {progressLoading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
              </div>
            ) : progressHistory && (
              <div className="space-y-6 py-2">
                {progressHistory.history?.length > 0 ? (
                  <>
                    <Card className="bg-[#121212] border-[#27272A] p-4">
                      <h3 className="text-sm font-medium mb-3 flex items-center gap-2"><Hash className="w-4 h-4 text-purple-400" />Questões Acumuladas</h3>
                      <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={progressHistory.history}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                          <XAxis dataKey="date" tick={{ fill: '#A1A1AA', fontSize: 10 }} />
                          <YAxis tick={{ fill: '#A1A1AA', fontSize: 10 }} />
                          <Tooltip contentStyle={{ backgroundColor: '#121212', border: '1px solid #27272A', borderRadius: 8 }} />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          {(progressHistory.notebooks || []).map((nb, i) => (
                            <Line key={i} type="monotone" dataKey={`${nb.name}_questoes`} name={nb.name} stroke={nb.color} strokeWidth={2} dot={false} />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    </Card>
                    <Card className="bg-[#121212] border-[#27272A] p-4">
                      <h3 className="text-sm font-medium mb-3 flex items-center gap-2"><Target className="w-4 h-4 text-green-400" />Taxa de Acerto (%)</h3>
                      <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={progressHistory.history}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                          <XAxis dataKey="date" tick={{ fill: '#A1A1AA', fontSize: 10 }} />
                          <YAxis tick={{ fill: '#A1A1AA', fontSize: 10 }} domain={[0, 100]} />
                          <Tooltip contentStyle={{ backgroundColor: '#121212', border: '1px solid #27272A', borderRadius: 8 }} />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          {(progressHistory.notebooks || []).map((nb, i) => (
                            <Line key={i} type="monotone" dataKey={`${nb.name}_acerto`} name={`${nb.name} %`} stroke={nb.color} strokeWidth={2} dot={false} />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    </Card>
                    <Card className="bg-[#121212] border-[#27272A] p-4">
                      <h3 className="text-sm font-medium mb-3 flex items-center gap-2"><Clock className="w-4 h-4 text-yellow-400" />Horas de Estudo Acumuladas</h3>
                      <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={progressHistory.history}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                          <XAxis dataKey="date" tick={{ fill: '#A1A1AA', fontSize: 10 }} />
                          <YAxis tick={{ fill: '#A1A1AA', fontSize: 10 }} />
                          <Tooltip contentStyle={{ backgroundColor: '#121212', border: '1px solid #27272A', borderRadius: 8 }} />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          {(progressHistory.notebooks || []).map((nb, i) => (
                            <Line key={i} type="monotone" dataKey={`${nb.name}_horas`} name={`${nb.name} h`} stroke={nb.color} strokeWidth={2} dot={false} />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    </Card>
                  </>
                ) : (
                  <div className="text-center py-10">
                    <BarChart3 className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
                    <p className="text-[#A1A1AA]">Sem dados de progresso ainda</p>
                    <p className="text-xs text-[#52525B]">Registre questões e sessões de foco para ver a evolução</p>
                  </div>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* ========== EDITAL VERTICALIZADO DIALOG ========== */}
        <Dialog open={showVerticalizadoDialog} onOpenChange={setShowVerticalizadoDialog}>
          <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Layers className="w-5 h-5 text-purple-400" />Edital Verticalizado</DialogTitle>
              <DialogDescription>{verticalizadoData?.program_name || 'Programa de Estudos'}</DialogDescription>
            </DialogHeader>
            {verticalizadoLoading ? (
              <div className="flex flex-col items-center justify-center py-10">
                <Loader2 className="w-8 h-8 animate-spin text-purple-400 mb-3" />
                <p className="text-sm text-[#A1A1AA]">Carregando edital verticalizado...</p>
              </div>
            ) : verticalizadoData && (
              <div className="space-y-4 py-2">
                {/* Concurso Info Header */}
                <Card className="bg-[#121212] border-[#27272A]">
                  <CardContent className="pt-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                      {verticalizadoData.banca && (
                        <div><span className="text-[#71717A]">Banca:</span> <span className="text-white font-medium">{verticalizadoData.banca}</span></div>
                      )}
                      {verticalizadoData.orgao && (
                        <div><span className="text-[#71717A]">Órgão:</span> <span className="text-white font-medium">{verticalizadoData.orgao}</span></div>
                      )}
                      {verticalizadoData.cargo && (
                        <div><span className="text-[#71717A]">Cargo:</span> <span className="text-white font-medium">{verticalizadoData.cargo}</span></div>
                      )}
                      {verticalizadoData.target_date && (
                        <div><span className="text-[#71717A]">Prova:</span> <span className="text-purple-400 font-medium">{verticalizadoData.target_date}</span></div>
                      )}
                    </div>
                    <div className="flex gap-4 mt-3">
                      <Badge className="bg-purple-500/20 text-purple-400">{verticalizadoData.total_disciplinas} Disciplinas</Badge>
                      <Badge className="bg-blue-500/20 text-blue-400">{verticalizadoData.total_assuntos} Assuntos</Badge>
                    </div>
                  </CardContent>
                </Card>

                {/* Disciplines with full content */}
                {(verticalizadoData.disciplinas || []).map((disc, i) => {
                  const isExpanded = expandedDisciplinas.has(`vert_${i}`);
                  const hasConteudo = disc.conteudo_programatico?.length > 0;
                  const hasTopicos = disc.topicos?.length > 0;
                  return (
                    <Card key={i} className="bg-[#121212] border-[#27272A] overflow-hidden">
                      <button
                        className="w-full px-4 py-3 flex items-center justify-between hover:bg-[#1A1A1A] transition-colors"
                        onClick={() => toggleDisciplinaExpanded(`vert_${i}`)}
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: disc.color }} />
                          <div className="text-left">
                            <p className="text-sm font-medium text-white">{disc.nome}</p>
                            <div className="flex items-center gap-2 mt-0.5">
                              <Badge variant="outline" className="text-[9px] border-yellow-500 text-yellow-400">Peso {disc.peso}</Badge>
                              {disc.num_questoes > 0 && <span className="text-[10px] text-[#71717A]">{disc.num_questoes} questões</span>}
                              <Badge variant="outline" className={`text-[9px] ${disc.dificuldade === 'alta' ? 'border-red-500 text-red-400' : disc.dificuldade === 'media' ? 'border-yellow-500 text-yellow-400' : 'border-green-500 text-green-400'}`}>{disc.dificuldade}</Badge>
                              {disc.grupo && <span className="text-[10px] text-[#52525B]">{disc.grupo}</span>}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-right text-[10px] hidden md:block">
                            <p className="text-[#A1A1AA]">{disc.study_hours}h estudado</p>
                            <p className="text-[#A1A1AA]">{disc.total_questions_answered} questões | {disc.accuracy}% acerto</p>
                          </div>
                          <Badge variant="outline" className="text-[9px] border-[#3F3F46] text-[#A1A1AA]">
                            {hasConteudo ? `${disc.total_assuntos} assuntos` : hasTopicos ? `${disc.topicos.length} tópicos` : 'Sem conteúdo'}
                          </Badge>
                          {isExpanded ? <ChevronUp className="w-4 h-4 text-[#A1A1AA]" /> : <ChevronDown className="w-4 h-4 text-[#A1A1AA]" />}
                        </div>
                      </button>
                      {isExpanded && (
                        <CardContent className="border-t border-[#27272A] pt-3">
                          {/* Study Progress Mini */}
                          <div className="grid grid-cols-4 gap-2 text-center mb-4 bg-[#0A0A0A] rounded-lg p-2">
                            <div><p className="text-lg font-bold text-white">{disc.study_hours}h</p><p className="text-[9px] text-[#71717A]">Estudado</p></div>
                            <div><p className="text-lg font-bold text-purple-400">{disc.total_questions_answered}</p><p className="text-[9px] text-[#71717A]">Questões</p></div>
                            <div><p className={`text-lg font-bold ${disc.accuracy >= 70 ? 'text-green-400' : disc.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{disc.accuracy}%</p><p className="text-[9px] text-[#71717A]">Acerto</p></div>
                            <div><p className="text-lg font-bold text-blue-400">{disc.num_questoes || '-'}</p><p className="text-[9px] text-[#71717A]">Questões Edital</p></div>
                          </div>

                          {/* Conteúdo Programático Detalhado */}
                          {hasConteudo ? (
                            <div className="space-y-2">
                              <p className="text-xs font-medium text-purple-400 mb-2">Conteúdo Programático:</p>
                              {disc.conteudo_programatico.map((item, j) => (
                                <div key={j} className="pl-3 border-l-2 border-purple-500/30 py-1">
                                  <p className="text-xs font-medium text-white">{j + 1}. {item.assunto}</p>
                                  {item.subtopicos?.length > 0 && (
                                    <div className="ml-4 mt-1 space-y-0.5">
                                      {item.subtopicos.map((sub, k) => (
                                        <p key={k} className="text-[10px] text-[#A1A1AA] flex items-start gap-1">
                                          <span className="text-[#52525B] mt-0.5">•</span> {sub}
                                        </p>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          ) : hasTopicos ? (
                            <div>
                              <p className="text-xs font-medium text-purple-400 mb-2">Tópicos:</p>
                              <div className="flex flex-wrap gap-1">
                                {disc.topicos.map((t, j) => (
                                  <Badge key={j} variant="outline" className="text-[10px] border-[#27272A] text-[#A1A1AA]">{t}</Badge>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <p className="text-xs text-[#52525B] italic">Conteúdo programático não disponível para esta disciplina.</p>
                          )}
                        </CardContent>
                      )}
                    </Card>
                  );
                })}
              </div>
            )}
          </DialogContent>
        </Dialog>

      </main>
      <MobileNav user={user} />
    </div>
  );
}

