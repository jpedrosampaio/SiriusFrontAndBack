export const EQUIPMENT = [
  ['halteres', 'Halteres'], ['barra_anilhas', 'Barra e anilhas'], ['banco', 'Banco'],
  ['elasticos', 'Elásticos'], ['barra_fixa', 'Barra fixa'], ['paralelas', 'Paralelas'],
  ['argolas', 'Argolas'], ['kettlebell', 'Kettlebell'], ['maquinas', 'Máquinas'],
  ['smith', 'Smith'], ['polias', 'Polias/crossover'], ['esteira', 'Esteira'],
  ['bicicleta', 'Bicicleta ergométrica'], ['corda', 'Corda'], ['colchonete', 'Colchonete'],
  ['eliptico', 'Elíptico'], ['remo', 'Remo'], ['piscina', 'Piscina'],
];
export const MUSCLES = ['peito', 'costas', 'pernas', 'ombros', 'biceps', 'triceps', 'abdomen', 'gluteos', 'trapezio', 'antebraco', 'panturrilha'];
export const muscleLabel = value => ({ peito:'Peito',costas:'Costas',pernas:'Pernas',ombros:'Ombros',biceps:'Bíceps',triceps:'Tríceps',abdomen:'Abdômen',gluteos:'Glúteos',trapezio:'Trapézio',antebraco:'Antebraço',panturrilha:'Panturrilha' }[value] || value);
export const SPLITS = {
  AB: [['Superior', ['peito', 'costas', 'ombros', 'biceps', 'triceps']], ['Inferior', ['pernas', 'gluteos', 'abdomen', 'panturrilha']]],
  ABC: [['Peito, tríceps e ombros', ['peito', 'triceps', 'ombros']], ['Costas e bíceps', ['costas', 'biceps']], ['Pernas e abdômen', ['pernas', 'abdomen', 'gluteos']]],
  ABCD: [['Peito e tríceps', ['peito', 'triceps']], ['Costas e bíceps', ['costas', 'biceps']], ['Ombros e abdômen', ['ombros', 'abdomen', 'trapezio']], ['Pernas e glúteos', ['pernas', 'gluteos', 'panturrilha']]],
  ABCDE: [['Peito', ['peito']], ['Costas', ['costas', 'trapezio']], ['Ombros e trapézio', ['ombros', 'trapezio']], ['Bíceps e tríceps', ['biceps', 'triceps', 'antebraco']], ['Pernas e glúteos', ['pernas', 'gluteos', 'panturrilha', 'abdomen']]],
};
export function splitConfig(type) {
  return SPLITS[type].map(([name, muscle_groups], i) => ({ label: type[i], name, muscle_groups: [...muscle_groups] }));
}
export function initialGenerationForm() {
  return { objective: 'hipertrofia', level: 'intermediario', workout_type: 'musculacao',
    training_location: '', available_equipment: null, session_minutes: 45, weeks: 4,
    single: false, training_days_per_week: 3, generation_mode: 'periodo', muscle_groups: [],
    split_type: 'ABC', split_config: splitConfig('ABC'), include_cardio: false,
    cardio_type: 'corrida', cardio_mode: 'hibrido', running_goal: '5km',
    preferred_terrain: 'asfalto', calisthenics_focus: 'full_body', health_condition: '', avoid_text: '' };
}
export function generationPayload(form) {
  if (!form.training_location) throw new Error('Informe onde pretende treinar.');
  if (form.available_equipment === null) throw new Error('Declare os equipamentos ou selecione “Nenhum equipamento”.');
  const weeks = Number(form.weeks), frequency = Number(form.training_days_per_week);
  if (![1, 4, 8, 12].includes(weeks) || !Number.isInteger(frequency) || frequency < 2 || frequency > 7) throw new Error('Confira a duração e a frequência.');
  const split = !form.single && ['musculacao', 'hibrido'].includes(form.workout_type) && form.generation_mode === 'tipo_treino';
  const strength = ['musculacao', 'hibrido'].includes(form.workout_type);
  if (form.single && strength && (form.workout_type === 'hibrido' || form.include_cardio) && form.cardio_mode === 'hibrido_alternado') throw new Error('Para uma sessão única, combine força e condicionamento na mesma sessão ou escolha um planejamento com mais sessões.');
  if (split) {
    if (form.split_config.some(s => !s.muscle_groups.length)) throw new Error('Selecione os grupos musculares de cada divisão.');
    const strengthSlots = weeks * ((form.workout_type === 'hibrido' || form.include_cardio) && form.cardio_mode === 'hibrido_alternado' ? Math.ceil(frequency / 2) : frequency);
    if (strengthSlots < form.split_config.length) throw new Error('O calendário precisa incluir todas as divisões. Aumente a duração ou a frequência, ou escolha menos divisões.');
  }
  const body = { objective: form.objective, level: form.level, workout_type: form.workout_type,
    training_location: form.training_location, available_equipment: [...form.available_equipment].sort(),
    session_minutes: Number(form.session_minutes), health_condition: form.health_condition.trim() || null,
    avoid_exercises: form.avoid_text.split('\n').map(s => s.trim()).filter(Boolean),
    generation_mode: split ? 'tipo_treino' : 'periodo',
    duration: form.single ? 'dia' : split ? 'ciclo' : ({ 1: 'semana', 4: 'mes' }[weeks] || 'ciclo'),
    cycle_weeks: form.single ? 1 : weeks, muscle_groups: strength && !split ? form.muscle_groups : [],
  };
  if (!form.single) body.training_days_per_week = frequency;
  if (split) Object.assign(body, { split_type: form.split_type, split_config: form.split_config });
  if (form.workout_type === 'calistenia') body.calisthenics_focus = form.calisthenics_focus;
  if (form.workout_type === 'corrida') Object.assign(body, { running_goal: form.running_goal, preferred_terrain: form.preferred_terrain });
  if (form.workout_type === 'hibrido' || (form.workout_type === 'musculacao' && form.include_cardio)) Object.assign(body, {
    include_cardio: true, cardio_type: form.cardio_type, cardio_mode: form.cardio_mode,
  });
  return body;
}
export function generationCount(form) { return form.single ? 1 : Number(form.weeks) * Number(form.training_days_per_week); }
export function uncertainGeneration(error) {
  const status = error?.response?.status, code = error?.response?.data?.detail?.code;
  // These typed failures occur before persistence. Transport/internal failures may follow a commit.
  if (typeof code === 'string' && (code.startsWith('ai_') || code.startsWith('workout_generation_'))) return false;
  return !status || status >= 500;
}
export function createGenerationRequest(makeKey = () => crypto.randomUUID()) {
  let current = null;
  return {
    begin(payload) {
      if (current?.pending) return null;
      if (!current?.uncertain) current = { key: makeKey(), payload: JSON.parse(JSON.stringify(payload)) };
      current.pending = true;
      return { key: current.key, payload: current.payload };
    },
    finish(error) {
      if (!error || !uncertainGeneration(error)) current = null;
      else Object.assign(current, { pending: false, uncertain: true });
      return Boolean(current?.uncertain);
    },
  };
}
