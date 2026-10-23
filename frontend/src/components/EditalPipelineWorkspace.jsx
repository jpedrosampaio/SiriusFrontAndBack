import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { ArrowLeft, FileText, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import useEditalPipeline from '@/hooks/useEditalPipeline';
import EditalProviderPlan from '@/components/EditalProviderPlan';
import EditalProgressOverview from '@/components/EditalProgressOverview';
import EditalProviderDiagnostic from '@/components/EditalProviderDiagnostic';
import { sessionVersion } from '@/lib/query-cache';
import { getApiErrorMessage } from '@/lib/api-errors';
import { openSirius } from '@/lib/sirius-context';
import '@/components/edital-workspace.css';

const panel = 'edital-surface scroll-mt-24 space-y-4';
const field = 'w-full min-w-0 rounded-lg border border-white/10 bg-zinc-950 px-3 py-2 text-sm';
const factStates = { extracted: 'Extraído com evidência · confira a interpretação', missing: 'Não informado', ambiguous: 'Ambíguo · exige correção', corrected_by_user: 'Informado ou corrigido por você' };
const ruleLabels = { weight: 'Peso', question_count: 'Quantidade de questões', penalty: 'Penalização', blank_score: 'Pontuação em branco', time_limit: 'Duração', evaluation_criterion: 'Critério de avaliação' };
const auditLabels = { correct_fact: 'Correção de informação', add_general_fact: 'Informação manual acrescentada', edit_program_structure: 'Conteúdo reorganizado', resolve_review_issue: 'Pendência conferida', confirm_role: 'Cargo e conteúdo confirmados', reopen_confirmed_review: 'Conferência reaberta', reanalyze_sections: 'Seções reanalisadas', correct_section_association: 'Associação corrigida', edit_exam_rule: 'Regra de prova corrigida', import_confirmed_program: 'Programa importado' };
const labels = { name: 'Nome', code: 'Código', vacancies: 'Vagas', salary: 'Remuneração', requirements: 'Requisitos',
  exam_name: 'Concurso', board: 'Banca', exam_date: 'Data da prova', registration_start: 'Início das inscrições', registration_end: 'Fim das inscrições',
  fee: 'Taxa', schedule_event: 'Cronograma', external_reference: 'Referência externa', document_relationship: 'Relação entre documentos' };

function Sources({ fact, onSource }) {
  return <div className="space-y-2 text-xs text-slate-400">{(fact?.sources || []).slice(0, 6).map((source, i) => <div key={`${source.block_id}:${i}`}>
    <Button type="button" size="sm" variant="ghost" className="text-blue-300 px-0" onClick={() => onSource(source)}>Consultar página {source.page}</Button>
    <blockquote className="border-l-2 border-blue-400/40 pl-3 whitespace-pre-wrap [overflow-wrap:anywhere]">{source.quote}</blockquote>
  </div>)}{fact?.human_note && <p className="text-emerald-300">Justificativa: {fact.human_note}</p>}</div>;
}

function Fact({ title, fact, target, identity, field: property, editable, revision, command, pending, onSource }) {
  const [draft, setDraft] = useState(null);
  const save = async event => {
    event.preventDefault();
    if (await command('facts', { ...draft, value: draft.value || null, target, identity, field: property })) setDraft(null);
  };
  return <div className="border-t border-slate-800 pt-3 space-y-2 min-w-0">
    <div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="text-xs text-slate-400">{title}</h3>
      <p className="text-sm whitespace-pre-wrap [overflow-wrap:anywhere]">{fact?.value ?? 'Não informado'}</p></div>
      {editable && !draft && <Button size="sm" variant="ghost" disabled={pending} aria-label={`Corrigir ${title}`} onClick={() => setDraft({ value: fact?.value || '', note: '', revision })}>Corrigir</Button>}</div>
    <p className={`text-xs ${fact?.state === 'ambiguous' ? 'text-amber-300' : 'text-slate-400'}`}>{factStates[fact?.state || 'missing']}{fact?.verification === 'confirmed' ? ' · conferido' : ''}</p>
    {(fact?.sources?.length > 0 || fact?.human_note || fact?.alternatives?.length > 0) && <details><summary className="text-xs cursor-pointer py-2 text-blue-300">Evidências e alternativas</summary><Sources fact={fact} onSource={onSource} />
      {(fact.alternatives || []).slice(0, 12).map((alternative, i) => <div key={i} className="mt-3 border-l-2 border-amber-400/30 pl-3"><p className="text-sm [overflow-wrap:anywhere]">Alternativa: {alternative.value}</p><Sources fact={alternative} onSource={onSource} /></div>)}</details>}
    {draft && <form onSubmit={save} className="rounded-xl bg-slate-950 p-3 space-y-3">
      <label className="block text-xs">Valor de {title}<Textarea aria-label={`Valor de ${title}`} className={field} maxLength={2000} value={draft.value} onChange={e => setDraft({ ...draft, value: e.target.value })} /></label>
      <label className="block text-xs">Origem e justificativa da correção<Textarea required minLength={3} maxLength={1000} className={field} value={draft.note} onChange={e => setDraft({ ...draft, note: e.target.value })} /></label>
      <p className="text-xs text-slate-400">Novos valores ficam identificados como declaração sua. As evidências anteriores permanecem no histórico. Para data da prova, use AAAA-MM-DD.</p>
      <div className="flex flex-wrap gap-2"><Button size="sm" disabled={pending || draft.note.trim().length < 3}>Salvar correção</Button><Button type="button" size="sm" variant="ghost" disabled={pending} onClick={() => setDraft(null)}>Cancelar correção</Button></div>
    </form>}
  </div>;
}

function SourcePage({ api, analysisId, source, onClose }) {
  const [data, setData] = useState(null), [error, setError] = useState('');
  useEffect(() => {
    if (!source) return;
    const controller = new AbortController(), version = sessionVersion();setData(null);setError('');
    axios.get(`${api}/study/edital-pipeline/${analysisId}/source/${source.page}`, { signal: controller.signal, timeout: 20000 })
      .then(response => { if (!controller.signal.aborted && version === sessionVersion()) setData(response.data); })
      .catch(failure => { if (!controller.signal.aborted && version === sessionVersion()) setError(getApiErrorMessage(failure, 'Não foi possível consultar esta página.')); });
    return () => controller.abort();
  }, [api, analysisId, source]);
  return <Dialog open={!!source} onOpenChange={open => { if (!open) onClose(); }}><DialogContent className="w-[calc(100vw-24px)] max-w-3xl max-h-[90dvh] overflow-y-auto bg-slate-950 text-white border-slate-700">
    <DialogHeader><DialogTitle>Página {source?.page} · texto extraído</DialogTitle><DialogDescription>Esta visualização preserva os trechos salvos. O PDF original não foi armazenado e o layout pode exigir conferência no seu arquivo.</DialogDescription></DialogHeader>
    {error && <p role="alert" className="text-amber-300">{error}</p>}{!data && !error && <p role="status">Carregando página…</p>}
    {data && <div className="space-y-3 text-sm">{data.blocks.map(block => <p key={block.id} className={`whitespace-pre-wrap [overflow-wrap:anywhere] ${block.id === source?.block_id ? 'rounded-lg bg-blue-500/20 p-3 border border-blue-400/40' : 'text-slate-300'}`}>{block.text}</p>)}</div>}
    <Button variant="outline" onClick={onClose}>Fechar página</Button>
  </DialogContent></Dialog>;
}

function ReviewAction({ action, identity, target, command, pending, children }) {
  const [note, setNote] = useState('');
  return <form onSubmit={async e => { e.preventDefault();if (await command('resolve', { kind: action, identity, target, note })) setNote(''); }} className="space-y-2 border-t border-slate-700 pt-3">
    {children}<label className="block text-xs">Como você conferiu esta pendência?<Textarea className={field} required minLength={3} maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></label>
    <Button size="sm" disabled={pending || note.trim().length < 3}>Registrar conferência</Button>
  </form>;
}

function AuditEntry({ item, api, analysisId }) {
  const [snapshot, setSnapshot] = useState(null), [error, setError] = useState(''), [loading, setLoading] = useState(false);
  const request = useRef(null);
  useEffect(() => () => request.current?.abort(), []);
  const load = async () => {
    if (request.current) return;
    const controller = new AbortController(), version = sessionVersion();request.current = controller;setLoading(true);setError('');
    try { const response = await axios.get(`${api}/study/edital-pipeline/${analysisId}/history/${item.id}`, { signal: controller.signal, timeout: 20000 });
      if (!controller.signal.aborted && version === sessionVersion()) setSnapshot(response.data);
    } catch (failure) { if (!controller.signal.aborted && version === sessionVersion()) setError(getApiErrorMessage(failure, 'Não foi possível consultar esta revisão.')); }
    finally { if (request.current === controller) request.current = null;if (!controller.signal.aborted && version === sessionVersion()) setLoading(false); }
  };
  return <details className="text-xs border-t border-slate-800 py-2"><summary className="cursor-pointer">{new Date(item.at).toLocaleString('pt-BR')} · {auditLabels[item.action] || 'Revisão registrada'}</summary>
    <p className="mt-2 text-slate-300 [overflow-wrap:anywhere]">{item.note || 'Registro preservado da ação e de seus dados anteriores.'}</p>
    {!snapshot && <Button variant="ghost" size="sm" disabled={loading} onClick={load}>Consultar dados desta revisão</Button>}{error && <p role="alert" className="text-amber-200">{error}</p>}
    {snapshot && <details className="mt-2"><summary className="cursor-pointer text-slate-400">Dados salvos desta revisão</summary><pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap [overflow-wrap:anywhere]">{JSON.stringify({ antes: snapshot.before, depois: snapshot.after }, null, 2)}</pre></details>}
  </details>;
}


function PriorPrograms({ api, analysisId, onImported }) {
  const [data, setData] = useState(null), [error, setError] = useState(''), [loading, setLoading] = useState(false);
  const request = useRef(null);
  useEffect(() => () => request.current?.abort(), []);
  const load = async (offset = 0) => {
    if (request.current) return;
    const controller = new AbortController(), version = sessionVersion();request.current = controller;setLoading(true);setError('');
    try { const response = await axios.get(`${api}/study/edital-pipeline/${analysisId}/import-candidates?offset=${offset}`, { signal: controller.signal, timeout: 20000 });
      if (!controller.signal.aborted && version === sessionVersion()) setData(previous => ({ ...response.data, programs: offset ? [...previous.programs, ...response.data.programs] : response.data.programs }));
    } catch (failure) { if (!controller.signal.aborted && version === sessionVersion()) setError(getApiErrorMessage(failure, 'Não foi possível consultar os programas anteriores.')); }
    finally { if (request.current === controller) request.current = null;if (!controller.signal.aborted && version === sessionVersion()) setLoading(false); }
  };
  return <div className="space-y-3"><Button variant="outline" disabled={loading} onClick={() => load()}>Ver programas já criados deste PDF</Button>
    {error && <p role="alert" className="text-sm text-amber-200">{error}</p>}{data && !data.programs.length && <p className="text-xs text-slate-400">Nenhum programa anterior identificado com este documento.</p>}
    {data?.programs.map(program => <div className="rounded-xl border border-slate-700 p-3 text-sm [overflow-wrap:anywhere]" key={program.program_id}><p>{program.name}{program.archived ? ' · arquivado' : ''}</p>
      {!program.archived && <Button size="sm" variant="ghost" onClick={() => onImported?.({ program, message: 'Programa anterior aberto. A nova análise permanece salva; nenhum conteúdo ou histórico foi sobrescrito.' })}>Abrir programa anterior</Button>}</div>)}
    {data?.next_offset != null && <Button variant="ghost" disabled={loading} onClick={() => load(data.next_offset)}>Mais programas anteriores</Button>}
  </div>;
}

export default function EditalPipelineWorkspace({ api, analysisId, areas, defaultAreaId, form, onFormChange, onBack, onImported }) {
  const query = useEditalPipeline(api, analysisId), { command, pending } = query;
  const [roleId, setRoleId] = useState(''), [disciplineId, setDisciplineId] = useState(''), [source, setSource] = useState(null);
  const [note, setNote] = useState(''), [acknowledged, setAcknowledged] = useState(false), [areaId, setAreaId] = useState(defaultAreaId || '');
  const [structure, setStructure] = useState({ action: 'add_topic', title: '', topic_id: '', parent_id: '', note: '' });
  const [general, setGeneral] = useState({ field: 'exam_date', value: '', note: '' });
  const [newVersion, setNewVersion] = useState(false), [topicPage, setTopicPage] = useState(0), [sectionPage, setSectionPage] = useState(0);
  const [section, setSection] = useState(''), [decision, setDecision] = useState('include'), [sectionNote, setSectionNote] = useState('');
  const [history, setHistory] = useState(null), [historyError, setHistoryError] = useState('');
  const [ruleDraft, setRuleDraft] = useState({ action: 'add', target_scope: 'discipline', kind: 'weight', target: '', value: '', rule_id: '', note: '' });
  const [sourceNumber, setSourceNumber] = useState(1);
  const historyRequest = useRef(null);
  useEffect(() => () => historyRequest.current?.abort(), [analysisId]);
  const data = query.data, state = data?.manifest, scope = state?.scopes?.[state?.selected_role_id];
  const role = state?.inventory.roles.find(r => r.id === (roleId || state.selected_role_id)) || state?.inventory.roles[0];
  const disciplines = scope?.program.disciplines || [], discipline = disciplines.find(d => d.id === disciplineId) || disciplines[0];
  const editingSelectedRole = role?.id === state?.selected_role_id;
  const editable = state?.status === 'awaiting_review' && scope?.status === 'awaiting_review' && editingSelectedRole;
  const unresolved = state && scope && [[state.inventory, data.review?.inventory_issues], [scope, data.review?.program_issues]].some(([value, issues]) =>
    Object.keys(value.findings || {}).some(identity => !value.finding_resolutions?.[identity]) || (issues || []).some(issue => !value.issue_resolutions?.[issue.id]));
  const facts = { editable, revision: data?.revision, command, pending, onSource: setSource };
  const topicNames = Object.fromEntries((discipline?.topics || []).map(t => [t.id, t.title.value]));
  const sectionRows = data?.review?.sections || [];
  const loadHistory = async (offset = 0) => {
    if (historyRequest.current) return;
    const version = sessionVersion(), controller = new AbortController();historyRequest.current = controller;setHistoryError('');
    try { const response = await axios.get(`${api}/study/edital-pipeline/${analysisId}/history?offset=${offset}`, { signal: controller.signal, timeout: 20000 });
      if (!controller.signal.aborted && version === sessionVersion()) setHistory(previous => ({ rows: offset ? Array.from(new Map([...previous.rows, ...response.data.history].map(item => [item.id, item])).values()) : response.data.history, hasMore: response.data.has_more }));
    } catch (failure) { if (!controller.signal.aborted && version === sessionVersion()) setHistoryError(getApiErrorMessage(failure, 'Não foi possível abrir o histórico.')); }
    finally { if (historyRequest.current === controller) historyRequest.current = null; }
  };
  const sections = sectionRows.slice(sectionPage * 20, (sectionPage + 1) * 20);
  const selectedSection = sectionRows.find(s => s.key === section);
  const available = scope?.status === 'completed' && state?.selected_role_id === role?.id;
  return <main className="edital-workspace min-h-screen px-3 sm:px-7 py-4 sm:py-7 pb-28"><div className="max-w-6xl mx-auto space-y-5">
    <Button variant="ghost" onClick={onBack}><ArrowLeft size={16} className="mr-2" />Meus estudos</Button>
    <header className="flex flex-wrap items-center justify-between gap-5 pb-1"><div className="min-w-0 flex-1"><p className="edital-kicker">Estudos / Editais salvos</p><h1 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100 sm:text-3xl">Conferir meu edital</h1><div className="mt-3 flex min-w-0 items-center gap-2 text-xs text-zinc-500"><FileText size={14} className="shrink-0" /><p className="min-w-0 [overflow-wrap:anywhere]">{data?.filename || 'Abrindo análise salva'}</p></div></div>{state && <span className="hidden shrink-0 items-center gap-2 rounded-full border border-white/10 sm:inline-flex px-3 py-1.5 text-[11px] text-zinc-400"><span className="h-1.5 w-1.5 rounded-full bg-lime-200" aria-hidden="true" />Documento salvo</span>}</header>
    {(query.isError || query.commandError) && <div role="alert" className="rounded-xl border border-amber-500/40 p-4 text-sm text-amber-200"><p>{query.commandError || getApiErrorMessage(query.error, 'Não foi possível abrir a análise salva.')}</p><Button variant="outline" disabled={query.isFetching} className="mt-3" onClick={() => query.refetch()}>Atualizar estado salvo</Button></div>}
    {!state ? !query.isError && <p role="status" className="flex gap-2"><Loader2 className="animate-spin" />Abrindo checkpoints…</p> : <>
      <nav aria-label="Navegação da análise" className="edital-nav sticky top-0 z-10 flex gap-5 overflow-x-auto border-b border-white/[0.08] bg-[#101114]/95 backdrop-blur"><a href="#edital-progress">Visão geral</a><a href="#edital-roles">Cargos e informações</a>{scope && <a href="#edital-program">Conteúdo</a>}<a href="#edital-history">Histórico</a></nav>
      <section id="edital-progress" className="scroll-mt-24 space-y-5" aria-label="Progresso real da análise"><div className="grid items-start gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.15fr)]"><div className="order-1 min-w-0 lg:order-2"><EditalProviderPlan key={data.analysis_id} contextKey={`${data.analysis_id}:${data.revision}`} plan={data.execution_plan} diagnostics={data.diagnostics} state={state} command={command} pending={pending} /></div><div className="order-2 min-w-0 lg:order-1"><EditalProgressOverview data={data} pending={pending} fetching={query.isFetching} onRefresh={() => query.refetch()} /></div></div>
        {!!state.source.low_text_pages?.length && <p className="text-sm text-amber-200">Baixa quantidade de texto nas páginas {state.source.low_text_pages.join(', ')}. Confira essas páginas no PDF antes de confirmar o conteúdo.</p>}
        {!!state.source.image_pages?.length && <p className="text-xs text-amber-200">Há imagens nas páginas {state.source.image_pages.join(', ')}. Confira se todo conteúdo exigido também aparece no texto salvo. A identificação de regiões sem texto é conservadora e não substitui essa conferência.</p>}
        {state.source.warnings?.includes('column_order_is_a_layout_hint') && <p className="text-xs text-amber-200">O documento contém colunas. A ordem extraída é uma aproximação do layout e exige conferência no original.</p>}
        <form className="flex flex-wrap items-end gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] p-4" onSubmit={e => { e.preventDefault();setSource({ page: sourceNumber }); }}><label className="text-xs text-slate-300">Consultar texto da página<Input aria-label="Número da página extraída" type="number" min="1" max={state.source.pages} step="1" className={`${field} mt-2 max-w-28`} value={sourceNumber} onChange={e => setSourceNumber(Number(e.target.value))} /></label><Button size="sm" variant="outline" disabled={!Number.isInteger(sourceNumber) || sourceNumber < 1 || sourceNumber > state.source.pages}>Consultar página extraída</Button><p className="text-xs leading-relaxed text-slate-500 sm:ml-auto sm:max-w-xs">Consulte a fonte enquanto a análise está pausada. O texto extraído permanece disponível.</p></form>
        {state.status === 'processing' && <Button variant="outline" disabled={pending} onClick={() => command('cancel')}>Cancelar processamento</Button>}
        {['cancelled', 'waiting_provider', 'quota_paused', 'recoverable_failure'].includes(state.status) && <div className="space-y-3"><p className="text-sm text-amber-200">Os checkpoints válidos foram preservados. Confira o diagnóstico antes de retomar. A liberação de cota não está confirmada.</p>
          {state.retry_at && <p className="text-xs">Nova tentativa a partir de {new Date(state.retry_at).toLocaleString('pt-BR')}.</p>}
          {!data.execution_plan && <><Button disabled={pending || (!!state.retry_at && Date.parse(state.retry_at) > Date.now())} onClick={() => command('resume')}>Retomar lotes pendentes</Button>
          {state.budget.provider_limit < 200 && <Button variant="outline" disabled={pending} onClick={() => window.confirm('Autorizar até 200 tentativas totais nesta análise? Isso amplia o orçamento de chamadas, sem garantir cota ou sucesso.') && command('resume', { provider_limit: 200 })}>Ampliar limite e retomar</Button>}</>}</div>}
        {state.status === 'ocr_required' && <p role="status" className="text-amber-200 text-sm">Páginas {state.source.ocr_required_pages.join(', ')} requerem OCR. O OCR local não está disponível neste ambiente. Nenhuma análise completa será confirmada com essa lacuna; envie um PDF com texto pesquisável.</p>}
        {state.error_kind && <p className="text-xs text-amber-200 [overflow-wrap:anywhere]">{data.error_message || 'Confira as pendências e os lotes salvos antes de retomar.'}</p>}
        {!data.worker_configured && <p role="alert" className="text-amber-200 text-sm">O processamento não está configurado neste backend. Seus dados salvos continuam acessíveis.</p>}
      </section>
      <section id="edital-roles" className={panel}><h2 className="font-semibold">Cargos e informações gerais</h2>{!state.inventory.roles.length && <div className="rounded-xl border border-dashed border-slate-700 bg-slate-950/30 p-6 text-center"><FileText size={25} className="mx-auto mb-3 text-slate-500" /><p className="text-sm text-slate-300">Os cargos aparecerão aqui após a descoberta validada.</p><p className="mt-2 text-xs text-slate-500">Nenhum cargo será criado com base em uma tentativa recusada ou em dados sem evidência.</p></div>}<label className="block text-sm">Cargo / especialidade<select aria-label="Cargo / especialidade" className={`${field} mt-2`} value={role?.id || ''} disabled={pending} onChange={e => setRoleId(e.target.value)}><option value="" disabled>Nenhum cargo identificado ainda</option>{state.inventory.roles.map(r => <option key={r.id} value={r.id}>{r.name.value || r.code.value || 'Identificação a conferir'}</option>)}</select></label>
        {role && <Button disabled={pending || state.status === 'ocr_required'} onClick={async () => { if (await command('select-role', { role_id: role.id })) { setDisciplineId('');setTopicPage(0); } }}>Abrir análise deste cargo</Button>}
        <p className="text-xs text-slate-400">Inventário {state.inventory.status === 'awaiting_review' ? 'extraído e comparado; ainda sujeito à sua conferência' : 'parcial'}. Os outros cargos permanecem disponíveis para análise posterior.</p>
        {role && <div className="grid sm:grid-cols-2 gap-4">{['name', 'code', 'vacancies', 'salary', 'requirements'].map(property => <Fact key={`${role.id}:${property}`} {...facts} title={labels[property]} fact={role[property]} target="role" identity={role.id} field={property} />)}</div>}
        <details><summary className="cursor-pointer py-2 text-sm">Informações e datas do concurso</summary><div className="space-y-3">{state.inventory.facts.map(item => <Fact key={item.id} {...facts} title={labels[item.key] || item.key} fact={item.fact} target="general" identity={item.id} field="fact" />)}</div>
          {editable && <form className="mt-4 space-y-3" onSubmit={async e => { e.preventDefault();if (await command('general-facts', general)) setGeneral({ ...general, value: '', note: '' }); }}>
            <label className="block text-xs">Informação ausente<select className={field} value={general.field} onChange={e => setGeneral({ ...general, field: e.target.value })}>{['exam_name', 'board', 'exam_date', 'registration_start', 'registration_end', 'fee', 'schedule_event', 'external_reference'].map(k => <option key={k} value={k}>{labels[k]}</option>)}</select></label>
            <label className="block text-xs">Valor informado<Input required maxLength={2000} className={field} value={general.value} onChange={e => setGeneral({ ...general, value: e.target.value })} /></label>
            <label className="block text-xs">Fonte e justificativa<Textarea required minLength={3} maxLength={1000} className={field} value={general.note} onChange={e => setGeneral({ ...general, note: e.target.value })} /></label><Button disabled={pending || general.note.trim().length < 3}>Registrar informação manual</Button>
          </form>}</details>
      </section>
      {scope && <>
        {!editingSelectedRole && <p role="status" className="rounded-xl border border-amber-500/40 p-4 text-sm text-amber-200">O conteúdo abaixo pertence ao cargo em análise. Para conferir o cargo escolhido na lista, clique em “Abrir análise deste cargo”.</p>}
        <section id="edital-program" className={panel}><h2 className="font-semibold">Edital verticalizado do cargo em análise</h2><p className="text-sm text-slate-400">{disciplines.length} disciplinas extraídas para {state.inventory.roles.find(r => r.id === state.selected_role_id)?.name.value}. Campos desconhecidos e regras por grupo permanecem separados.</p>
          {!!disciplines.length && <label className="block text-sm">Disciplina<select className={`${field} mt-2`} value={discipline?.id || ''} onChange={e => { setDisciplineId(e.target.value);setTopicPage(0); }}>{disciplines.map(d => <option key={d.id} value={d.id}>{d.name.value}</option>)}</select></label>}
          {discipline && <div className="space-y-3"><Fact key={`${discipline.id}:name`} {...facts} title="Disciplina" fact={discipline.name} target="discipline" identity={discipline.id} field="name" />
            {['stage', 'group'].map(property => <Fact key={`${discipline.id}:${property}`} {...facts} title={property === 'stage' ? 'Etapa de avaliação' : 'Grupo de conhecimentos'} fact={discipline[property]} target="discipline" identity={discipline.id} field={property} />)}
            <h3 className="text-sm font-semibold pt-3">Assuntos e subtópicos</h3>{discipline.topics.slice(topicPage * 30, (topicPage + 1) * 30).map(topic => <div key={topic.id} className="rounded-xl border border-slate-800 p-3 min-w-0">
              {topic.parent_id && <p className="text-xs text-slate-400 [overflow-wrap:anywhere]">Pertence a: {topicNames[topic.parent_id] || 'Assunto pai a conferir'}</p>}
              <Fact {...facts} title={`${topic.numbering ? `${topic.numbering} · ` : ''}Assunto`} fact={topic.title} target="topic" identity={topic.id} field="title" />
            </div>)}<div className="flex flex-wrap gap-2 items-center text-xs"><Button size="sm" variant="ghost" disabled={!topicPage} onClick={() => setTopicPage(n => n - 1)}>Assuntos anteriores</Button><span>{Math.min(topicPage * 30 + 1, discipline.topics.length)}–{Math.min((topicPage + 1) * 30, discipline.topics.length)} de {discipline.topics.length}</span><Button size="sm" variant="ghost" disabled={(topicPage + 1) * 30 >= discipline.topics.length} onClick={() => setTopicPage(n => n + 1)}>Próximos assuntos</Button></div>
          </div>}
          {editable && <details><summary className="py-2 text-sm cursor-pointer">Adicionar, remover ou reorganizar conteúdo</summary><form className="space-y-3" onSubmit={async e => { e.preventDefault();if (await command('structure', { ...structure, discipline_id: discipline?.id || null, topic_id: structure.topic_id || null, parent_id: structure.parent_id || null, title: structure.title || null })) setStructure({ ...structure, title: '', topic_id: '', parent_id: '', note: '' }); }}>
            <label className="block text-xs">Alteração<select className={field} value={structure.action} onChange={e => setStructure({ ...structure, action: e.target.value })}>{Object.entries({ add_topic: 'Adicionar assunto', add_discipline: 'Adicionar disciplina', remove_discipline: 'Remover disciplina atual', remove_topic: 'Remover assunto e descendentes', move_topic: 'Alterar assunto pai' }).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            {['add_topic', 'add_discipline'].includes(structure.action) && <label className="block text-xs">Nome do conteúdo<Input required maxLength={2000} className={field} value={structure.title} onChange={e => setStructure({ ...structure, title: e.target.value })} /></label>}
            {['move_topic', 'remove_topic'].includes(structure.action) && <label className="block text-xs">Assunto a alterar<select required className={field} value={structure.topic_id} onChange={e => setStructure({ ...structure, topic_id: e.target.value })}><option value="">Selecione</option>{(discipline?.topics || []).map(t => <option key={t.id} value={t.id}>{t.title.value}</option>)}</select></label>}
            {['move_topic', 'add_topic'].includes(structure.action) && <label className="block text-xs">Assunto pai<select className={field} value={structure.parent_id} onChange={e => setStructure({ ...structure, parent_id: e.target.value })}><option value="">Assunto principal</option>{(discipline?.topics || []).map(t => <option key={t.id} value={t.id}>{t.title.value}</option>)}</select></label>}
            <label className="block text-xs">Justificativa da alteração<Textarea required minLength={3} maxLength={1000} className={field} value={structure.note} onChange={e => setStructure({ ...structure, note: e.target.value })} /></label><Button disabled={pending || structure.note.trim().length < 3}>Aplicar alteração de conteúdo</Button>
          </form></details>}
        </section>
        <section className={panel}><h2 className="font-semibold">Regras, pesos e quantidades</h2><p className="text-xs text-slate-400">Um total de questões ou peso do grupo não é copiado para cada disciplina. Ausência de regra não significa valor zero.</p>
          {!scope.program.rules.length && <p className="text-sm text-slate-400">Nenhuma regra identificada para este cargo. Confira o edital original.</p>}
          {scope.program.rules.map(rule => <details key={rule.id}><summary className="py-2 text-sm cursor-pointer [overflow-wrap:anywhere]">{ruleLabels[rule.kind]} · {({ group: 'Grupo', discipline: 'Disciplina', stage: 'Etapa' })[rule.target_scope]}: {rule.target.value} · {rule.fact.value ?? 'Não informado'}</summary>
            <Fact {...facts} title="Aplicação da regra" fact={rule.target} target="rule" identity={rule.id} field="target" /><Fact {...facts} title="Valor da regra" fact={rule.fact} target="rule" identity={rule.id} field="fact" /></details>)}
          {editable && <details><summary className="cursor-pointer py-2 text-sm">Registrar regra ausente ou remover associação incorreta</summary><form className="space-y-3" onSubmit={async e => { e.preventDefault();if (await command('rules', { ...ruleDraft, rule_id: ruleDraft.rule_id || null, target: ruleDraft.target || null, value: ruleDraft.value || null })) setRuleDraft({ ...ruleDraft, target: '', value: '', rule_id: '', note: '' }); }}>
            <label className="block text-xs">Operação<select className={field} value={ruleDraft.action} onChange={e => setRuleDraft({ ...ruleDraft, action: e.target.value })}><option value="add">Registrar regra manual</option><option value="remove">Remover regra incorreta</option></select></label>
            {ruleDraft.action === 'remove' ? <label className="block text-xs">Regra a remover<select className={field} required value={ruleDraft.rule_id} onChange={e => setRuleDraft({ ...ruleDraft, rule_id: e.target.value })}><option value="">Selecione</option>{scope.program.rules.map(r => <option key={r.id} value={r.id}>{r.kind}: {r.target.value} · {r.fact.value}</option>)}</select></label> : <>
              <label className="block text-xs">Aplicação<select className={field} value={ruleDraft.target_scope} onChange={e => setRuleDraft({ ...ruleDraft, target_scope: e.target.value })}><option value="discipline">Disciplina</option><option value="group">Grupo</option><option value="stage">Etapa</option></select></label>
              <label className="block text-xs">Tipo de regra<select className={field} value={ruleDraft.kind} onChange={e => setRuleDraft({ ...ruleDraft, kind: e.target.value })}>{Object.entries({ weight: 'Peso', question_count: 'Quantidade de questões', time_limit: 'Duração', penalty: 'Penalização', blank_score: 'Pontuação em branco', evaluation_criterion: 'Critério de avaliação' }).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
              <label className="block text-xs">Nome exato da disciplina, grupo ou etapa<Input required maxLength={2000} className={field} value={ruleDraft.target} onChange={e => setRuleDraft({ ...ruleDraft, target: e.target.value })} /></label>
              <label className="block text-xs">Valor e unidade<Input required maxLength={2000} className={field} value={ruleDraft.value} onChange={e => setRuleDraft({ ...ruleDraft, value: e.target.value })} /></label>
            </>}
            <label className="block text-xs">Fonte e justificativa da regra<Textarea required minLength={3} maxLength={1000} className={field} value={ruleDraft.note} onChange={e => setRuleDraft({ ...ruleDraft, note: e.target.value })} /></label><Button disabled={pending || ruleDraft.note.trim().length < 3}>Salvar alteração da regra</Button>
          </form></details>}
        </section>
        <section className={panel}><h2 className="font-semibold">Seções, associações e reanálise</h2><p className="text-xs text-slate-400">Confira inclusive seções não classificadas como conteúdo. Incluir ou excluir uma seção reprocessa apenas o escopo afetado, preservando evidências, correções e histórico.</p>
          <label className="block text-xs">Seção do documento<select className={field} value={section} onChange={e => setSection(e.target.value)}><option value="">Selecione uma seção</option>{sections.map(s => <option key={s.key} value={s.key}>{s.title?.value || `${s.kind} · ${s.block_id}`}</option>)}</select></label>
          <div className="flex flex-wrap gap-2"><Button size="sm" variant="ghost" disabled={!sectionPage} onClick={() => setSectionPage(n => n - 1)}>Seções anteriores</Button><Button size="sm" variant="ghost" disabled={(sectionPage + 1) * 20 >= sectionRows.length} onClick={() => setSectionPage(n => n + 1)}>Próximas seções</Button></div>
          {selectedSection && <><Sources fact={selectedSection.title} onSource={setSource} /><p className="text-xs">Associação atual: {scope.binding_corrections?.[section]?.value || scope.bindings?.[section]?.decision || 'A conferir'}.</p>
            {selectedSection.source_page && <Button size="sm" variant="ghost" onClick={() => setSource({ page: selectedSection.source_page, block_id: selectedSection.block_id })}>Ler início da seção na página {selectedSection.source_page}</Button>}
            <label className="block text-xs">Decisão de associação<select className={field} value={decision} onChange={e => setDecision(e.target.value)}><option value="include">Exigida neste cargo</option><option value="exclude">Não se aplica a este cargo</option><option value="ambiguous">Ainda ambígua</option></select></label>
            <label className="block text-xs">Motivo da decisão ou reanálise<Textarea minLength={3} maxLength={1000} className={field} value={sectionNote} onChange={e => setSectionNote(e.target.value)} /></label>
            <div className="flex flex-wrap gap-2"><Button disabled={!editable || pending || sectionNote.trim().length < 3} onClick={() => command('binding', { section_key: section, decision, note: sectionNote })}>Corrigir associação</Button>
              <Button variant="outline" disabled={!editingSelectedRole || pending || sectionNote.trim().length < 3 || state.inventory.status !== 'awaiting_review'} onClick={() => command('reanalyze', { section_keys: [section], note: sectionNote })}>Reanalisar esta seção</Button></div></>}
        </section>
        <section className={panel}><h2 className="font-semibold">Pendências de conferência</h2><p className="text-xs text-slate-400">Uma comparação automática sem apontamentos não confirma a análise. Resolva os problemas reais e registre como conferiu cada pendência.</p>
          {!!scope.unapplied_corrections?.length && <div className="rounded-xl border border-amber-500/40 p-3 space-y-2"><p className="text-sm text-amber-200">Há alterações humanas preservadas que não foram associadas ao novo resultado. Confira o histórico e transfira ou justifique cada decisão antes de confirmar.</p>
            {scope.unapplied_corrections.map(path => <p key={path} className="text-xs text-amber-100 [overflow-wrap:anywhere]">Correção preservada: {scope.corrections?.[path]?.value || 'Alteração estrutural registrada'} · {scope.corrections?.[path]?.note || 'Consulte os dados da revisão anterior.'}</p>)}</div>}
          {[['inventory', state.inventory, data.review.inventory_issues], ['scope', scope, data.review.program_issues]].map(([target, value, issues]) => <div key={target} className="space-y-3">
            {Object.entries(value.findings || {}).map(([identity, finding]) => <div key={identity} className="space-y-2"><p className="text-sm [overflow-wrap:anywhere]">{finding.description}</p><Sources fact={finding} onSource={setSource} />{value.finding_resolutions?.[identity] ? <p className="text-xs text-emerald-300">Conferido: {value.finding_resolutions[identity].note}</p> : editable && <ReviewAction {...{ command, pending, identity, target }} action="finding" />}</div>)}
            {(issues || []).map(issue => <div key={issue.id}><p className="text-sm [overflow-wrap:anywhere]">{issue.message}</p>{value.issue_resolutions?.[issue.id] ? <p className="text-xs text-emerald-300">Conferido: {value.issue_resolutions[issue.id].note}</p> : editable && <ReviewAction {...{ command, pending, target }} identity={issue.id} action="issue" />}</div>)}
          </div>)}
          {editable && <form className="space-y-3" onSubmit={async e => { e.preventDefault();if (await command('confirm', { note, acknowledge_document_limits: true })) { setNote('');setAcknowledged(false); } }}>
            <label className="block text-sm">Registro da conferência final<Textarea required minLength={3} maxLength={1000} className={field} value={note} onChange={e => setNote(e.target.value)} /></label>
            <label className="flex items-start gap-3 text-xs text-slate-300"><input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} className="mt-1" /><span>Conferi o cargo, as associações, as fontes e o conteúdo no edital. Entendo as limitações da extração e que dados ausentes permanecem desconhecidos.</span></label>
            <Button disabled={pending || unresolved || !acknowledged || note.trim().length < 3}>Confirmar cargo e conteúdo conferidos</Button>
          </form>}
          {scope.status === 'completed' && <Button variant="outline" disabled={pending} onClick={() => window.confirm('Reabrir a revisão? O programa importado e a confirmação anterior permanecem no histórico; será necessária nova confirmação.') && command('reopen', { note: 'Reabertura explícita da revisão pelo proprietário.' })}>Reabrir revisão do cargo</Button>}
        </section>
      </>}
      <details className={panel} open={!!scope}><summary className="cursor-pointer text-sm font-semibold text-zinc-200">Criar programa no meu planejamento</summary><p className="text-sm text-slate-400">O conteúdo confirmado entra em Meus estudos. Depois, use o planejamento existente para propor horários com sua disponibilidade real. Compromissos fixos não são movidos.</p>
        <PriorPrograms {...{ api, analysisId, onImported }} />
        <div className="grid sm:grid-cols-2 gap-4"><label className="text-xs">Área de estudos<select aria-label="Área de estudos" className={field} value={areaId} onChange={e => setAreaId(e.target.value)}><option value="">Selecione</option>{areas.map(a => <option key={a.area_id} value={a.area_id}>{a.name}</option>)}</select></label>
          <label className="text-xs">Meta pessoal de estudo (opcional)<Input type="date" className={field} value={form.target_date} onChange={e => onFormChange({ ...form, target_date: e.target.value })} /></label>
          <label className="text-xs">Horas disponíveis por dia<Input type="number" min="0.25" max="12" step="0.25" className={field} value={form.hours_per_day} onChange={e => onFormChange({ ...form, hours_per_day: Number(e.target.value) })} /></label>
          <label className="text-xs">Dias disponíveis por semana<Input type="number" min="1" max="7" step="1" className={field} value={form.days_per_week} onChange={e => onFormChange({ ...form, days_per_week: Number(e.target.value) })} /></label></div>
        <label className="flex gap-3 items-start text-xs text-slate-400"><input className="mt-1" type="checkbox" checked={newVersion} onChange={e => setNewVersion(e.target.checked)} /><span>Conferi os programas já criados deste PDF e autorizo criar outro programa separado, preservando os anteriores e sem novo XP. O mesmo conteúdo não será duplicado.</span></label>
        <Button disabled={pending || !available || !areaId} onClick={async () => { const result = await command('import', { role_id: state.selected_role_id, confirmed_digest: scope.confirmed_digest, area_id: areaId, target_date: form.target_date || null, hours_per_day: form.hours_per_day, days_per_week: form.days_per_week, create_new_version: newVersion });if (result) onImported?.(result); }}>Criar programa com conteúdo confirmado</Button>
        {!available && <p className="text-xs text-amber-200">Abra o cargo desejado, conclua os lotes e confirme a revisão antes de criar o programa.</p>}
      </details>
      <details id="edital-history" className={panel}><summary className="cursor-pointer text-sm">Diagnóstico seguro e histórico</summary><p className="text-xs text-slate-400">O último modelo observado registra uma tentativa. Só o último modelo concluído indica um lote validado; nenhum teste ativo de provedor é feito aqui.</p>
        {(data.diagnostics || []).map(item => <div key={item.unit_id} className="text-xs space-y-1 border-t border-slate-800 pt-2 [overflow-wrap:anywhere]"><p>{item.kind} · {item.status} · {item.provider_calls} chamadas reservadas</p>
          <p>Última tentativa: {item.last_observed_model ? `${item.last_observed_model.provider} / ${item.last_observed_model.model}` : 'Nenhuma chamada registrada'}</p>
          {item.failure && <p>HTTP: {item.failure.http_status ?? 'sem resposta HTTP registrada'} · motivo: {({ schema_keyword: 'propriedade de schema não aceita', schema_reference: 'referência de schema incompatível', schema_complexity: 'complexidade do schema', schema_feature: 'recurso de schema incompatível', schema_rejected: 'schema recusado pelo provedor', model_capability: 'modelo sem suporte à solicitação', request_rejected: 'formato da solicitação recusado', cooldown: 'intervalo de recuperação do provedor', no_compatible_route: 'nenhum modelo compatível disponível', payload_rejected: 'solicitação incompatível já identificada', pilot_limit: 'limite do piloto atingido' })[item.failure.incompatibility || item.failure.reason] || 'consulte o diagnóstico do lote'}{item.failure.provider_attempted === false ? ' · nenhuma chamada de rede nesta execução' : ''}</p>}
          {item.failure?.provider_rejection && <EditalProviderDiagnostic key={item.reference} item={item} />}
          <p>Último lote validado: {item.last_completed_model ? `${item.last_completed_model.provider} / ${item.last_completed_model.model}` : 'Não disponível'}</p>
          {item.error_kind && <p className="text-amber-200">{item.error_message || item.error_kind} · referência {item.reference}</p>}</div>)}
        <Button variant="outline" onClick={() => loadHistory()}>Consultar histórico de revisões</Button>{historyError && <p role="alert" className="text-amber-200 text-sm">{historyError}</p>}
        {history?.rows.map(item => <AuditEntry key={item.id} {...{ item, api, analysisId }} />)}
        {history?.hasMore && <Button variant="ghost" onClick={() => loadHistory(history.rows.length)}>Revisões anteriores</Button>}
        <Button variant="ghost" onClick={() => openSirius({ surface: 'edital', analysis_id: analysisId, draft: 'Ajude a conferir as fontes deste edital. Não considere propostas não confirmadas como regras oficiais.' })}>Perguntar ao Sirius sobre as fontes</Button>
      </details>
    </>}
    <SourcePage {...{ api, analysisId, source }} onClose={() => setSource(null)} />
  </div></main>;
}
