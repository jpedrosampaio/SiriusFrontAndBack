import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

import { Badge } from "@/components/ui/badge";

import { FileText, Loader2, CheckCircle2, XCircle, Sparkles, PenTool, BookMarked, Lightbulb, Zap, Upload } from "lucide-react";

export default function StudiesRedacaoTab({ redacaoFile, setRedacaoFile, handleRedacaoCorrection, redacaoLoading, handleRandomTheme, themeLoading, randomTheme, showRedacaoResult, redacaoCorrection, setShowRedacaoResult, redacaoHistory, fetchRedacaoHistory, setRedacaoCorrection }) {
 return <>
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
          </>;
}
