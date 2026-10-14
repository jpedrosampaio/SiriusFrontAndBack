import { lazy, Suspense, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { cacheKey } from '@/lib/query-cache';
import { getCurrentUser } from '@/lib/api';
import { openSirius } from '@/lib/sirius-context';
import WhyDetails from '@/components/WhyDetails';
import { formatBRL } from '@/lib/finance-money';
import Onboarding from '@/components/Onboarding';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import ErrorBoundary from '@/components/ErrorBoundary';

const Details = lazy(() => import('./DashboardDetails'));
const Tools = lazy(() => import('@/components/CommandTools'));
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api`;
const button = 'min-h-11 rounded-lg border border-white/15 px-4 py-2 text-sm hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400';
const labels = { preparation: 'Preparação', finance: 'Finanças', training: 'Treinos', nutrition: 'Nutrição', tasks: 'Tarefas', calendar: 'Agenda', habits: 'Hábitos', goals: 'Metas' };
const clock = n => `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
function summary(area) {
  const f = area.facts || {}, unknown = 'desconhecido';
  const values = {
    preparation: `${f.recorded_minutes_today ?? unknown} min de estudo registrados hoje`,
    finance: `${formatBRL(f.expense)} em despesas registradas no mês`,
    training: `${f.completed_today ?? unknown} treino(s) concluído(s) hoje`,
    nutrition: `${f.consumed?.calories?.total ?? unknown} kcal registradas hoje`,
    tasks: `${f.completed_today ?? unknown} conclusão(ões) registrada(s) hoje`,
    calendar: `${f.commitments ?? unknown} compromisso(s) ou alocação(ões) hoje`,
    habits: `${f.completed_today ?? unknown} hábito(s) marcado(s) hoje`,
    goals: `${area.candidate_count} meta(s) com candidato de revisão`,
  };
  return values[area.domain];
}
export default function Dashboard() {
  const [tool, setTool] = useState(null);
  const [params, setParams] = useSearchParams();
  const view = params.get('view') === 'analyses' ? 'analyses' : 'day';
  const selectView = value => setParams(previous => { const next = new URLSearchParams(previous); if (value === 'day') next.delete('view'); else next.set('view', value); return next; }, { replace: true });
  const query = useQuery({ queryKey: cacheKey('command-home'), enabled: view === 'day', queryFn: async ({ signal }) => {
    const [home, user] = await Promise.all([axios.get(`${API}/command/home`, { signal, timeout: 20000 }), getCurrentUser()]);
    return { ...home.data, user: user.data };
  } });
  const data = query.data, next = data?.next_action;
  return <div className="page-container pb-28 max-w-5xl mx-auto space-y-7" data-testid="command-center">
    {view === 'day' && <Onboarding />}
    <header className="pt-5 space-y-2"><p className="text-sm text-sky-300">Sirius · {view === 'day' ? 'Command Center' : 'Seu painel'}</p><h1 data-testid="dashboard-title" className="text-2xl sm:text-3xl font-semibold break-words">{view === 'day' ? `Seu próximo passo${data?.user?.name ? `, ${data.user.name.split(' ')[0]}` : ''}` : 'Análises e evolução'}</h1><p className="text-sm text-slate-400">{view === 'day' ? 'Uma visão do seu dia, com fatos e espaço para decidir.' : 'Indicadores dos seus registros, com estimativas e informações ausentes identificadas.'}</p></header>
    <Tabs value={view} onValueChange={selectView} className="min-w-0">
      <TabsList aria-label="Visão da página inicial" className="grid w-full grid-cols-2 h-auto p-1 mb-6"><TabsTrigger value="day" className="min-h-11">MEU DIA</TabsTrigger><TabsTrigger value="analyses" className="min-h-11">ANÁLISES</TabsTrigger></TabsList>
      <TabsContent value="day" className="space-y-7">
    {query.isPending && <p role="status">Consultando sua vida integrada…</p>}
    {query.isError && <div role="alert" className="rounded-xl border border-amber-400/30 p-4"><p>Não foi possível atualizar o Command Center. {data ? 'A última consulta continua visível.' : 'Tente novamente.'}</p><button className={button} onClick={() => query.refetch()}>Tentar novamente</button></div>}
    {data && <>
      <section aria-labelledby="next-action-title" className="rounded-2xl border border-sky-400/25 bg-sky-400/5 p-4 sm:p-6 space-y-3">
        <h2 id="next-action-title" className="text-xs uppercase tracking-widest text-sky-300">Próxima ação</h2>
        {next ? <><h3 className="text-xl font-medium break-words">{next.title}</h3><p className="text-sm text-slate-400">{clock(next.start_minute)}–{clock(next.end_minute)} · {next.confirmed ? 'Horário registrado' : 'Sugestão para revisar'}</p><Link className={`${button} inline-flex items-center bg-sky-600/20`} to={next.link}>{next.confirmed ? 'Abrir atividade' : 'Conferir atividade'}</Link><WhyDetails why={next.why} /></> : <><p>Nenhuma próxima ação alocada com segurança.</p><Link className={`${button} inline-flex items-center`} to="/calendar">Conferir disponibilidade e agenda</Link></>}
        <p className="text-xs text-slate-400">{data.date} · {data.timezone}. Nenhuma sugestão altera seus registros automaticamente.</p>
      </section>
      <section aria-labelledby="today-title" className="space-y-3"><div className="flex flex-wrap justify-between gap-2"><h2 id="today-title" className="text-lg font-semibold">Hoje</h2><Link to="/calendar" className="text-sm min-h-11 inline-flex items-center text-sky-300 underline">Abrir agenda</Link></div>
        <ol className="divide-y divide-white/10">{(data.today || []).map(row => <li key={row.id} className="py-3"><div className="flex flex-wrap gap-x-4 gap-y-1"><span className="text-sm tabular-nums text-sky-200">{clock(row.start_minute)}–{clock(row.end_minute)}</span><Link className="break-words flex-1 min-w-0 underline" to={row.link}>{row.title}</Link></div><p className="text-xs text-slate-400 mt-1">{row.confirmed ? 'Registrado' : 'Prévia não confirmada'}{row.ambiguous ? ' · Mudança de horário; confira a agenda' : ''}</p><WhyDetails why={row.why} /></li>)}</ol>
        {!data.today?.length && <p className="text-sm text-slate-400">Nenhum compromisso ou sugestão alocada hoje.</p>}
        {data.today_count > data.today?.length && <p className="text-sm">Exibindo {data.today.length} de {data.today_count}. A agenda mantém todos os registros.</p>}
        {!!data.unscheduled_count && <p className="text-sm text-amber-200">{data.unscheduled_count} atividade(s) aguardam horário ou duração declarada.</p>}
        {(data.warnings || []).map(w => <p className="text-sm text-amber-200" key={w}>{w}</p>)}
      </section>
      <section aria-labelledby="attention-title" className="space-y-3"><h2 id="attention-title" className="text-lg font-semibold">Atenção</h2>
        {!data.attention?.length && <p className="text-sm text-slate-400">Nenhuma pendência importante identificada nas fontes consultadas.</p>}
        {(data.attention || []).map(row => <article className="border-l-2 border-amber-300/50 pl-4" key={row.id}><Link className="min-h-11 inline-flex items-center break-words underline" to={row.link}>{row.title}</Link>{row.subtitle && <p className="text-sm text-slate-400">{row.subtitle}</p>}<WhyDetails why={row.why} /></article>)}
        {data.attention_count > data.attention?.length && <p className="text-xs text-slate-400">{data.attention_count} pendências identificadas; as primeiras {data.attention.length} aparecem aqui.</p>}
      </section>
      <section aria-labelledby="areas-title" className="space-y-3"><h2 id="areas-title" className="text-lg font-semibold">Áreas</h2><ul className="divide-y divide-white/10">{(data.areas || []).map(area => <li key={area.domain} className="py-3 flex flex-wrap gap-2 items-center justify-between"><div className="min-w-0"><h3 className="font-medium">{labels[area.domain]}</h3><p className="text-sm text-slate-400 break-words">{summary(area)}{area.truncated ? ' · Consulta limitada' : ''}</p></div><Link className={`${button} inline-flex items-center`} to={area.link}>Abrir {labels[area.domain]}</Link></li>)}</ul></section>
    </>}
    <section aria-label="Ferramentas do Command Center" className="space-y-3 border-t border-white/10 pt-5"><div className="flex flex-wrap gap-2">{[['scenarios','Simular cenários'],['memory','Memória explícita'],['audit','Histórico de ações'],['export','Exportar dados']].map(([id,label]) => <button className={button} key={id} aria-pressed={tool===id} onClick={() => setTool(tool===id ? null : id)}>{label}</button>)}<button className={button} onClick={() => openSirius({ intent:'next_action',draft:'O que devo fazer agora?' })}>Perguntar ao Sirius</button><button className={button} onClick={() => selectView('analyses')}>Painel detalhado</button></div>
      {tool && <Suspense fallback={<p role="status">Carregando ferramenta…</p>}><Tools key={tool} initialTab={tool} onClose={() => setTool(null)} /></Suspense>}
    </section>
      </TabsContent>
      <TabsContent value="analyses" className="min-w-0"><ErrorBoundary><Suspense fallback={<p role="status">Carregando painel detalhado…</p>}><Details embedded /></Suspense></ErrorBoundary></TabsContent>
    </Tabs>
  </div>;
}
