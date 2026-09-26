"""Conservative cross-check of explicitly delimited syllabus headings, not AI claims."""
import re
from edital_quality import normalized_name


def subject_key(name):
    # Parenthetical legal references qualify the source, not the subject title.
    return normalized_name(re.sub(r'\([^)]*\)', '', name))


def syllabus_sections(pages):
    common, roles = [], []
    active = False
    current = None
    common_applies = False
    for page in pages:
        for line in page['text'].splitlines():
            line = line.strip()
            normalized = normalized_name(line)
            if normalized in ('conteudo programatico', 'conteudos programaticos'):
                active = True
                continue
            if not active:
                continue
            if re.fullmatch(r'ANEXO\s+[IVX\d]+', line):
                active = False
                continue
            if 'conhecimentos gerais' in normalized and 'todos os cargos' in normalized:
                common_applies = True
            heading = re.match(r'^([A-Z]\d{2})\s*[-–—]\s*(.+)$', line)
            if heading:
                current = {'code': heading[1], 'name': heading[2], 'subjects': []}
                roles.append(current)
                continue
            title = line.split(':', 1)[0].strip()
            # Some PDF headings omit ':'; recognize a run of capitalized words
            # only when followed by mixed-case prose, never an all-caps body line.
            if ':' not in line:
                prefix = re.match(r'^([A-ZÀ-Ý]+(?:[ -]+[A-ZÀ-Ý]+)+)\s+[A-ZÀ-Ý][a-zà-ÿ]', line)
                title = prefix[1] if prefix else ''
            if not 5 <= len(title) <= 150 or title.upper() != title:
                continue
            if title.startswith(('ABNT', 'ISO', 'NBR', 'ART.', 'CONHECIMENTOS')):
                continue
            item = {'name': title, 'page': page['page'], 'quote': line[:1200]}
            if current is not None:
                current['subjects'].append(item)
            elif common_applies:
                common.append(item)
    return common, roles


def audit_cargos(cargos, pages):
    common, roles = syllabus_sections(pages)
    for cargo in cargos:
        code = str(cargo.get('codigo') or cargo.get('codigo_cargo') or '').strip().upper()
        if not code:
            match = re.match(r'^([A-Z]\d{2})\b', cargo.get('nome', ''))
            code = match[1] if match else ''
        matches = [r for r in roles if (r['code'] == code if code else normalized_name(r['name']) == normalized_name(cargo.get('nome')))]
        audit = {'status': 'nao_verificado', 'missing': [], 'expected': [],
                 'notice': 'A conferência automática não substitui a leitura do edital. Quantidades e pesos de blocos não são quantidades por disciplina.'}
        if len(matches) == 1 and matches[0]['subjects']:
            expected = common + matches[0]['subjects']
            names = {subject_key(d.get('nome', '')) for d in cargo.get('disciplinas', [])}
            missing = [item for item in expected if subject_key(item['name']) not in names]
            audit.update(status='titulos_ausentes' if missing else 'titulos_conferidos',
                         missing=missing, expected=expected, cargo_code=matches[0]['code'])
            if missing:
                cargo['disciplinas_status'] = 'incompleto'
                cargo['disciplinas_aviso'] = 'Títulos encontrados no conteúdo programático não constam na análise: ' + '; '.join(x['name'] for x in missing) + '. Confira e corrija antes de criar o programa.'
        cargo['conferencia'] = audit
    return cargos
