const positiveInteger = value => Number.isInteger(Number(value)) && Number(value) > 0 ? Number(value) : null;

export function getWorkoutCalendar(plan, requestedIndex = 0) {
  const days = Array.isArray(plan.days) ? plan.days : [];
  const frequency = positiveInteger(plan.training_days_per_week) || 5;
  const weeks = {};
  days.forEach((day, index) => {
    const namedWeek = String(day.day_name || '').match(/sem(?:ana)?[_\s]*(\d+)/i)
      || String(day.day_label || '').match(/semana\s*(\d+)/i);
    const week = positiveInteger(day.week) || positiveInteger(namedWeek?.[1]) || Math.floor(index / frequency) + 1;
    (weeks[week] ||= []).push({ ...day, _globalIdx: index });
  });
  const selectedDayIndex = Number.isInteger(requestedIndex) && requestedIndex >= 0 && requestedIndex < days.length ? requestedIndex : 0;
  const weekNumbers = Object.keys(weeks).map(Number).sort((a, b) => a - b);
  const selectedWeek = weekNumbers.find(week => weeks[week].some(day => day._globalIdx === selectedDayIndex)) || 1;
  return { weeks, weekNumbers, selectedWeek, selectedDayIndex, currentWeekDays: weeks[selectedWeek] || [] };
}
