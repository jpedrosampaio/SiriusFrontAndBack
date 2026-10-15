export function editableExercises(plan, dayIndex) {
  return plan?.days?.length ? plan.days[dayIndex]?.exercises || [] : plan?.exercises || [];
}

export function editPlanExercises(plan, dayIndex, change) {
  if (!plan.days?.length) return { ...plan, exercises: change(plan.exercises || []) };
  const days = plan.days.map((day, index) => index === dayIndex ? { ...day, exercises: change(day.exercises || []) } : day);
  return { ...plan, days, exercises: days.flatMap(day => day.exercises || []) };
}

export function planEditPayload(plan) {
  return { name: plan.name, description: plan.description, plan_duration: plan.plan_duration,
    ...(plan.days?.length ? { days: plan.days } : { exercises: plan.exercises || [] }) };
}
