export function summarizeSets(exercise) {
  const sets = (exercise?.sets_data || []).filter(s => Number.isFinite(Number(s.weight)) && Number(s.weight) >= 0 && Number.isFinite(Number(s.reps)) && Number(s.reps) > 0);
  if (!sets.length) return null;
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
