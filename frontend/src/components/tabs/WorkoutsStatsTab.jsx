import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import { Check, Timer, Flame, TrendingUp, Activity, Sparkles, Target, RefreshCw, Save } from "lucide-react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, PieChart, Pie, Cell } from 'recharts';

export default function WorkoutsStatsTab({ detailedStats, stats, getAiSuggestions, loadingSuggestions, aiSuggestions, handleSaveInsight, setAiSuggestions }) {
 return <>
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
            </>;
}
