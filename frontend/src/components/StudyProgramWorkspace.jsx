import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { ArrowLeft, BookOpen, Calendar, ChevronRight, Layers, Loader2, Play, Search } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import MobileNav from '@/components/MobileNav';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { getApiErrorMessage } from '@/lib/api-errors';
import { STUDY_VIEWS, normalizeStudyText, topicRows, blockMinutes, displayStudyDate } from '@/lib/study-workspace';
import StudyLessons from '@/components/StudyLessons';
import PomodoroTimer from '@/components/PomodoroTimer';

const labels = { edital: 'Edital analisado', verticalizado: 'Edital verticalizado', cronograma: 'Cronograma', estudar: 'Estudar' };
const box = 'rounded-2xl border border-[#27272A] bg-[#101014] p-5 md:p-6';
const muted = 'text-sm text-[#A1A1AA]';

export function EditalOverview({ concurso = {}, cargo = {}, filename, targetDate }) {
  const fields = [['Órgão', concurso.orgao], ['Banca', concurso.banca], ['Cargo', cargo.nome || concurso.cargo], ['Vagas', cargo.vagas || concurso.vagas], ['Remuneração', cargo.remuneracao || concurso.remuneracao], ['Escolaridade', cargo.escolaridade || concurso.escolaridade], ['Taxa de inscrição', cargo.taxa_inscricao || concurso.taxa_inscricao]];
  const deadlines = Array.isArray(concurso.prazos) ? concurso.prazos : [];
  return <div className="space-y-6">
    <section className={box}>
      <h2 className="text-lg font-semibold mb-4">Resumo do edital</h2>
      {concurso.visao_geral && <p className={`${muted} mb-5`}>{concurso.visao_geral}</p>}
      <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{fields.map(([label, value]) => <div key={label}><dt className="text-xs uppercase tracking-wide text-[#71717A]">{label}</dt><dd className="mt-1 text-sm leading-relaxed break-words">{value || 'Não informado na análise'}</dd></div>)}</dl>
      {filename && <p className="mt-5 border-t border-[#27272A] pt-4 text-xs text-[#71717A]">Arquivo analisado: {filename}</p>}
    </section>
    <section className={box}>
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2"><Calendar className="h-4 w-4 text-purple-400" />Prazos e datas</h2>
      {deadlines.length ? <ol className="space-y-4 border-l border-purple-500/40 pl-5">{deadlines.map((deadline, index) => <li key={index}><p className="text-sm font-medium">{deadline.label || deadline.nome} <span className="ml-2 text-purple-300">{displayStudyDate(deadline.data)}</span></p>{deadline.fonte && <p className="text-xs text-[#71717A] mt-1">Trecho do edital: {deadline.fonte}</p>}</li>)}</ol> : <p className={muted}>{concurso.data_prova ? `Data da prova: ${displayStudyDate(concurso.data_prova)}` : 'Esta análise não contém prazos detalhados. Confira as datas no edital original.'}</p>}
      {targetDate && <p className="text-xs text-[#A1A1AA] mt-4">Data definida para o planejamento: {displayStudyDate(targetDate)}</p>}
    </section>
  </div>;
}

export default function StudyProgramWorkspace({ user, programId, api, onBack, onManageSchedule, onNotebook }) {
  const [params, setParams] = useSearchParams();
  const view = STUDY_VIEWS.includes(params.get('view')) ? params.get('view') : 'edital';
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [progress, setProgress] = useState({});
  const [pending, setPending] = useState({});
  const [notes, setNotes] = useState('');
  const [sessionCompleted, setSessionCompleted] = useState(false);
  const pendingRef = useRef(new Set());
  const generationRef = useRef(0);

  const load = useCallback(async () => {
    const generation = ++generationRef.current;
    setError('');
    try {
      const [schedule, vertical] = await Promise.all([
        axios.get(`${api}/study/programs/${programId}/cronograma`, { withCredentials: true }),
        axios.get(`${api}/study/programs/${programId}/edital-verticalizado`, { withCredentials: true }),
      ]);
      if (generationRef.current !== generation) return;
      setData({ ...schedule.data, vertical: vertical.data });
      setProgress(Object.fromEntries((vertical.data.disciplinas || []).map(d => [d.notebook_id, d.topic_progress || {}])));
    } catch (err) { if (generationRef.current === generation) setError(getApiErrorMessage(err, 'Não foi possível carregar este plano.')); }
  }, [api, programId]);
  useEffect(() => { setData(null); load(); return () => { generationRef.current += 1; }; }, [load]);

  const navigate = (next, session = null) => {
    const nextParams = new URLSearchParams(params);
    nextParams.set('view', next);
    if (session) {
      nextParams.set('notebook', session.notebookId);
      nextParams.set('topic', session.key ?? '');
      nextParams.set('minutes', String(Math.min(120, Math.max(1, session.minutes || 25))));
    }
    setParams(nextParams);
    window.scrollTo({ top: 0, behavior: 'auto' });
  };
  const disciplines = data?.vertical?.disciplinas || [];
  const filteredDisciplines = disciplines.filter(d => normalizeStudyText([d.nome, ...topicRows(d).map(t => t.title)].join(' ')).includes(normalizeStudyText(search)));
  const selectedDiscipline = disciplines.find(d => d.notebook_id === params.get('notebook'));
  const selectedTopic = selectedDiscipline && topicRows(selectedDiscipline).find(t => t.key === params.get('topic'));
  const selectedMinutes = Math.min(120, Math.max(1, Number(params.get('minutes')) || 25));
  const sessionKey = `${programId}:${params.get('notebook')}:${params.get('topic')}`;
  const draftsRef = useRef({});
  useEffect(() => {
    setNotes(draftsRef.current[sessionKey] || '');
    setSessionCompleted(false);
  }, [sessionKey]);

  const updateTopic = async (discipline, topic, status, checked) => {
    const key = `${discipline.notebook_id}:${topic.key}:${status}`;
    if (pendingRef.current.has(key)) return;
    pendingRef.current.add(key); setPending(old => ({ ...old, [key]: true }));
    try {
      const response = await axios.post(`${api}/study/notebooks/${discipline.notebook_id}/topic-progress`, { topic_key: topic.key, status, checked }, { withCredentials: true });
      setProgress(old => ({ ...old, [discipline.notebook_id]: { ...old[discipline.notebook_id], [topic.key]: { ...old[discipline.notebook_id]?.[topic.key], [status]: !!response.data.topics?.[topic.key]?.[status] } } }));
    } catch (err) { toast.error(getApiErrorMessage(err, 'Não foi possível atualizar o assunto.')); }
    finally { pendingRef.current.delete(key); setPending(old => ({ ...old, [key]: false })); }
  };

  const program = data?.program;
  const edital = program?.edital_data || {};
  const totalTopics = disciplines.reduce((count, d) => count + topicRows(d).length, 0);
  const studiedTopics = disciplines.reduce((count, d) => count + topicRows(d).filter(t => progress[d.notebook_id]?.[t.key]?.studied).length, 0);

  return <div className="min-h-screen bg-[#050505] text-white flex">
    <Sidebar user={user} />
    <main className="flex-1 min-w-0 md:ml-64 px-4 md:px-8 pt-[84px] md:pt-8 pb-24">
      <div className="max-w-6xl mx-auto space-y-6">
        <Button variant="ghost" onClick={onBack} className="-ml-3 text-[#A1A1AA]"><ArrowLeft className="h-4 w-4 mr-2" />Meus estudos</Button>
        <header className="space-y-3">
          <span className="inline-flex rounded-full border border-purple-500/30 px-3 py-1 text-xs text-purple-300">Plano de estudos</span>
          <h1 className="text-2xl md:text-3xl font-semibold leading-tight">{program?.name || 'Carregando plano…'}</h1>
          {program && <p className={muted}>{edital.concurso?.banca || 'Banca não informada'} · {disciplines.length} disciplinas · {studiedTopics}/{totalTopics} assuntos estudados</p>}
        </header>
        <nav aria-label="Organização do plano" className="flex gap-1 overflow-x-auto border-b border-[#27272A]">{STUDY_VIEWS.map(name => <button key={name} aria-current={view === name ? 'page' : undefined} onClick={() => navigate(name)} className={`shrink-0 px-4 py-3 text-sm border-b-2 ${view === name ? 'border-purple-400 text-purple-300' : 'border-transparent text-[#A1A1AA] hover:text-white'}`}>{labels[name]}</button>)}</nav>
        {error ? <section className={box} role="alert"><p>{error}</p><Button onClick={load} className="mt-4">Tentar novamente</Button></section> : !data ? <div role="status" className="py-20 flex justify-center"><Loader2 className="animate-spin" /></div> : <>
          {view === 'edital' && <div className="space-y-6">
            <EditalOverview concurso={edital.concurso} cargo={edital.cargo_selecionado} filename={edital.pdf_filename} targetDate={program.target_date} />
            <div className="flex flex-wrap gap-3"><Button onClick={() => navigate('verticalizado')} className="bg-purple-600 hover:bg-purple-700"><Layers className="h-4 w-4 mr-2" />Explorar edital verticalizado</Button><Button variant="outline" onClick={() => navigate('cronograma')}><Calendar className="h-4 w-4 mr-2" />Ver cronograma</Button></div>
          </div>}

          {view === 'verticalizado' && <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-4"><div><h2 className="text-xl font-semibold">Conteúdo para estudar</h2><p className={muted}>Disciplina → assunto → subtópico. Acompanhe cada etapa do estudo.</p></div><Button onClick={() => navigate('cronograma')}>Ver cronograma<ChevronRight className="h-4 w-4 ml-2" /></Button></div>
            <label className="flex items-center gap-2 max-w-lg"><Search className="h-4 w-4 text-[#71717A]" /><Input aria-label="Buscar disciplina ou assunto" placeholder="Buscar disciplina ou assunto…" value={search} onChange={e => setSearch(e.target.value)} className="bg-[#101014] border-[#27272A]" /></label>
            {!filteredDisciplines.length && <p className={muted}>Nenhuma disciplina ou assunto encontrado.</p>}
            {filteredDisciplines.map(d => {
              const rows = topicRows(d), done = rows.filter(t => progress[d.notebook_id]?.[t.key]?.studied).length;
              return <details key={d.notebook_id} open={search ? true : undefined} className="rounded-2xl border border-[#27272A] bg-[#101014] overflow-hidden">
                <summary className="cursor-pointer p-5"><span className="font-medium">{d.nome}</span><span className="block sm:inline sm:ml-4 mt-2 sm:mt-0 text-xs text-[#A1A1AA]">Peso {d.peso} · {d.num_questoes ? `${d.num_questoes} questões · ` : ''}{done}/{rows.length} estudados</span><span className="block mt-2 text-xs text-purple-300">Prioridade {d.prioridade}{d.prioridade_provisoria ? ' · provisória' : ''}</span></summary>
                <div className="border-t border-[#27272A] p-4 md:p-5 space-y-3">
                  <p className="text-xs text-[#71717A]">Prioridade da disciplina calculada por {d.prioridade_base}. {d.peso_fonte && `Fonte do peso: ${d.peso_fonte}`}</p>
                  {rows.length ? rows.map(t => <div key={t.key} className={`rounded-xl border border-[#27272A] p-3 ${t.depth ? 'ml-4 md:ml-7' : 'bg-[#15151B]'}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3"><span className={`text-sm ${t.depth ? 'text-[#A1A1AA]' : 'font-medium'}`}>{t.title}</span><Button size="sm" variant="outline" onClick={() => navigate('estudar', { notebookId: d.notebook_id, key: t.key })}><Play className="h-3 w-3 mr-1" />Estudar</Button></div>
                    <div className="flex flex-wrap gap-4 mt-3">{[['studied', 'Estudado'], ['reviewed', 'Revisado'], ['mastered', 'Dominado']].map(([status, label]) => <label key={status} className="text-xs text-[#A1A1AA] flex items-center gap-2"><input type="checkbox" className="accent-purple-500" checked={!!progress[d.notebook_id]?.[t.key]?.[status]} disabled={!!pending[`${d.notebook_id}:${t.key}:${status}`]} onChange={e => updateTopic(d, t, status, e.target.checked)} />{label}</label>)}</div>
                  </div>) : <p className={muted}>Nenhum assunto foi extraído para esta disciplina.</p>}
                </div>
              </details>;
            })}
          </div>}

          {view === 'cronograma' && <div className="space-y-6">
            <section className={box}><div className="flex flex-wrap justify-between gap-4"><div><h2 className="text-xl font-semibold">Sua agenda semanal</h2><p className={`${muted} mt-2`}>Escolha um bloco para abrir a página de estudo com a matéria e a duração previstas.</p></div><Button variant="outline" onClick={() => onManageSchedule(programId)}>Ajustes e exportação</Button></div>{data.estrategia?.resumo && <p className={`${muted} mt-4`}>{data.estrategia.resumo}</p>}</section>
            {data.cronograma?.length ? data.cronograma.map(day => <section key={day.day} className={box}><div className="flex justify-between mb-4"><h3 className="font-semibold">{day.day_label}</h3><span className="text-xs text-[#71717A]">{day.total_minutes} min planejados</span></div><div className="space-y-3">{day.blocos.map(block => {
              const discipline = disciplines.find(d => d.notebook_id === block.notebook_id);
              const firstTopic = discipline && topicRows(discipline).find(t => !progress[discipline.notebook_id]?.[t.key]?.studied);
              return <article key={block.schedule_id} className="rounded-xl border border-[#27272A] p-4 flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs text-purple-300 mb-1">{block.start_time}–{block.end_time} · {block.tipo_estudo || 'Estudo'}</p><h4 className="font-medium text-sm">{block.disciplina_nome}</h4>{firstTopic && <p className="text-xs text-[#A1A1AA] mt-1">Próximo assunto pendente: {firstTopic.title}</p>}</div><Button size="sm" disabled={!discipline} onClick={() => navigate('estudar', { notebookId: block.notebook_id, key: firstTopic?.key, minutes: blockMinutes(block) })}>Estudar<Play className="h-3 w-3 ml-2" /></Button></article>;
            })}</div></section>) : <section className={box}><p className={muted}>Este programa ainda não tem blocos de estudo.</p><Button className="mt-4" onClick={() => onManageSchedule(programId)}>Organizar cronograma</Button></section>}
          </div>}

          {view === 'estudar' && (selectedDiscipline ? <div className="space-y-6" key={sessionKey}>
            <header><p className="text-xs text-purple-300 mb-2">{selectedDiscipline.nome} · {selectedMinutes} minutos</p><h2 className="text-2xl font-semibold">{selectedTopic?.title || 'Sessão de estudo'}</h2></header>
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.8fr)]">
              <div className="space-y-6"><PomodoroTimer key={`${sessionKey}:${selectedMinutes}`} notebooks={data.notebooks} initialNotebookId={selectedDiscipline.notebook_id} initialMinutes={selectedMinutes} lockNotebook topic={[selectedTopic?.title, notes].filter(Boolean).join('\n\n')} onComplete={() => { setSessionCompleted(true); toast.success('Tempo de estudo e anotações registrados.'); }} />
                <section className={box}><h3 className="font-semibold mb-3">Anotações da sessão</h3><Textarea aria-label="Anotações da sessão" rows={7} value={notes} onChange={e => { draftsRef.current[sessionKey] = e.target.value; setNotes(e.target.value); }} placeholder="Resumo, dúvidas e questões para revisar…" className="bg-[#050505] border-[#27272A]" /><p className="text-xs text-[#71717A] mt-2">As anotações são registradas com a sessão ao terminar o cronômetro. Mantenha esta página aberta durante o estudo.</p>{sessionCompleted && <p role="status" className="text-sm text-green-400 mt-3">Sessão registrada.</p>}</section></div>
              <div className="space-y-6"><StudyLessons notebookId={selectedDiscipline.notebook_id} topic={selectedTopic?.title || ''} api={api} /><section className={box}><h3 className="font-semibold mb-3">Progresso do assunto</h3>{selectedTopic ? <div className="space-y-3">{[['studied', 'Marcar como estudado'], ['reviewed', 'Marcar como revisado'], ['mastered', 'Marcar como dominado']].map(([status, label]) => <label key={status} className="flex gap-2 text-sm"><input type="checkbox" className="accent-purple-500" checked={!!progress[selectedDiscipline.notebook_id]?.[selectedTopic.key]?.[status]} disabled={!!pending[`${selectedDiscipline.notebook_id}:${selectedTopic.key}:${status}`]} onChange={e => updateTopic(selectedDiscipline, selectedTopic, status, e.target.checked)} />{label}</label>)}</div> : <p className={muted}>Escolha um assunto no edital verticalizado para acompanhar o progresso.</p>}<Button variant="outline" className="mt-4" onClick={() => onNotebook(data.notebooks.find(n => n.notebook_id === selectedDiscipline.notebook_id))}><BookOpen className="h-4 w-4 mr-2" />Notas e materiais da matéria</Button></section></div>
            </div>
          </div> : <section className={box}><h2 className="text-xl font-semibold mb-2">O que vamos estudar?</h2><p className={muted}>Abra um assunto do edital verticalizado ou um bloco do cronograma para começar.</p><Button className="mt-4" onClick={() => navigate('verticalizado')}>Escolher assunto</Button></section>)}
        </>}
      </div>
    </main>
    <MobileNav user={user} />
  </div>;
}
