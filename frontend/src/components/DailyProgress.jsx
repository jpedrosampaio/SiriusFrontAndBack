export default function DailyProgress({ summary, raw = {} }) {
  const total = ['tasks_done', 'habits_done', 'tasks_pending', 'habits_pending'].reduce((n, key) => n + (raw[key] || 0), 0);
  return <div className="ml-auto text-center text-xs shrink-0" aria-label="Progresso do dia">
    <p className="text-slate-400">Progresso</p>
    <strong className={total ? 'text-sky-300 text-lg' : 'text-slate-400 text-lg'}>{total ? `${summary.score}%` : '—'}</strong>
    <p className="text-slate-400">{total ? 'do dia' : 'Sem itens planejados'}</p>
  </div>;
}
