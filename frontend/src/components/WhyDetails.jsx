export default function WhyDetails({ why }) {
  if (!why) return null;
  const groups = [['Evidências', why.evidence], ['Restrições', why.constraints], ['Limites', why.limitations]];
  return <details className="text-sm text-slate-300 mt-2"><summary className="cursor-pointer min-h-11 inline-flex items-center text-sky-300">Por quê?</summary><div className="rounded-lg border border-white/10 p-3 space-y-3">
    {groups.map(([label, values]) => values?.length ? <div key={label}><p className="font-medium">{label}</p><ul className="list-disc pl-5">{values.map((value, i) => <li className="break-words" key={i}>{typeof value === 'string' ? value : JSON.stringify(value)}</li>)}</ul></div> : null)}
    <p className="text-xs text-slate-400 break-words">Fonte: {{'global-planner/1':'Planejador Global','finance-intelligence':'Finance Intelligence','flashcards':'Flashcards','questions-intelligence':'Questions Intelligence','edital-intelligence':'Radar de editais','ai_action_audit':'Histórico do Sirius Agent'}[why.source]||why.source}</p>
  </div></details>;
}
