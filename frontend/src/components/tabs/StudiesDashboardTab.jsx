import PomodoroTimer from "@/components/PomodoroTimer";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

import { BookOpen, Plus, Folder, Clock, Brain, Layers, Target, ChevronRight, Timer, BarChart3, TrendingUp } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, PieChart, Pie, Cell } from 'recharts';

export default function StudiesDashboardTab({ stats, overallStudyStats, totalQuestions, accuracy, focusToday, showAreaDialog, setShowAreaDialog, areaForm, setAreaForm, handleCreateArea, areas, areaIcons, programs, notebooks, setSelectedArea, setSelectedProgram, setSelectedNotebook, setActiveTab, QuestionLogger, fetchAllData, user, StudyAIChat, selectedNotebook, pendingTasksCount, tasks, handleToggleTask, taskTypeLabels }) {
 return <>
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
                <PomodoroTimer userId={user?.user_id} notebooks={notebooks} onComplete={fetchAllData} />
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
          </>;
}
