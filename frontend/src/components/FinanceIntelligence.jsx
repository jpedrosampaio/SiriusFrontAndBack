import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { getApiErrorMessage } from '@/lib/api-errors';
import { formatBRL } from '@/lib/finance-money';
import { openSirius } from '@/lib/sirius-context';

const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/finance/intelligence`;
const field = 'min-h-11 w-full min-w-0 rounded-lg border border-white/15 bg-black/30 px-3 text-sm';
const decimal = v => v.trim().replace(',', '.');
const newDebt = rank => ({ id: crypto.randomUUID(), title: '', principal: '', monthly_rate_percent: '', minimum_payment: '', rank: String(rank) });
const statusLabel = { unknown_rates: 'Taxas incompletas: prazo e juros não calculados', minimums_exceed_envelope: 'Mínimos excedem o valor mensal', horizon_reached: 'Dívida restante ao fim do horizonte', paid_in_model: 'Quitação no modelo hipotético' };
const strategyLabel = { snowball: 'Bola de neve · menor saldo', avalanche: 'Avalanche · maior taxa', custom: 'Ordem personalizada' };
const factLabels = { spent: 'Gasto', limit: 'Limite', excess: 'Excedente', current: 'Período atual', previous: 'Período anterior', increase_percent: 'Aumento', current_start: 'Início atual', current_end: 'Fim atual', previous_start: 'Início anterior', previous_end: 'Fim anterior', count: 'Quantidade', total_in_horizon: 'Total no horizonte' };
const moneyFacts = new Set(['spent', 'limit', 'excess', 'current', 'previous', 'total_in_horizon']);

function ForecastCards({ forecast }) {
  const [expanded, setExpanded] = useState(false);
  if (!forecast) return null;
  return <div className="space-y-3"><div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">{(expanded ? forecast.months : forecast.months.slice(0, 3)).map((m, index) => <article className={`rounded-xl border border-white/10 bg-black/25 p-3 space-y-2 ${!expanded && index > 0 ? 'hidden sm:block' : ''}`} key={m.month}>
    <h4 className="font-medium">{m.month.slice(0, 7)}</h4><dl className="text-xs space-y-2">
      {[['Receita futura registrada', m.recorded_future_income], ['Despesa futura registrada', m.recorded_future_expense], ['Obrigações estimadas', m.estimated_expense], ['Receita hipotética', m.scenario_income], ['Despesa hipotética', m.scenario_expense], ['Variação prevista dos registros', m.net_change], ['Variação acumulada', m.cumulative_change]].map(([label, value]) => <div className="flex flex-wrap justify-between gap-x-2" key={label}><dt className="text-slate-400">{label}</dt><dd className="font-mono break-all">{formatBRL(value)}</dd></div>)}
      {m.scenario_balance !== null && <div><dt className="text-sky-300">Saldo do cenário com valor inicial declarado</dt><dd className="font-mono break-all">{formatBRL(m.scenario_balance)}</dd></div>}
    </dl></article>)}</div>{forecast.months.length > 1 && <Button className="min-h-11" variant="outline" onClick={() => setExpanded(!expanded)}>{expanded ? 'Recolher meses' : `Ver todos os ${forecast.months.length} meses`}</Button>}<details className="text-xs text-slate-400"><summary className="cursor-pointer min-h-11">Premissas do cálculo</summary>{forecast.assumptions.map(a => <p className="mb-2" key={a}>{a}</p>)}</details></div>;
}

export default function FinanceIntelligence({ userId }) {
  const [state, setState] = useState(null), [view, setView] = useState('flow'), [months, setMonths] = useState(6), [reload, setReload] = useState(0);
  const [error, setError] = useState(''), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [opening, setOpening] = useState(''), [income, setIncome] = useState(''), [expense, setExpense] = useState(''), [offset, setOffset] = useState(0);
  const [paymentId, setPaymentId] = useState(''), [paymentDate, setPaymentDate] = useState(''), [simulation, setSimulation] = useState(null);
  const [debts, setDebts] = useState(() => [newDebt(1)]), [monthlyPayment, setMonthlyPayment] = useState(''), [debtMonths, setDebtMonths] = useState(120), [comparison, setComparison] = useState(null);
  const generation = useRef(0), locked = useRef(false);
  useEffect(() => {
    let timer;
    const refresh = () => { clearTimeout(timer); timer = setTimeout(() => setReload(value => value + 1), 100); };
    window.addEventListener('sirius-data-changed', refresh);
    return () => { clearTimeout(timer); window.removeEventListener('sirius-data-changed', refresh); };
  }, [userId]);
  useEffect(() => {
    setDebts([newDebt(1)]); setOpening(''); setIncome(''); setExpense(''); setMonthlyPayment('');
  }, [userId]);
  useEffect(() => {
    const controller = new AbortController(), gen = ++generation.current;
    setState(null); setSimulation(null); setComparison(null); setPaymentId(''); setError(''); setLoading(true); locked.current = false; setBusy(false);
    axios.get(`${API}/state`, { params: { months }, signal: controller.signal, timeout: 20000 }).then(({ data }) => {
      if (!data || Array.isArray(data) || !['warnings', 'budgets', 'goals', 'debts', 'insights', 'upcoming_bills'].every(key => Array.isArray(data[key])) || (data.forecast && !Array.isArray(data.forecast.months))) throw new Error('A análise retornou dados incompletos. Atualize para tentar novamente.');
      if (generation.current === gen) { setState(data); setPaymentDate(data.as_of); }
    }).catch(e => { if (!controller.signal.aborted && generation.current === gen) setError(getApiErrorMessage(e, 'Não foi possível consultar os registros financeiros.')); })
      .finally(() => { if (generation.current === gen) setLoading(false); });
    return () => { controller.abort(); generation.current = gen + 1; };
  }, [userId, months, reload]);
  const run = async kind => {
    if (locked.current || !state) return;
    locked.current = true; setBusy(true); setError(''); const gen = generation.current;
    try {
      if (kind === 'simulate') {
        const body = { months, opening_balance: opening ? decimal(opening) : null, monthly_income: decimal(income) || '0.00', monthly_expense: decimal(expense) || '0.00', additions_start_offset: offset, fingerprint: state.fingerprint,
          prepayments: paymentId ? [{ source_id: paymentId, date: paymentDate }] : [] };
        const { data } = await axios.post(`${API}/simulate`, body, { timeout: 20000 });
        if (gen === generation.current) setSimulation(data);
      } else {
        const ranks = debts.map(d => Number(d.rank));
        if (!ranks.every(rank => Number.isInteger(rank) && rank >= 1 && rank <= 20) || new Set(ranks).size !== debts.length) throw new Error('Use posições inteiras de 1 a 20, sem repetir a ordem personalizada.');
        const body = { debts: debts.map(d => ({ id: d.id, title: d.title, principal: decimal(d.principal), monthly_rate_percent: d.monthly_rate_percent ? decimal(d.monthly_rate_percent) : null, minimum_payment: decimal(d.minimum_payment) || '0.00' })),
          monthly_payment: decimal(monthlyPayment), months: debtMonths, custom_order: [...debts].sort((a, b) => Number(a.rank) - Number(b.rank)).map(d => d.id) };
        const { data } = await axios.post(`${API}/compare-debts`, body, { timeout: 20000 });
        if (gen === generation.current) setComparison(data);
      }
    } catch (e) { if (gen === generation.current) setError(e.response ? getApiErrorMessage(e, 'Confira os valores e atualize os dados antes de simular.') : e.message); }
    finally { if (gen === generation.current) { locked.current = false; setBusy(false); } }
  };
  const editDebt = (id, key, value) => { setDebts(debts.map(d => d.id === id ? { ...d, [key]: value } : d)); setComparison(null); };
  return <section className="mb-8 rounded-2xl border border-emerald-400/20 bg-gradient-to-br from-emerald-950/25 to-[#0A0A0A] p-4 md:p-6 space-y-4 min-w-0" aria-label="Inteligência financeira">
    <div className="flex flex-wrap justify-between items-start gap-3"><div><h2 className="text-xl font-semibold">Inteligência financeira</h2><p className="text-sm text-slate-400">Fluxo, compromissos e cenários com fatos dos seus registros.</p></div><Button variant="outline" className="min-h-11" disabled={loading || busy} onClick={() => setReload(reload + 1)}>Atualizar análise</Button></div>
    {loading && <p role="status">Consultando registros…</p>}{error && <p role="alert" className="text-sm text-amber-300 break-words">{error}</p>}
    {!loading && !state && <Button className="min-h-11" onClick={() => setReload(reload + 1)}>Tentar novamente</Button>}
    {state && <><p className="text-xs text-slate-400">{state.as_of} · {state.timezone} · mês atual · {state.complete ? 'dados completos no horizonte' : 'detalhes parciais; projeção suspensa'}</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">{[['Receita registrada', state.income], ['Despesa registrada', state.expense], ['Saldo dos registros · não bancário', state.recorded_net]].map(([label, value]) => <div className="rounded-xl bg-black/30 p-3 min-w-0" key={label}><p className="text-xs text-slate-400">{label}</p><strong className="font-mono break-all">{formatBRL(value)}</strong></div>)}</div>
      {state.warnings.map(w => <p className="text-xs text-amber-200 break-words" key={w}>{w}</p>)}
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Análise financeira">{[['flow', 'Fluxo previsto'], ['scenario', 'Cenários'], ['debts', 'Dívidas']].map(([id, label]) => <button className={`min-h-11 rounded-lg px-3 text-sm border ${view === id ? 'border-emerald-400/50 bg-emerald-900/30' : 'border-white/10'}`} role="tab" aria-selected={view === id} key={id} onClick={() => setView(id)}>{label}</button>)}</div>
      <label className="block text-xs max-w-xs">Horizonte (meses)<select className={field} disabled={busy} value={months} onChange={e => { setMonths(Number(e.target.value)); setOffset(0); }}>{Array.from({ length: 12 }, (_, i) => <option key={i} value={i + 1}>{i + 1}</option>)}</select></label>
      {view === 'flow' && <div role="tabpanel" aria-label="Fluxo previsto" className="space-y-4"><p className="text-sm text-slate-300">Não repetimos renda passada. Valores de obrigações são estimativas; lançamentos futuros ficam separados. Saldo bancário: não informado.</p><ForecastCards forecast={state.forecast} />
        <details><summary className="min-h-11 cursor-pointer">Contas, parcelas e recorrências ({state.upcoming_bills.length})</summary>{state.upcoming_bills.slice(0, 50).map(o => <div className="border-b border-white/10 py-3 text-sm break-words" key={o.source_id}><p>{o.title} · {formatBRL(o.amount)}</p><p className="text-xs text-slate-400">{o.due_date ? `${o.due_date} · dia configurado do cartão` : `${o.month.slice(0, 7)} · dia de vencimento não cadastrado`}{o.recurring ? ' · recorrência registrada' : ''} · {o.reason}</p></div>)}{state.upcoming_bills.length > 50 && <p>Mostrando as primeiras 50; o cálculo considera todas as obrigações do snapshot.</p>}</details>
        <details><summary className="min-h-11 cursor-pointer">Orçamentos e fatos detectados</summary>{state.budgets.map(b => <p className="text-sm py-2 break-words" key={b.budget_id}>{b.category} · gasto {formatBRL(b.spent)} · limite {formatBRL(b.effective_limit)} · {b.basis}</p>)}{state.insights.slice(0, 20).map((i, index) => <article className="rounded-lg border border-white/10 p-3 my-2" key={index}><h4 className="text-sm">{i.title}</h4><p className="text-xs text-slate-400">{i.method}</p><dl className="text-xs mt-2">{Object.entries(i.facts).filter(([k]) => factLabels[k]).map(([k, v]) => <div key={k} className="flex flex-wrap gap-2"><dt>{factLabels[k]}</dt><dd className="break-all">{moneyFacts.has(k) ? formatBRL(v) : k === 'increase_percent' ? `${v}%` : String(v)}</dd></div>)}</dl></article>)}</details>
        {state.goals.length > 0 && <details><summary className="min-h-11 cursor-pointer">Metas pessoais do contexto</summary><p className="text-xs text-slate-400">Metas existentes, sem valor financeiro presumido.</p>{state.goals.slice(0, 20).map(g => <p className="text-sm py-2 break-words" key={g.goal_id}>{g.title} · {g.progress_percent}% registrado · {g.target_date}</p>)}<Link className="inline-flex min-h-11 items-center text-emerald-300 underline" to="/goals">Abrir metas</Link></details>}
        <Button variant="outline" className="min-h-11" onClick={() => openSirius({ draft: 'Explique meu estado financeiro, o fluxo previsto e os fatos detectados. Não invente renda futura ou saldo bancário.' })}>Entender com Sirius</Button>
      </div>}
      {view === 'scenario' && <div role="tabpanel" aria-label="Cenários financeiros" className="space-y-3"><p className="text-sm text-slate-300">Teste possibilidades sem alterar transações. Valores mensais são hipóteses; antecipações usam o valor integral, sem presumir desconto.</p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">{[['Saldo inicial do cenário', opening, setOpening], ['Receita mensal hipotética', income, setIncome], ['Despesa mensal hipotética', expense, setExpense]].map(([label, value, setter]) => <label className="text-xs" key={label}>{label}<input className={field} disabled={busy} type="number" step="0.01" value={value} onChange={e => { setter(e.target.value); setSimulation(null); }} /></label>)}</div>
        <label className="block text-xs">Acréscimos a partir de<select className={field} disabled={busy} value={offset} onChange={e => { setOffset(Number(e.target.value)); setSimulation(null); }}>{state.forecast?.months.map((m, i) => <option key={m.month} value={i}>{m.month.slice(0, 7)} · mês incluído integralmente</option>)}</select></label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3"><label className="text-xs">Obrigação a antecipar no cenário<select className={field} disabled={busy} value={paymentId} onChange={e => { setPaymentId(e.target.value); setSimulation(null); }}><option value="">Sem alteração de data</option>{state.upcoming_bills.map(o => <option key={o.source_id} value={o.source_id}>{o.title} · {formatBRL(o.amount)}</option>)}</select></label><label className="text-xs">Data de pagamento no cenário<input className={field} disabled={busy || !paymentId} type="date" min={state.as_of} max={state.forecast?.end} value={paymentDate} onChange={e => { setPaymentDate(e.target.value); setSimulation(null); }} /></label></div>
        <Button className="min-h-11" disabled={busy || !state.complete} onClick={() => run('simulate')}>{busy ? 'Calculando…' : 'Simular fluxo sem gravar'}</Button>
        {simulation && <div role="region" aria-label="Resultado do cenário financeiro" className="space-y-3"><p className="text-emerald-300 text-sm">Cenário calculado · nenhum registro alterado</p><details><summary className="min-h-11 cursor-pointer">Comparar com o fluxo original</summary><ForecastCards forecast={simulation.baseline} /></details><ForecastCards forecast={simulation.scenario} /></div>}
      </div>}
      {view === 'debts' && <div role="tabpanel" aria-label="Comparação de dívidas" className="space-y-3"><p className="text-sm text-slate-300">Declare saldos, taxas mensais e mínimos para comparar hipóteses. Sem todas as taxas, prazo e juros ficam indisponíveis. Confira os valores com o credor.</p>
        {state.debts.length > 0 && <Button className="min-h-11" variant="outline" disabled={busy || !state.complete} onClick={() => { setDebts(state.debts.slice(0, 20).map((d, i) => ({ ...newDebt(i + 1), title: d.title, principal: d.known_obligations }))); setComparison(null); }}>Usar compromissos registrados no horizonte como hipótese</Button>}
        {debts.map((d, index) => <fieldset className="rounded-xl border border-white/10 p-3 space-y-3 min-w-0" key={d.id}><legend className="text-sm">Dívida hipotética {index + 1}</legend><div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">{[['Nome', 'title', 'text'], ['Principal declarado', 'principal', 'number'], ['Taxa mensal (%) · vazio se desconhecida', 'monthly_rate_percent', 'number'], ['Mínimo hipotético · 0 se não modelado', 'minimum_payment', 'number'], ['Ordem personalizada', 'rank', 'number']].map(([label, key, type]) => <label className="text-xs" key={key}>{label}<input className={field} disabled={busy} type={type} step={key === 'rank' ? '1' : key === 'monthly_rate_percent' ? '0.0001' : '0.01'} value={d[key]} onChange={e => editDebt(d.id, key, e.target.value)} /></label>)}</div>{debts.length > 1 && <Button variant="outline" disabled={busy} className="min-h-11" onClick={() => { setDebts(debts.filter(row => row.id !== d.id)); setComparison(null); }}>Remover esta hipótese</Button>}</fieldset>)}
        <Button className="min-h-11" variant="outline" disabled={busy || debts.length >= 20} onClick={() => { setDebts([...debts, newDebt(Math.max(...debts.map(d => Number(d.rank) || 0)) + 1)]); setComparison(null); }}>Adicionar dívida hipotética</Button>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3"><label className="text-xs">Valor mensal disponível no modelo<input className={field} disabled={busy} type="number" step="0.01" value={monthlyPayment} onChange={e => { setMonthlyPayment(e.target.value); setComparison(null); }} /></label><label className="text-xs">Limite do modelo (meses)<input className={field} disabled={busy} type="number" min="1" max="360" value={debtMonths} onChange={e => { setDebtMonths(Number(e.target.value)); setComparison(null); }} /></label></div>
        <Button className="min-h-11" disabled={busy} onClick={() => run('debts')}>{busy ? 'Calculando…' : 'Comparar estratégias sem gravar'}</Button>
        {comparison && <div role="region" aria-label="Resultado das estratégias de dívida" className="grid grid-cols-1 md:grid-cols-3 gap-3">{comparison.results.map(r => <article className="rounded-xl border border-emerald-400/20 p-3 text-sm min-w-0" key={r.strategy}><h4 className="font-medium">{strategyLabel[r.strategy]}</h4><p className="text-xs text-amber-200 my-2">{statusLabel[r.status]}</p><p>Prazo: {r.payoff_months === null ? 'não calculado / não quitado' : `${r.payoff_months} meses`}</p><p className="break-all">Juros: {formatBRL(r.total_interest)}</p><p className="break-all">Restante: {formatBRL(r.remaining)}</p><p className="text-xs text-slate-400 break-words">Ordem: {r.order ? r.order.map(id => debts.find(d => d.id === id)?.title || id).join(' → ') : 'Taxas necessárias para ordenar'}</p><details><summary className="min-h-11 cursor-pointer">Fluxo mensal do modelo</summary>{r.timeline.slice(0, 24).map(m => <p className="text-xs break-all py-1" key={m.month_number}>Mês {m.month_number} · pagamento {formatBRL(m.payment)} · juros {formatBRL(m.interest)} · restante {formatBRL(m.remaining)}</p>)}{r.timeline.length > 24 && <p className="text-xs">Primeiros 24 meses exibidos; totais consideram todo o horizonte calculado.</p>}</details></article>)}</div>}
      </div>}
    </>}
  </section>;
}
