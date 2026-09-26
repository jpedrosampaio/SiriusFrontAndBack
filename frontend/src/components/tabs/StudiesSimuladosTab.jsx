import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { Progress } from "@/components/ui/progress";

import { BookOpen, Trash2, ChevronRight, Loader2, RotateCcw, CheckCircle2, XCircle, Sparkles, Play, Timer, Lightbulb, Repeat, ArrowLeft, BarChart3, Zap, TrendingUp, Upload, ListChecks, ClipboardList, Eye, EyeOff, ChevronLeft, CircleDot, Flag, StopCircle } from "lucide-react";

export default function StudiesSimuladosTab({ simuladoMode, currentSimulado, handleExitSimulado, simuladoCurrentQ, formatTimer, simuladoTimer, simuladoAnswers, simuladoMarked, setSimuladoMarked, setSimuladoAnswers, setSimuladoCurrentQ, handleSubmitSimulado, simuladoSubmitting, showGabarito, setShowGabarito, handleStartSimulado, simuladoResult, setShowSimuladoStatsView, showSimuladoStatsView, showImportPdfDialog, setShowImportPdfDialog, setImportFile, importForm, setImportForm, handleImportPdf, simuladoImporting, importFile, showGenerateDialog, setShowGenerateDialog, generateForm, setGenerateForm, handleGenerateSimulado, simuladoGenerating, simuladoStats, simulados, handleDeleteSimulado, handleViewSimulado, handleViewResults }) {
 return <>
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
          </>;
}
