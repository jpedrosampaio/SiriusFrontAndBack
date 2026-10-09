import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { createActivityRequests } from '@/lib/activity-requests';
import { getApiErrorMessage } from '@/lib/api-errors';
import { openSirius } from '@/lib/sirius-context';

const API = `${process.env.REACT_APP_BACKEND_URL}/api/nutrition/intelligence`;
const labels = { calories: 'Energia', protein: 'Proteína', carbs: 'Carboidratos', fat: 'Gordura' };
const inputClass = 'w-full min-w-0 rounded-lg border border-white/15 bg-[#121212] p-2 text-white';
const show = value => value == null ? 'Não disponível' : Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 3 });
const names = text => text.split(',').map(s => s.trim()).filter(Boolean);

export default function NutritionIntelligence({ userId, date, onRecorded }) {
  const [state, setState] = useState(null), [error, setError] = useState(''), [reload, setReload] = useState(0);
  const [result, setResult] = useState(null), [loading, setLoading] = useState(false), [busy, setBusy] = useState(false);
  const [portions, setPortions] = useState('1'), [days, setDays] = useState('1'), [budgetOnly, setBudgetOnly] = useState(false), [availableOnly, setAvailableOnly] = useState(false);
  const [prefs, setPrefs] = useState(null), [message, setMessage] = useState('');
  const [availableText,setAvailableText]=useState(''),[excludedText,setExcludedText]=useState('');
  const [recipeType,setRecipeType]=useState('lunch'),[financeBudgets,setFinanceBudgets]=useState([]),[financeBudgetId,setFinanceBudgetId]=useState('');
  const requests = useRef(createActivityRequests()), controller = useRef(null);
  useEffect(() => {
    controller.current?.abort(); setLoading(false); setResult(null);
    return () => controller.current?.abort();
  }, [userId, date]);
  useEffect(() => {
    const abort = new AbortController(); setState(null); setError(''); setResult(null); setMessage('');
    if (!userId) return () => abort.abort();
    axios.get(`${API}/state`, { params: { date }, signal: abort.signal }).then(({ data }) => {
      if (!data?.consumed || !data?.preferences) throw new Error('Resposta incompleta.');
      setState(data); setPrefs(data.preferences);setAvailableText((data.preferences.available_foods || []).join(', '));setExcludedText(data.preferences.excluded_foods.join(', '));
    }).catch(e => { if (!abort.signal.aborted) setError(getApiErrorMessage(e, 'Não foi possível analisar os registros.')); });
    return () => abort.abort();
  }, [userId, date, reload]);
  useEffect(() => {
    const refresh = () => setReload(n => n + 1);
    window.addEventListener('sirius-data-changed', refresh);
    return () => { window.removeEventListener('sirius-data-changed', refresh); controller.current?.abort(); };
  }, []);
  const preview = async () => {
    controller.current?.abort(); const abort = new AbortController(); controller.current = abort;
    setLoading(true); setError(''); setResult(null);
    try {
      const { data } = await axios.post(`${API}/alternatives`, { date, days: Number(days), portions, within_budget: budgetOnly, available_only: availableOnly,finance_budget_id:financeBudgetId || null }, { signal: abort.signal });
      if (!Array.isArray(data?.candidates) || !Array.isArray(data?.organization)) throw new Error('Resposta incompleta.');
      if (!abort.signal.aborted) setResult(data);
    } catch (e) { if (!abort.signal.aborted) setError(getApiErrorMessage(e, 'Não foi possível comparar as opções.')); }
    finally { if (!abort.signal.aborted) setLoading(false); }
  };
  const write = async (resource, body, operation) => {
    const key = requests.current.begin(resource, JSON.stringify(body)); if (!key) return;
    setBusy(true); setError(''); let succeeded = false;
    try { await operation(key); succeeded = true; setMessage('Salvo. Histórico anterior preservado.'); setReload(n => n + 1); }
    catch (e) { setError(getApiErrorMessage(e, 'Falha ao salvar; tente novamente com os mesmos dados.')); }
    finally { requests.current.finish(resource, succeeded); setBusy(false); }
  };
  const savePreferences = next => write('preferences', next, key => axios.put(`${API}/preferences`, next, { headers: { 'Idempotency-Key': key } }));
  const repeat = candidate => {
    if (!window.confirm(`Registrar ${candidate.name} em ${date}, com fator de porção ${candidate.portions}?`)) return;
    const body = { date, portions: candidate.portions,...(candidate.template_kind==='recipe'?{meal_type:recipeType}:{}) };
    return write('record', { ...body, id: candidate.template_id }, async key => {
      await axios.post(`${API}/templates/${candidate.template_kind || 'meal'}/${candidate.template_id}/record`, body, { headers: { 'Idempotency-Key': key } }); onRecorded?.();
    });
  };
  if (!state) return <section aria-label="Inteligência nutricional" className="rounded-xl border border-white/10 p-4 space-y-3">
    {error ? <p role="alert">{error}</p> : <p>Consultando registros nutricionais…</p>}
    <Button onClick={() => setReload(n => n + 1)}>Atualizar análise</Button>
  </section>;
  return <section aria-label="Inteligência nutricional" className="space-y-5 min-w-0">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">Seu dia alimentar</h2><p className="text-sm text-slate-400">{date} · {state.timezone} · Dados registrados e estimativas separados</p></div>
      <Button variant="outline" onClick={() => setReload(n => n + 1)}>Atualizar análise</Button></header>
    {error && <p role="alert" className="text-amber-300">{error}</p>}{message && <p role="status">{message}</p>}
    {!state.goals?.configured && <p className="rounded-lg border border-amber-400/30 p-3 text-amber-200">Metas não confirmadas. Configure ou confirme suas metas na Visão Geral. Nenhuma necessidade foi presumida.</p>}
    {state.truncated && <p className="text-amber-200">Cobertura parcial: confira os limites da análise.</p>}
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">{Object.entries(labels).map(([key, label]) => {
      const value = state.consumed[key]; return <article key={key} className="rounded-xl border border-white/10 bg-[#0A0A0A] p-4 space-y-2">
        <h3 className="font-semibold">{label}</h3><p className="text-xl">{show(value.total)} {value.unit}</p>
        <p className="text-sm text-slate-400">Registrado: {show(value.registered)} · Estimado: {show(value.estimated)}</p>
        {value.unknown_items > 0 && <p className="text-xs text-amber-200">{value.unknown_items} item(ns) com dados desconhecidos; subtotal conhecido {show(value.known_total)} {value.unit}. Histórico sem origem: {show(value.legacy_unverified)}.</p>}
        <p className="text-sm">Para a meta confirmada: {show(state.remaining[key])} {value.unit}</p>
      </article>;
    })}</div>
    <div className="rounded-xl border border-white/10 p-4 space-y-2"><h3 className="font-semibold">Registros e rotina</h3>
      <p>{state.meals.length} refeição(ões) na data · {state.water_ml} ml de água registrada · {state.consistency.recorded_days}/{state.consistency.days} dias com registros</p>
      <p className="text-xs text-slate-400">Dias sem registro não comprovam ausência de alimentação.</p>
      {state.meals.map(m => <p className="text-sm break-words" key={m.meal_id}>{m.name} · {m.foods.length} alimento(s)</p>)}
      {state.planned.filter(p => p.status !== 'recorded').map(p => <p className="text-sm break-words" key={p.planned_meal_id}>Planejada: {p.name} · {p.date_confirmed ? p.time_label || 'Sem horário' : 'Data não definida'} · composição estimada ou não verificada</p>)}
      {state.training_context.map((t, i) => <p className="text-sm" key={t.log_id || t.session_id || i}>Treino registrado: {t.name} {t.status === 'active' ? '· em andamento' : `· ${t.date}`}</p>)}
      {state.routine_context?.map(e => <p className="text-sm break-words" key={e.event_id}>Compromisso fixo: {e.title} · {new Date(e.start_at).toLocaleString('pt-BR', { timeZone: state.timezone })}</p>)}
    </div>
    <details className="rounded-xl border border-white/10 p-4"><summary className="cursor-pointer font-semibold">Preferências, disponibilidade e orçamento</summary>
      <div className="space-y-3 mt-4">
        <label className="block">Alimentos disponíveis, separados por vírgulas<input className={inputClass} value={availableText} onChange={e => setAvailableText(e.target.value)} /></label>
        <label className="block">Alimentos a excluir<input className={inputClass} value={excludedText} onChange={e => setExcludedText(e.target.value)} /></label>
        <div className="grid sm:grid-cols-2 gap-3"><label>Limite opcional (R$)<input type="number" min="0.01" step="0.01" className={inputClass} value={prefs.budget ?? ''} onChange={e => setPrefs({ ...prefs, budget: e.target.value || null })} /></label>
          <label>Período do limite<select className={inputClass} value={prefs.budget_period} onChange={e => setPrefs({ ...prefs, budget_period: e.target.value })}><option value="daily">Diário</option><option value="weekly">Semanal</option></select></label></div>
        <p className="text-xs text-slate-400">Preços por unidade declarada (g, ml ou porção). Não são despesas e não geram compras. Use unidades iguais às do registro.</p>
        {prefs.prices.map((price, index) => <div key={index} className="grid sm:grid-cols-2 gap-2 border border-white/10 rounded-lg p-3">
          {[['food', 'Alimento'], ['unit', 'Unidade'], ['amount', 'Preço (R$)']].map(([field, label]) => <label key={field}>{label}<input className={inputClass} type={field === 'amount' ? 'number' : 'text'} min="0" step="0.01" value={price[field]} onChange={e => setPrefs({ ...prefs, prices: prefs.prices.map((p, i) => i === index ? { ...p, [field]: e.target.value } : p) })} /></label>)}
          <label>Origem do preço<select className={inputClass} value={price.source} onChange={e => setPrefs({ ...prefs, prices: prefs.prices.map((p, i) => i === index ? { ...p, source: e.target.value } : p) })}><option value="known">Conhecido</option><option value="estimated">Estimado</option></select></label>
          <Button variant="outline" onClick={() => setPrefs({ ...prefs, prices: prefs.prices.filter((_, i) => i !== index) })}>Remover preço</Button>
        </div>)}
        <Button variant="outline" onClick={() => setPrefs({ ...prefs, prices: [...prefs.prices, { food: '', unit: 'porcao', amount: '', source: 'known', currency: 'BRL' }] })}>Adicionar preço</Button>
        <Button disabled={busy} onClick={() => savePreferences({...prefs,available_foods:availableText.trim()?names(availableText):null,excluded_foods:names(excludedText)})}>Salvar preferências</Button>
      </div>
    </details>
    <div className="rounded-xl border border-white/10 p-4 space-y-3"><h3 className="font-semibold">Reaproveitar e comparar refeições</h3>
      <p className="text-sm text-slate-400">Sugestões do seu histórico. Ajustes de porção são cenários escolhidos por você; nada é registrado antes da confirmação.</p>
      <div className="grid sm:grid-cols-2 gap-3"><label>Fator de porção<input aria-label="Fator de porção" className={inputClass} type="number" min="0.25" max="4" step="0.25" value={portions} onChange={e => setPortions(e.target.value)} /></label>
        <label>Organização<select aria-label="Período da organização" className={inputClass} value={days} onChange={e => setDays(e.target.value)}><option value="1">Dia selecionado</option><option value="7">Sete dias</option></select></label></div>
      <label className="block"><input type="checkbox" checked={budgetOnly} onChange={e => setBudgetOnly(e.target.checked)} /> Somente opções dentro do orçamento</label>
      <label className="block"><input type="checkbox" checked={availableOnly} onChange={e => setAvailableOnly(e.target.checked)} /> Somente alimentos declarados disponíveis</label>
      <Button variant="outline" onClick={async()=>{try{const {data}=await axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/finance/intelligence/state`);setFinanceBudgets(data.budgets || []);}catch(e){setError(getApiErrorMessage(e,'Não foi possível consultar orçamentos financeiros.'));}}}>Consultar orçamentos financeiros</Button>
      <label className="block">Limite financeiro opcional<select className={inputClass} value={financeBudgetId} onChange={e=>setFinanceBudgetId(e.target.value)}><option value="">Usar limite alimentar configurado, se existir</option>{financeBudgets.map(b=><option key={b.budget_id} value={b.budget_id}>{b.category} · limite {show(b.effective_limit)} · gasto {show(b.spent)}</option>)}</select></label>
      <label className="block">Tipo escolhido para registrar receitas<select className={inputClass} value={recipeType} onChange={e=>setRecipeType(e.target.value)}><option value="breakfast">Café da manhã</option><option value="lunch">Almoço</option><option value="dinner">Jantar</option><option value="snack">Lanche</option></select></label>
      <Button onClick={preview} disabled={loading}>{loading ? 'Comparando…' : 'Comparar alternativas'}</Button>
      {result && <div className="space-y-3">
        {!result.candidates.length && <p>Nenhuma alternativa comprovável com os filtros atuais. Revise dados, preços e disponibilidade.</p>}
        {result.candidates.map(c => <article className="rounded-lg bg-white/5 p-3 space-y-2" key={c.template_id}><h4 className="font-semibold break-words">{c.name}</h4>
          <p className="text-xs text-amber-200">Composição: {c.composition_source === 'estimated' ? 'estimada, sujeita a revisão' : 'dados registrados ou origem antiga não verificada'}</p>
          <p className="text-sm">{Object.entries(labels).map(([k,label])=>`${label}: ${show(c.macros[k].total)} ${c.macros[k].unit}`).join(' · ')} · Custo: {show(c.cost)} {c.currency} ({c.cost_source === 'known' ? 'conhecido' : c.cost_source === 'estimated' ? 'estimado' : 'incompleto'})</p>
          <p className="text-xs text-slate-400 break-words">{c.reason}</p><div className="flex flex-wrap gap-2">{(!c.template_kind || c.template_kind==='meal') && <Button disabled={busy} variant="outline" onClick={() => savePreferences({ ...prefs, favorite_meals: c.favorite ? prefs.favorite_meals.filter(id => id !== c.template_id) : [...new Set([...prefs.favorite_meals, c.template_id])] })}>{c.favorite ? 'Remover favorita' : 'Favoritar'}</Button>}
            <Button disabled={busy} onClick={() => repeat(c)}>Registrar com confirmação</Button></div></article>)}
        {result.organization.length > 0 && <details><summary className="cursor-pointer">Organização proposta, sem agendamento</summary><div className="mt-2 space-y-2">{result.organization.map((o, i) => <p className="text-sm break-words" key={i}>{o.date} · {o.name} · fator {o.portions} · custo {show(o.cost)} R$</p>)}</div></details>}
        <ul className="text-xs text-slate-400 space-y-1">{result.limitations.map(l => <li key={l}>{l}</li>)}</ul>
      </div>}
    </div>
    <Button variant="outline" onClick={() => openSirius({ surface: 'nutrition', draft: 'O que ainda falta consumir hoje conforme minhas metas confirmadas e meus registros?' })}>Perguntar ao Sirius</Button>
    <details><summary className="cursor-pointer text-sm text-slate-400">Critérios e limites</summary><ul className="text-xs text-slate-400 space-y-1 mt-2">{state.limitations.map(l => <li key={l}>{l}</li>)}</ul></details>
  </section>;
}
