"""Pure, versioned preparation rules; no database, authentication or AI imports."""
VERSION = 'preparation-state-3.0.1'


def exam_day(program,target=None):
    """A personal study goal cannot become an official exam countdown."""
    if target and target.metadata_origin=='edital_reviewed':return target.exam_date
    if (program.edital_data or {}).get('universal_edital'):
        from datetime import date
        try:return date.fromisoformat(program.edital_data.get('concurso',{}).get('data_prova'))
        except (TypeError,ValueError):return None
    return (target.exam_date if target else None) or program.target_date


def learning_stage(covered, estimate, last_date, today):
    if not estimate['samples']:
        return 'exposed' if covered else 'not_started'
    if estimate['samples'] < 10 or estimate['score'] < 60:
        return 'practicing'
    if estimate['confidence'] != 'high' or estimate['score'] < 80:
        return 'consolidating'
    return 'maintenance' if last_date and (today-last_date).days > 14 else 'mastered'
