import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { getApiErrorMessage } from '@/lib/api-errors';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api`;
const modes = [['explain', 'Explicar'], ['socratic', 'Socrático'], ['quick', 'Revisão rápida'], ['examiner', 'Me testar'], ['questions', 'Questões'], ['flashcards', 'Flashcards'], ['deepen', 'Aprofundar'], ['pre_exam', 'Pré-prova']];

export default function SiriusTutor({ userId, programId, notebookId, topic, sessionCompleted, onReview }) {
  const [mode, setMode] = useState('explain'), [message, setMessage] = useState(''), [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState('');
  const [uploadFailed, setUploadFailed] = useState(false);
  const [materials, setMaterials] = useState(null), [uploading, setUploading] = useState(false), [summary, setSummary] = useState(null);
  const [excerpt, setExcerpt] = useState(''), [front, setFront] = useState(''), [back, setBack] = useState(''), [proposal, setProposal] = useState(null), [saving, setSaving] = useState(false), [saved, setSaved] = useState('');
  const generation = useRef(0), pending = useRef(null), turnLock = useRef(false), saveLock = useRef(false), action = useRef(null);
  const reviewJob = useRef(null);
  const upload = useRef(null), uploadLock = useRef(false), started = useRef(new Date().toISOString());
  const scope = { preparation_id: programId, notebook_id: notebookId, topic_key: topic?.key ?? null };
  const identity = JSON.stringify([userId, programId, notebookId, topic?.key, mode]);
  const conversation = useRef({});
  if (!conversation.current[identity]) {
    const key = `sirius-tutor:${identity}`;
    try { conversation.current[identity] = localStorage.getItem(key) || crypto.randomUUID(); localStorage.setItem(key, conversation.current[identity]); }
    catch { conversation.current[identity] = crypto.randomUUID(); }
  }
  const conversationId = conversation.current[identity];
  useEffect(() => { started.current = new Date().toISOString(); }, [programId, notebookId, topic?.key]);
  const refreshMaterials = async () => { const { data } = await axios.get(`${API}/study/tutor/materials`, { params: scope }); return data; };
  useEffect(() => {
    const c = new AbortController(); const current = ++generation.current;
    turnLock.current = false; saveLock.current = false; uploadLock.current = false; pending.current = null; action.current = null; reviewJob.current = null; upload.current = null; setUploadFailed(false);
    setBusy(false); setSaving(false); setUploading(false); setMessages([]); setError(''); setLoading(true); setProposal(null); setSummary(null); setMaterials(null); setSaved('');
    axios.get(`${API}/study/tutor/history`, { params: { preparation_id: programId, notebook_id: notebookId, topic_key: topic?.key ?? null, mode, conversation_id: conversationId }, signal: c.signal })
      .then(r => { if (!c.signal.aborted) setMessages(r.data.messages || []); }).catch(e => { if (!c.signal.aborted) setError(getApiErrorMessage(e, 'Não foi possível retomar o tutor.')); }).finally(() => { if (!c.signal.aborted) setLoading(false); });
    axios.get(`${API}/study/tutor/materials`, { params: { preparation_id: programId, notebook_id: notebookId, topic_key: topic?.key ?? null }, signal: c.signal }).then(r => { if (!c.signal.aborted) setMaterials(r.data); }).catch(() => {});
    return () => { c.abort(); generation.current = current + 1; };
  }, [programId, notebookId, topic?.key, mode, conversationId]);
  const send = async (text = message) => {
    if (turnLock.current || loading || !text.trim()) return; turnLock.current = true; setBusy(true); setError('');
    const current = generation.current, intent = JSON.stringify([scope, mode, conversationId, text]);
    if (pending.current?.intent !== intent) pending.current = { intent, body: { ...scope, mode, conversation_id: conversationId, request_id: crypto.randomUUID(), message: text.trim() } };
    try {
      const { data } = await axios.post(`${API}/study/tutor/turn`, pending.current.body);
      if (current !== generation.current) return;
      setMessages(old => [...old.filter(m => ![data.user_message.message_id, data.ai_message.message_id].includes(m.message_id)), data.user_message, data.ai_message]); pending.current = null; setMessage('');
    } catch (e) { if (current === generation.current) setError(getApiErrorMessage(e, 'Não foi possível responder. Reenvie a mesma mensagem para retomar com segurança.')); }
    finally { if (current === generation.current) { setBusy(false); turnLock.current = false; } }
  };
  const attach = async file => {
    if (!file || uploadLock.current) return; uploadLock.current = true; setUploading(true); setUploadFailed(false); setError(''); const current = generation.current;
    try {
      if (upload.current?.file !== file) upload.current = { file, key: crypto.randomUUID() };
      const job = upload.current;
      if (!job.attachment) { const form = new FormData(); form.append('file', file); const r = await axios.post(`${API}/ai/attachments`, form); job.attachment = r.data; }
      await axios.post(`${API}/study/tutor/materials/${job.attachment.attachment_id}/link`, scope, { headers: { 'Idempotency-Key': job.key } });
      if (current === generation.current) { const data = await refreshMaterials(); if (current === generation.current) { setMaterials(data); setSaved('Texto extraído vinculado. O arquivo original não foi retido.'); } }
    } catch (e) { if (current === generation.current) { setUploadFailed(true); setError(getApiErrorMessage(e, 'Não foi possível vincular. Use Tentar material novamente.')); } }
    finally { if (current === generation.current) { setUploading(false); uploadLock.current = false; } }
  };
  const copilot = async () => {
    const current = generation.current;
    try { const { data } = await axios.get(`${API}/study/tutor/copilot`, { params: { ...scope, since: new Date(Math.max(Date.parse(started.current), Date.now() - (24 * 60 - 5) * 60000)).toISOString() } }); if (current === generation.current) setSummary(data); }
    catch (e) { if (current === generation.current) setError(getApiErrorMessage(e, 'Não foi possível resumir a sessão.')); }
  };
  const saveProposal = async () => {
    if (saveLock.current) return; saveLock.current = true; setSaving(true); setError(''); const current = generation.current;
    const body = proposal === 'flashcard' ? { notebook_id: notebookId, deck_name: 'Trechos de estudo', front, back, tags: ['trecho', ...(topic ? [topic.title] : [])] } : { notebook_id: notebookId, title: front, content: back, tags: ['trecho'], links: [] };
    const intent = JSON.stringify([proposal, body]); if (action.current?.intent !== intent) action.current = { intent, key: crypto.randomUUID() };
    try { await axios.post(`${API}/study/${proposal === 'flashcard' ? 'flashcards' : 'notes'}`, body, { headers: { 'Idempotency-Key': action.current.key } }); if (current === generation.current) { setProposal(null); action.current = null; setSaved('Proposta salva na biblioteca.'); } }
    catch (e) { if (current === generation.current) setError(getApiErrorMessage(e, 'Não foi possível salvar. Tente a mesma proposta novamente.')); }
    finally { if (current === generation.current) { setSaving(false); saveLock.current = false; } }
  };
  const confirmReview = async () => {
    if (saveLock.current || !topic) return; saveLock.current = true; setSaving(true); setError(''); const current = generation.current;
    reviewJob.current ||= crypto.randomUUID();
    try { await axios.post(`${API}/study/tutor/review`, scope, { headers: { 'Idempotency-Key': reviewJob.current } }); if (current === generation.current) { reviewJob.current = null; setSaved('Revisão registrada na sessão.'); await onReview?.(); } }
    catch (e) { if (current === generation.current) setError(getApiErrorMessage(e, 'Não foi possível confirmar a revisão. Tente novamente.')); }
    finally { if (current === generation.current) { setSaving(false); saveLock.current = false; } }
  };
  const last = [...messages].reverse().find(m => m.role === 'assistant');
  return <section aria-label="Sirius Tutor" className="rounded-2xl border border-purple-500/30 bg-slate-950 p-4 md:p-6 space-y-5 min-w-0 [&_button]:min-h-11">
    <header><h3 className="text-lg font-semibold">Sirius Tutor</h3><p className="text-sm text-slate-400">{topic?.title || 'Estudo da disciplina'} · perguntas, recall e materiais no seu contexto.</p></header>
    <label className="block text-sm">Modo do tutor<select className="block w-full bg-slate-900 rounded-xl p-3 mt-2" value={mode} disabled={busy} onChange={e => setMode(e.target.value)}>{modes.map(([v, label]) => <option value={v} key={v}>{label}</option>)}</select></label>
    <p className="text-xs text-slate-400">Assistência de IA. Avaliações são estimativas e não registram domínio ou XP. Fontes disponíveis aparecem abaixo; conhecimento geral deve ser identificado.</p>
    <div aria-label="Conversa de estudo" className="max-h-[32rem] overflow-y-auto space-y-3">{loading && <p role="status">Retomando conversa…</p>}{messages.map(m => <article key={m.message_id} className={`rounded-xl p-4 whitespace-pre-wrap break-words ${m.role === 'user' ? 'bg-slate-900' : 'bg-purple-950/30'}`}><p className="text-xs text-slate-400 mb-2">{m.role === 'user' ? 'Você' : 'Sirius · assistência estimada'}</p>{m.content}{m.tutor?.knowledge_basis === 'general_model_knowledge_and_sirius_facts' && <p className="text-xs text-amber-200 mt-3">Sem trecho documental correspondente: conhecimento geral do modelo e fatos registrados.</p>}</article>)}</div>
    <form onSubmit={e => { e.preventDefault(); send(); }} className="space-y-3"><label className="block text-sm">Sua pergunta ou resposta<textarea aria-label="Mensagem para o tutor" maxLength={6000} rows={3} value={message} disabled={busy} onChange={e => setMessage(e.target.value)} className="block w-full rounded-xl bg-slate-900 p-3 mt-2" placeholder={mode === 'socratic' || mode === 'examiner' ? 'Peça uma pergunta ou responda à pergunta anterior…' : 'O que você quer compreender ou revisar?'} /></label><Button type="submit" disabled={busy || loading || !message.trim()}>{busy ? 'Respondendo…' : 'Enviar ao tutor'}</Button></form>
    {error && <p role="alert" className="text-amber-300 text-sm">{error}</p>}{saved && <p role="status" className="text-green-300 text-sm">{saved}</p>}
    <details className="rounded-xl border border-slate-700 p-4"><summary className="cursor-pointer py-2">Fontes e materiais de estudo</summary><p className="text-xs text-slate-400 my-3">Busca textual: materiais vinculados e anotações, edital registrado, fatos Sirius e conhecimento geral identificado. O original não fica armazenado.</p><label className="block text-sm py-3">Vincular PDF com texto · até 8 MB<input aria-label="Vincular material PDF" type="file" accept="application/pdf" disabled={uploading} onChange={e => attach(e.target.files?.[0])} className="block w-full mt-2 text-xs" /></label>{uploadFailed && <Button variant="outline" disabled={uploading} onClick={() => attach(upload.current?.file)}>Tentar material novamente</Button>}{uploading && <p role="status">Extraindo e vinculando…</p>}{materials?.materials?.map(f => <p className="text-sm break-words py-2" key={f.attachment_id}>{f.filename} · texto extraído</p>)}{materials && <p className="text-xs text-slate-400">{materials.related_errors?.length || 0} erros recentes no assunto/disciplina. {materials.notice}</p>}{last?.citations?.map(c => <article key={c.id} className="border-t border-slate-700 py-3 space-y-2"><p className="text-xs text-purple-300">[{c.id}] {c.title} · {c.category === 'edital_record' ? 'Edital registrado' : 'Material do usuário'}{c.page ? ` · página ${c.page}` : ''}</p><p className="text-sm whitespace-pre-wrap break-words">{c.text}</p><Button variant="outline" onClick={() => { setExcerpt(c.text); setBack(c.text); setFront(`Recall: ${topic?.title || 'trecho de estudo'}`); }}>Usar trecho como proposta</Button></article>)}</details>
    <details className="rounded-xl border border-slate-700 p-4"><summary className="cursor-pointer py-2">Trechos e propostas</summary><label className="block text-sm mt-3">Trecho marcado<textarea aria-label="Trecho marcado" rows={3} maxLength={12000} value={excerpt} onChange={e => setExcerpt(e.target.value)} className="block w-full bg-slate-900 rounded-xl p-3 mt-2" /></label><div className="flex flex-wrap gap-2 mt-3">{[['flashcard', 'Propor flashcard'], ['note', 'Propor nota']].map(([v, label]) => <Button key={v} variant="outline" disabled={!excerpt.trim() || saving} onClick={() => { setProposal(v); setFront(`Recall: ${topic?.title || 'trecho'}`); setBack(excerpt); setSaved(''); }}>{label}</Button>)}<Button variant="outline" disabled={!excerpt.trim() || busy} onClick={() => { setMode('questions'); setMessage(`Proponha uma questão de recall deste trecho, sem salvar: ${excerpt}`.slice(0,6000)); }}>Propor pergunta</Button>{topic && <Button variant="outline" disabled={saving} onClick={confirmReview}>Confirmar revisão deste assunto</Button>}</div>{proposal && <div className="space-y-3 mt-4"><p className="text-xs text-amber-200">Revise a proposta antes de salvar. Nenhuma resposta ou revisão é registrada automaticamente.</p><label className="block text-sm">Pergunta ou título<input aria-label="Título da proposta" maxLength={proposal === 'flashcard' ? 12000 : 500} value={front} onChange={e => setFront(e.target.value)} className="block w-full bg-slate-900 p-3 rounded-xl" /></label><label className="block text-sm">Conteúdo da proposta<textarea aria-label="Conteúdo da proposta" rows={3} maxLength={20000} value={back} onChange={e => setBack(e.target.value)} className="block w-full bg-slate-900 p-3 rounded-xl" /></label><Button disabled={saving || !front.trim() || !back.trim()} onClick={saveProposal}>{saving ? 'Salvando…' : 'Confirmar e salvar proposta'}</Button></div>}</details>
    <section className="border-t border-slate-700 pt-4 space-y-3"><h4 className="font-medium">Copiloto da sessão</h4><p className="text-xs text-slate-400">Use o objetivo, timer, anotações e questões desta página. Ao encerrar, confira apenas o que foi registrado.</p><Button variant="outline" onClick={copilot}>{sessionCompleted ? 'Ver resumo do estudo concluído' : 'Conferir sessão até agora'}</Button>{summary && <div role="region" aria-label="Resumo factual da sessão" className="rounded-xl bg-slate-900 p-4 space-y-2"><p className="text-xs text-slate-400">Intervalo: {new Date(summary.since).toLocaleString()} a {new Date(summary.until).toLocaleString()}.</p><p>{summary.recorded_minutes} min registrados · {summary.answered} questões · {summary.accuracy == null ? 'sem precisão medida' : `${summary.accuracy}% de acertos`} · {summary.reviewed_topics} assuntos revisados</p><p className="text-sm">{summary.recommendation}</p><p className="text-xs text-slate-400">{summary.notice}</p></div>}</section>
  </section>;
}
