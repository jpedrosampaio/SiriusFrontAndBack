"""Owned document retrieval. Lexical fallback is explicit, never called vector search."""
import hashlib
import re
import unicodedata


def terms(text):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    return set(re.findall(r'[a-z0-9]{3,}', text)) - {'para', 'como', 'uma', 'que', 'com', 'por', 'dos', 'das'}


def chunks(pages, size=1400):
    for number, page in enumerate(pages, 1):
        text = page.get('text', '') if isinstance(page, dict) else str(page)
        page_number = page.get('page', number) if isinstance(page, dict) else number
        for start in range(0, len(text), size-150):
            content = text[start:start+size].strip()
            if content:
                yield {'page': page_number, 'text': content, 'hash': hashlib.sha256(content.encode()).hexdigest(), 'terms': sorted(terms(content))[:250]}
