export function summarizeSets(exercise) {
  const sets = (exercise?.sets_data || []).filter(s => s.completed === true);
  const known = value => value != null && typeof value !== 'boolean' && String(value).trim() !== '' && Number.isFinite(Number(value));
  // An empty load is unknown, not zero; do not compare a partial subtotal as complete volume.
  if (!sets.length || !sets.every(s => known(s.weight) && Number(s.weight) >= 0 && known(s.reps) && Number(s.reps) > 0)) return null;
  const effort = sets.filter(s => Number(s.rpe) >= 1 && Number(s.rpe) <= 10);
  return { sets: sets.length, reps: sets.reduce((n, s) => n + Number(s.reps), 0),
    volume: sets.reduce((n, s) => n + Number(s.weight) * Number(s.reps), 0),
    rpe: effort.length ? effort.reduce((n, s) => n + Number(s.rpe), 0) / effort.length : null };
}

export function compareExercise(current, previous) {
  const a = summarizeSets(current), b = summarizeSets(previous);
  return a && b ? { current: a, previous: b, volumeDelta: a.volume - b.volume, repsDelta: a.reps - b.reps,
    rpeDelta: a.rpe !== null && b.rpe !== null ? a.rpe - b.rpe : null } : null;
}
