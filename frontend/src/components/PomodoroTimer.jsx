import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Timer, Coffee, Edit3, Play, Pause, RotateCcw } from "lucide-react";
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PomodoroTimer({ notebooks = [], onComplete, initialNotebookId = "", topic = "", initialMinutes = 25, lockNotebook = false }) {
  const [isRunning, setIsRunning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isBreak, setIsBreak] = useState(false);
  const [timeLeft, setTimeLeft] = useState(initialMinutes * 60);
  const [focusMinutes, setFocusMinutes] = useState(initialMinutes);
  const [breakMinutes, setBreakMinutes] = useState(5);
  const [selectedNb, setSelectedNb] = useState(initialNotebookId);
  const [sessionsCompleted, setSessionsCompleted] = useState(0);
  const [showSettings, setShowSettings] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const intervalRef = useRef(null);
  const completedPhaseRef = useRef(false);

  const handleFocusComplete = useCallback(async () => {
    setSaveError(false);
    try {
      await axios.post(`${API}/study/focus/complete`, {
        notebook_id: selectedNb && selectedNb !== "none" ? selectedNb : null,
        focus_minutes: focusMinutes,
        break_minutes: breakMinutes,
        notes: topic || null
      }, { withCredentials: true });
      setSessionsCompleted(prev => prev + 1);
      toast.success(`Sessão concluída! +XP 🎉`);
      if (onComplete) onComplete();
    } catch (err) {
      setSaveError(true);
    }
  }, [selectedNb, focusMinutes, breakMinutes, onComplete, topic]);

  useEffect(() => {
    if (isRunning && !isPaused) {
      intervalRef.current = setInterval(() => {
        setTimeLeft(prev => Math.max(0, prev - 1));
      }, 1000);
    }
    return () => clearInterval(intervalRef.current);
  }, [isRunning, isPaused]);

  useEffect(() => {
    if (timeLeft > 0) { completedPhaseRef.current = false; return; }
    if (!isRunning || isPaused || completedPhaseRef.current) return;
    completedPhaseRef.current = true;
    if (!isBreak) {
      handleFocusComplete();
      setIsBreak(true);
      setTimeLeft(breakMinutes * 60);
    } else {
      setIsBreak(false);
      setIsRunning(false);
      setTimeLeft(focusMinutes * 60);
      toast.success("Pausa finalizada! Pronto para mais?");
    }
  }, [timeLeft, isRunning, isPaused, isBreak, breakMinutes, focusMinutes, handleFocusComplete]);

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
        {saveError && <p role="alert" className="text-sm text-amber-300 mb-4">Registro não confirmado. Confira o histórico de foco antes de registrar novamente; suas anotações continuam nesta página.</p>}
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
                <Input type="number" value={focusMinutes} onChange={e => { const minutes = Math.min(120, Math.max(1, Math.floor(Number(e.target.value)) || 1)); setFocusMinutes(minutes); setTimeLeft(minutes * 60); }} className="bg-[#0A0A0A] border-[#27272A] h-8 text-sm" min={1} max={120} />
              </div>
              <div>
                <Label className="text-xs">Pausa (min)</Label>
                <Input type="number" value={breakMinutes} onChange={e => setBreakMinutes(Math.min(30, Math.max(1, Math.floor(Number(e.target.value)) || 1)))} className="bg-[#0A0A0A] border-[#27272A] h-8 text-sm" min={1} max={30} />
              </div>
            </div>
            <div>
              <Label className="text-xs">Matéria (opcional)</Label>
              <Select value={selectedNb} onValueChange={setSelectedNb} disabled={lockNotebook}>
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

