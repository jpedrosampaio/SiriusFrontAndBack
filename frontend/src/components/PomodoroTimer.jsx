import { useState } from "react";
import usePersistentFocus from "@/hooks/usePersistentFocus";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Timer, Coffee, Edit3, Play, Pause, RotateCcw } from "lucide-react";
export default function PomodoroTimer({ userId, storageId, notebooks = [], onComplete, initialNotebookId = "", topic = "", initialMinutes = 25, lockNotebook = false }) {
  const [showSettings, setShowSettings] = useState(false);
  const { isRunning, isPaused, isBreak, timeLeft, focusMinutes, breakMinutes, selectedNb,
    sessionsCompleted, saveError, saving, request, storageError, startTimer, togglePause, resetTimer, retry,
    setFocusMinutes, setBreakMinutes, setSelectedNb } = usePersistentFocus({ userId, storageId, initialNotebookId, initialMinutes, topic, onComplete });

  const mins = Math.floor(timeLeft / 60);
  const secs = timeLeft % 60;
  const totalSecs = isBreak ? breakMinutes * 60 : focusMinutes * 60;
  const progress = ((totalSecs - timeLeft) / totalSecs) * 100;

  return (
    <Card className={`border-2 transition-all ${isBreak ? 'bg-emerald-950/30 border-emerald-500/30' : isRunning ? 'bg-red-950/20 border-red-500/30' : 'bg-[#0A0A0A] border-[#27272A]'}`}>
      <CardContent className="p-4 md:p-6">
        {storageError && <p role="alert" className="text-sm text-amber-300">Não foi possível salvar o cronômetro neste dispositivo. Mantenha a tela aberta.</p>}
        {(saveError || request) && <div role="status" className="text-sm text-amber-300 mb-4"><p>{saving ? 'Registrando sessão…' : 'Sessão pendente de confirmação. Você pode tentar novamente sem duplicar tempo ou XP.'}</p><Button onClick={retry} disabled={saving} className="mt-2">{saving ? 'Salvando…' : 'Confirmar registro'}</Button></div>}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Timer className={`w-5 h-5 ${isBreak ? 'text-emerald-400' : 'text-red-400'}`} />
            <span className="font-bold text-sm">{isBreak ? 'PAUSA' : 'FOCO'}</span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              <Coffee className="w-3 h-3 mr-1" /> {sessionsCompleted} sessões
            </Badge>
            <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Configurar cronômetro" onClick={() => setShowSettings(!showSettings)}>
              <Edit3 className="w-3 h-3" />
            </Button>
          </div>
        </div>

        {showSettings && !isRunning && !request && (
          <div className="mb-4 p-3 bg-[#121212] rounded-lg space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Foco (min)</Label>
                <Input type="number" value={focusMinutes} onChange={e => { const minutes = Math.min(120, Math.max(1, Math.floor(Number(e.target.value)) || 1)); setFocusMinutes(minutes); }} className="bg-[#0A0A0A] border-[#27272A] h-8 text-sm" min={1} max={120} />
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
            <Button disabled={saving || !!request} onClick={startTimer} className="bg-red-600 hover:bg-red-700 px-8">
              <Play className="w-4 h-4 mr-2" /> {isBreak ? 'Iniciar descanso' : 'Iniciar foco'}
            </Button>
          ) : (
            <>
              <Button aria-label={isPaused ? "Retomar foco" : "Pausar foco"} disabled={!!request} onClick={togglePause} variant="outline" className="border-yellow-500 text-yellow-500">
                {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
              </Button>
              <Button aria-label="Reiniciar cronômetro" disabled={!!request} onClick={resetTimer} variant="outline" className="border-red-500 text-red-500">
                <RotateCcw className="w-4 h-4" />
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

