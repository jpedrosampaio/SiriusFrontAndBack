import { Card } from '@/components/ui/card';
import { Hash, Target, Clock } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend } from 'recharts';

export default function StudyProgressCharts({ progressHistory }) { return                   <>
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
                  </>; }
