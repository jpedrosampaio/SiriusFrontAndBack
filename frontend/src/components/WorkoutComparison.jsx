import { compareExercise } from '@/lib/workout-comparison';

export default function WorkoutComparison({ current, previous }) {
  const result = compareExercise(current, previous);
  if (!result) return <p className="text-xs text-slate-400 mt-2">Registre carga e repetições das séries para comparar com a sessão anterior.</p>;
  const signed = n => `${n > 0 ? '+' : ''}${Number(n.toFixed(1))}`;
  return <div className="mt-3 rounded-xl border border-blue-400/20 p-3 space-y-2">
    <p className="text-sm font-medium text-blue-200">Comparação com {previous.date}</p>
    <dl className="grid grid-cols-2 gap-2 text-xs"><div><dt className="text-slate-400">Volume registrado</dt><dd>{result.current.volume.toFixed(1)} kg × rep · {signed(result.volumeDelta)}</dd></div><div><dt className="text-slate-400">Repetições</dt><dd>{result.current.reps} · {signed(result.repsDelta)}</dd></div><div><dt className="text-slate-400">RPE médio</dt><dd>{result.current.rpe?.toFixed(1) ?? 'Não registrado'}{result.rpeDelta !== null ? ` · ${signed(result.rpeDelta)}` : ''}</dd></div><div><dt className="text-slate-400">Séries comparadas</dt><dd>{result.current.sets} nesta sessão / {result.previous.sets} na anterior</dd></div></dl>
    <p className="text-xs text-slate-400">Comparação das séries já registradas; a sessão pode estar em andamento. Confira quantidade de séries e execução antes de ajustar a próxima carga.</p>
  </div>;
}
