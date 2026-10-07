// Presentation derived only from recorded session data, never estimated physiology.
export function workoutSummary(session) {
  const exercises = session?.exercises || [];
  const sets = exercises.flatMap(ex => ex.sets_data || []).filter(s => s.completed !== false);
  let volume = 0;
  const completeVolume = sets.length > 0 && sets.every(s => {
    if (s.weight === '' || s.weight == null || s.reps === '' || s.reps == null) return false;
    const weight = Number(s.weight), reps = Number(s.reps);
    if (!Number.isFinite(weight) || weight < 0 || !Number.isFinite(reps) || reps < 0) return false;
    volume += weight * reps;
    return true;
  });
  return { exercises: exercises.filter(ex => ex.completed).length, total: exercises.length, sets: sets.length, volume: completeVolume ? volume : null };
}

export function setDefaults(exercise) {
  const last = exercise?.sets_data?.at(-1);
  const weight = last?.weight ?? exercise?.weight ?? '';
  return {
    // A prescription such as "moderado" is not a numeric load.
    weight: weight !== '' && Number.isFinite(Number(weight)) ? String(weight) : '',
    reps: String(last?.reps ?? exercise?.reps ?? 12).match(/\d+/)?.[0] || '12',
    rpe: last?.rpe == null ? '' : String(last.rpe),
  };
}

export function validateSet(values) {
  const reps = Number(values.reps);
  const weight = values.weight.trim().replace(',', '.');
  const rpe = values.rpe.trim().replace(',', '.');
  if (!Number.isInteger(reps) || reps < 1 || reps > 999) throw new Error('Informe de 1 a 999 repetições.');
  if (weight && (!Number.isFinite(Number(weight)) || Number(weight) < 0 || Number(weight) > 9999999 || !/^\d+(\.\d{1,3})?$/.test(weight))) throw new Error('Informe uma carga válida, com até 3 casas decimais, ou deixe em branco.');
  if (rpe && (!Number.isFinite(Number(rpe)) || Number(rpe) < 1 || Number(rpe) > 10)) throw new Error('O RPE deve estar entre 1 e 10, ou ficar em branco.');
  return { reps, weight, rpe, completed: true };
}

export function sessionTime(seconds) {
  const value = Math.max(0, Math.floor(seconds || 0));
  const m = Math.floor(value / 60), s = String(value % 60).padStart(2, '0');
  return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}:${s}` : `${String(m).padStart(2, '0')}:${s}`;
}
