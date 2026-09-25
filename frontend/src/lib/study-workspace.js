export const STUDY_VIEWS = ['edital', 'verticalizado', 'cronograma', 'estudar'];

export function normalizeStudyText(value) {
  return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

export function topicRows(discipline) {
  const source = Array.isArray(discipline.conteudo_programatico) && discipline.conteudo_programatico.length ? discipline.conteudo_programatico : (Array.isArray(discipline.topicos) ? discipline.topicos : []).map(assunto => ({ assunto }));
  return source.flatMap((item, index) => {
    const parent = typeof item === 'string' ? item : item?.assunto;
    if (typeof parent !== 'string' || !parent.trim()) return [];
    const subtopics = item && Array.isArray(item.subtopicos) ? item.subtopicos : typeof item?.subtopicos === 'string' ? [item.subtopicos] : [];
    const key = item?.topic_key ?? String(index);
    return [{ key, title: parent, depth: 0 }, ...subtopics.map((title, subindex) => ({ key: item?.subtopic_keys?.[subindex] ?? `${key}_${subindex}`, title, depth: 1, parent })).filter(row => typeof row.title === 'string' && row.title.trim())];
  });
}

export function blockMinutes(block) {
  const parse = value => {
    const match = /^(\d{1,2}):(\d{2})$/.exec(value || '');
    return match && Number(match[1]) < 24 && Number(match[2]) < 60 ? Number(match[1]) * 60 + Number(match[2]) : null;
  };
  const start = parse(block.start_time), end = parse(block.end_time);
  return start !== null && end !== null && end > start ? end - start : 25;
}

export function displayStudyDate(value) {
  if (!value) return 'Não informado';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : String(value);
}
