"""Bounded, deterministic source analysis. Never calls an AI provider."""
import difflib
import re
import unicodedata
from datetime import date

RULE_VERSION = 'edital-radar-1'
CATEGORIES = {
    'roles': ('cargo', 'vaga', 'remuneracao', 'salario'),
    'syllabus': ('disciplina', 'conteudo programatico', 'topico'),
    'weights': ('peso', 'pontuacao', 'questao', 'questoes'),
    'rules': ('eliminatorio', 'classificatorio', 'criterio', 'recurso'),
    'calendar': ('inscricao', 'isencao', 'pagamento', 'prova', 'resultado'),
}
EVENTS = (
    ('registration', ('inscricao', 'inscricoes')),
    ('exemption', ('isencao',)), ('payment', ('pagamento',)),
    ('exam', ('aplicacao da prova', 'aplicacao das provas', 'prova objetiva', 'prova discursiva')),
    ('location', ('local de prova', 'locais de prova')),
    ('appeal', ('recurso', 'recursos')), ('result', ('resultado',)),
    ('appointment', ('nomeacao',)), ('taking_office', ('posse',)),
    ('documents', ('entrega de documentos',)),
)
MONTHS = {name: index for index, name in enumerate(('janeiro','fevereiro','marco','abril','maio','junho',
    'julho','agosto','setembro','outubro','novembro','dezembro'), 1)}


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.lower()) if not unicodedata.combining(c))


def impact(previous, current, *, baseline=False, partial=False):
    # Comparing 200k-character inputs with SequenceMatcher can be quadratic.
    # Retain only a bounded line window and report omitted evidence explicitly.
    before, after = previous.splitlines(), current.splitlines()
    clipped = len(before) > 1500 or len(after) > 1500
    added, removed = [], []
    if not baseline:
        for line in difflib.unified_diff(before[:1500], after[:1500], n=0):
            if line.startswith('+') and not line.startswith('+++'): added.append(line[1:])
            if line.startswith('-') and not line.startswith('---'): removed.append(line[1:])
    evidence = normalized('\n'.join(added + removed))
    categories = [key for key, words in CATEGORIES.items() if any(word in evidence for word in words)]
    return {'rule_version': RULE_VERSION, 'baseline': baseline,
            'added': added[:60], 'removed': removed[:60],
            'partial': bool(partial or clipped or len(added) > 60 or len(removed) > 60),
            'categories': categories, 'classification': 'inferred',
            'confidence': 'heuristic_text_match',
            'syllabus_impact': {'status': 'review_required' if 'syllabus' in categories else 'not_established',
                'topic_changes_confirmed': False},
            'plan_impact': {'status': 'review_required' if categories else 'not_established',
                'recalculation_applied': False},
            'plan_changed': False, 'additional_minutes': None,
            'requires_confirmation': bool(categories)}


def official_dates(text, *, official):
    """Only full numeric dates paired with a nearby explicit event label.

    These are literal extracted candidates, not a legal interpretation of a
    deadline. Never supply a missing year or resolve conflicting source dates.
    """
    if not official: return []
    results = []
    for line in text[:200000].splitlines():
        folded = normalized(line)
        labels = [kind for kind, terms in EVENTS if any(term in folded for term in terms)]
        if len(labels) != 1: continue
        matches=[(match,int(match[2])) for match in re.finditer(r'(?<!\d)(\d{1,2})[/.](\d{1,2})[/.](\d{4})(?!\d)', folded)]
        matches.extend((match,MONTHS[match[2]]) for match in re.finditer(
            r'(?<!\d)(\d{1,2})\s+de\s+('+'|'.join(MONTHS)+r')\s+de\s+(\d{4})(?!\d)',folded))
        for match,month in sorted(matches,key=lambda item:item[0].start()):
            try: value = date(int(match[3]), month, int(match[1])).isoformat()
            except ValueError: continue
            if len(results) >= 100: return results
            candidate = {'event': labels[0], 'date': value, 'quote': line[max(0, match.start()-180):match.end()+180],
                         'provenance': 'extracted', 'confidence': 'literal_date', 'requires_confirmation': True}
            if candidate not in results: results.append(candidate)
    return results
