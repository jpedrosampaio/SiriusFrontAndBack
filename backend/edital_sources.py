"""Source locations are matched against extracted pages, never supplied by the LLM."""
import re
import unicodedata


def normalize(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', value.casefold()) if not unicodedata.combining(c)).split())


def source_pages(text):
    pieces = re.split(r'\[PÁGINA (\d+)\]\n', text or '')
    return [{'page': int(pieces[i]), 'text': pieces[i + 1]} for i in range(1, len(pieces) - 1, 2)]


def locate_subject(name, pages):
    needle = normalize(name or '')
    if len(needle) < 4:
        return []
    matches = []
    for page in pages:
        # Preserve the original line for the user to verify in context.
        lines = page['text'].splitlines()
        for index, line in enumerate(lines):
            if needle in normalize(line):
                matches.append({'page': page['page'], 'quote': '\n'.join(lines[max(0, index - 1):index + 5])[:1200]})
                break
    return matches[:10]
