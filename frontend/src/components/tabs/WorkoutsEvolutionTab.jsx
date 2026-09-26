import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";

import { Plus, Flame, Scale, Upload, Sparkles, Target, Ruler, Loader2, Search } from "lucide-react";

export default function WorkoutsEvolutionTab({ openMeasurement, setOpenMeasurement, handlePdfUpload, uploadingPdf, pdfAnalysis, newMeasurement, setNewMeasurement, handleCreateMeasurement, latestMeasurement, loadRecommendations, loadingRecommendations, recommendations, measurements, exerciseFilter, setExerciseFilter, setExerciseEvoData, fetchExerciseEvolution, evoLoading, evoError, exerciseEvoData }) {
 return <>
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

                {/* Exercise Evolution Section */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3 mb-4">
                    <div>
                      <h3 className="font-heading text-lg">EVOLUÇÃO DOS EXERCÍCIOS</h3>
                      <p className="text-xs text-[#A1A1AA]">Progresso de carga e repetições ao longo do tempo</p>
                    </div>
                    <div className="flex gap-2 w-full md:w-auto">
                      <input
                        type="text"
                        placeholder="Filtrar exercício..."
                        value={exerciseFilter}
                        onChange={(e) => { setExerciseFilter(e.target.value); setExerciseEvoData(null); }}
                        className="flex-1 md:w-48 h-9 px-3 text-sm bg-[#18181B] border border-[#27272A] rounded text-white"
                      />
                      <Button size="sm" onClick={() => fetchExerciseEvolution(exerciseFilter)} className="bg-[#00F0FF] hover:bg-[#00D4E5] text-black">
                        <Search className="w-4 h-4 mr-1" /> Buscar
                      </Button>
                    </div>
                  </div>

                  {evoLoading && (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin text-[#00F0FF]" />
                    </div>
                  )}

                  {evoError && (
                    <p className="text-sm text-red-400 text-center py-4">{evoError}</p>
                  )}

                  {exerciseEvoData && !evoLoading && (
                    <div className="space-y-4">
                      {Object.keys(exerciseEvoData).length === 0 ? (
                        <p className="text-sm text-[#52525B] text-center py-4">Nenhum dado encontrado para este exercício</p>
                      ) : (
                        Object.entries(exerciseEvoData).map(([exName, entries]) => (
                          <div key={exName} className="border border-[#27272A] rounded-lg p-3">
                            <h4 className="font-medium text-sm text-[#00F0FF] mb-2">{exName}</h4>
                            <div className="overflow-x-auto">
                              <table className="w-full text-xs">
                                <thead>
                                  <tr className="border-b border-[#27272A]">
                                    <th className="text-left p-1 text-[#52525B]">Data</th>
                                    <th className="text-right p-1 text-[#52525B]">Carga</th>
                                    <th className="text-right p-1 text-[#52525B]">Repetições</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {entries.map((entry, ei) => (
                                    <tr key={ei} className="border-b border-[#27272A]/30">
                                      <td className="p-1 text-[#A1A1AA]">{entry.date}</td>
                                      <td className="text-right p-1 text-white">{entry.weight || "-"}</td>
                                      <td className="text-right p-1 text-white">{entry.reps || "-"}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {!exerciseEvoData && !evoLoading && (
                    <p className="text-sm text-[#52525B] text-center py-4">
                      Digite o nome de um exercício e clique em "Buscar" para ver sua evolução
                    </p>
                  )}
                </Card>
              </div>
            </>;
}
