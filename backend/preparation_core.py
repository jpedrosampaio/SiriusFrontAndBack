"""Pure, versioned preparation rules; no database, authentication or AI imports."""
VERSION = 'preparation-state-3.0.1'


def learning_stage(covered, estimate, last_date, today):
    if not estimate['samples']:
        return 'exposed' if covered else 'not_started'
    if estimate['samples'] < 10 or estimate['score'] < 60:
        return 'practicing'
    if estimate['confidence'] != 'high' or estimate['score'] < 80:
        return 'consolidating'
    return 'maintenance' if last_date and (today-last_date).days > 14 else 'mastered'
