"""Public-source adapters. No browser automation, authentication or access bypass."""
import hashlib
import json
import http.client
import ipaddress
import re
import socket
import ssl
import time
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

AGENT = 'SiriusContestWatcher/1.0'
LIMIT = 2 * 1024 * 1024


class SourceUnavailable(ValueError):
    pass


def validate_url(value):
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.port not in (None, 443):
            raise SourceUnavailable('Use uma URL pública HTTPS, sem credenciais ou porta personalizada.')
        host = url.hostname.encode('idna').decode('ascii').lower()
        if any(host == domain or host.endswith('.' + domain) for domain in ('tecconcursos.com.br', 'qconcursos.com')):
            raise SourceUnavailable('Esta plataforma exige uma integração autorizada; acompanhamento automático não permitido.')
        if len(value) > 2000 or any(c in value for c in ('\r', '\n', '\\')):
            raise SourceUnavailable('URL inválida.')
        if '.' not in host or host.endswith(('.local', '.internal', '.localhost')):
            raise SourceUnavailable('Endereço local não permitido.')
        try:
            if not ipaddress.ip_address(host).is_global: raise SourceUnavailable('Endereço não público.')
        except ValueError as exc:
            if isinstance(exc, SourceUnavailable): raise
        return urlunsplit(('https', host, url.path or '/', url.query, ''))
    except (UnicodeError, ValueError) as exc:
        raise SourceUnavailable('Use uma URL pública HTTPS válida.') from exc


def public_addresses(host):
    addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise SourceUnavailable('A fonte não resolve para um endereço público permitido.')
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip):
        super().__init__(host, timeout=12, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        # Connect to the previously validated IP; never resolve a second time.
        raw = socket.create_connection((self.ip, 443), timeout=self.timeout)
        try: self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def fetch_public(url, headers=None):
    url = validate_url(url)
    parsed = urlsplit(url)
    connection = PinnedHTTPS(parsed.hostname, public_addresses(parsed.hostname)[0])
    try:
        connection.request('GET', urlunsplit(('', '', parsed.path, parsed.query, '')), headers={'User-Agent': AGENT, 'Accept': 'text/html,text/plain,application/pdf', 'Accept-Encoding': 'identity', **(headers or {})})
        response = connection.getresponse()
        # Redirects deliberately require a new explicit source registration. This
        # avoids crossing host trust boundaries or bypassing per-origin throttles.
        if 300 <= response.status < 400 and response.status != 304:
            raise SourceUnavailable('A página redirecionou. Cadastre o endereço final público exibido pelo navegador.')
        content = response.read(LIMIT + 1)
        if len(content) > LIMIT: raise SourceUnavailable('Página maior que o limite de 2 MB.')
        return response.status, {k.lower(): v for k, v in response.getheaders()}, content
    finally:
        connection.close()


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.text, self.current, self.suppressed = [], [], None, 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'): self.suppressed += 1
        if tag == 'a': self.current = [dict(attrs).get('href', ''), []]

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'): self.suppressed = max(0, self.suppressed - 1)
        if tag == 'a' and self.current:
            self.links.append((self.current[0], ' '.join(self.current[1]).strip()))
            self.current = None

    def handle_data(self, data):
        if not self.suppressed and data.strip():
            self.text.append(data.strip())
            if self.current: self.current[1].append(data.strip())


def trust(url):
    host = urlsplit(url).hostname or ''
    return 'OFFICIAL' if host.endswith(('.gov.br', '.jus.br', '.leg.br')) or any(host == h or host.endswith('.' + h) for h in ('fgv.br', 'cebraspe.org.br', 'fcc.org.br', 'vunesp.com.br', 'institutoaocp.org.br', 'ibfc.org.br')) else 'USER_PROVIDED'


def document_type(title, url):
    text = unicodedata.normalize('NFKD', title + ' ' + url).encode('ascii', 'ignore').decode().lower()
    for word, kind in [('retific', 'rectification'), ('gabarito', 'answer_key'), ('resultado', 'result'), ('prova', 'exam'), ('edital', 'notice'), ('comunicado', 'announcement')]:
        if word in text: return kind
    return 'document' if urlsplit(url).path.lower().endswith('.pdf') else None


@dataclass
class SourcePage:
    text: str
    documents: list
    content_hash: str
    etag: str | None = None
    modified: str | None = None
    hash_basis: str = 'page_text'
    partial: bool = False


class ContestSourceProvider:
    name = 'generic'
    capabilities = ('get_metadata', 'list_updates', 'list_documents', 'list_exams', 'list_results', 'poll')

    def get_metadata(self, page, url):
        return {'source': url, 'source_type': trust(url), 'provider': self.name, 'content_hash': page.content_hash}

    def list_documents(self, page):
        return list(page.documents)

    def list_updates(self, page):
        return [d for d in page.documents if d['document_type'] in ('notice', 'rectification', 'announcement')]

    def list_exams(self, page):
        return [d for d in page.documents if d['document_type'] in ('exam', 'answer_key')]

    def list_results(self, page):
        return [d for d in page.documents if d['document_type'] == 'result']

    def normalize(self, html, url):
        parser = PageParser()
        parser.feed(html)
        documents, seen = [], set()
        for href, title in parser.links:
            try: link = validate_url(urljoin(url, href))
            except SourceUnavailable: continue
            kind = document_type(title, link)
            if not kind or link in seen: continue
            seen.add(link)
            digest = hashlib.sha256((link + '\n' + title).encode()).hexdigest()
            documents.append({'title': title[:500] or 'Documento publicado', 'url': link, 'document_url': link if urlsplit(link).path.lower().endswith('.pdf') else None,
                              'document_type': kind, 'hash': digest, 'hash_basis': 'url_and_title', 'source_type': trust(link), 'official': trust(link) == 'OFFICIAL', 'published_at': None})
            if len(documents) == 300: break
        full_text = '\n'.join(parser.text)
        text = full_text[:200000]
        # Link replacements can change the edital even when anchor text does not.
        metadata=sorted((d['url'],d['title'],d['document_type']) for d in documents)
        digest=hashlib.sha256((text+'\n'+json.dumps(metadata,ensure_ascii=False,separators=(',',':'))).encode()).hexdigest()
        page = SourcePage(text, documents, digest,hash_basis='page_text_and_links')
        page.partial = len(full_text) > 200000 or len(documents) >= 300
        return page

    def poll(self, url, etag=None, modified=None):
        url = validate_url(url)
        origin = 'https://' + urlsplit(url).netloc
        code, _, robots = fetch_public(origin + '/robots.txt')
        if code in (401, 403, 429) or code >= 500: raise SourceUnavailable('Verificação de robots indisponível ou acesso limitado; consulta adiada.')
        if code == 200:
            rules = RobotFileParser()
            rules.parse(robots.decode('utf-8', 'replace').splitlines())
            if not rules.can_fetch(AGENT, url): raise SourceUnavailable('A fonte não permite consulta automática desta página.')
            delay = rules.crawl_delay(AGENT) or 0
            rate = rules.request_rate(AGENT)
            if rate and rate.requests: delay = max(delay, rate.seconds / rate.requests)
            if delay > 60: raise SourceUnavailable('A fonte exige um intervalo especial; consulte pelo navegador.')
            if delay: time.sleep(delay)
        headers = {}
        if etag: headers['If-None-Match'] = etag
        if modified: headers['If-Modified-Since'] = modified
        status, response_headers, body = fetch_public(url, headers)
        if status == 304: return None
        if status != 200: raise SourceUnavailable(f'Fonte respondeu HTTP {status}; consulta adiada.')
        mime = response_headers.get('content-type', '')
        if 'application/pdf' in mime or body.startswith(b'%PDF-'):
            from io import BytesIO
            from pypdf import PdfReader
            try:
                reader = PdfReader(BytesIO(body))
                if reader.is_encrypted or len(reader.pages) > 200: raise SourceUnavailable('PDF protegido ou acima do limite de 200 páginas.')
                parts, remaining = [], 200000
                for pdf_page in reader.pages:
                    part = (pdf_page.extract_text() or '')[:remaining]
                    parts.append(part)
                    remaining -= len(part)
                    if remaining <= 0: break
                joined = '\n'.join(parts)
                partial = remaining <= 0 or len(joined) > 200000
                text = joined[:200000]
            except SourceUnavailable: raise
            except Exception: raise SourceUnavailable('Não foi possível ler o PDF público.') from None
            digest = hashlib.sha256(body).hexdigest()
            page = SourcePage(text, [{'title': urlsplit(url).path.rsplit('/', 1)[-1] or 'PDF acompanhado', 'url': url, 'document_url': url,
                'document_type': document_type('', url) or 'document', 'hash': digest, 'hash_basis': 'document_bytes',
                'source_type': trust(url), 'official': trust(url) == 'OFFICIAL', 'published_at': None,
                'text_extraction': 'available' if text.strip() else 'unavailable', 'text_partial': partial}], digest)
            page.etag, page.modified = response_headers.get('etag'), response_headers.get('last-modified')
            page.hash_basis = 'document_bytes'
            page.partial = partial
            return page
        if not any(t in mime for t in ('text/html', 'text/plain', 'application/xhtml')): raise SourceUnavailable('Cadastre uma página pública ou PDF.')
        text = body.decode('utf-8', 'replace')
        if any(w in text.lower() for w in ('cf-chl-', 'g-recaptcha', 'h-captcha')): raise SourceUnavailable('A página exige verificação de acesso; consulte pelo navegador.')
        page = self.normalize(text, url)
        page.etag, page.modified = response_headers.get('etag'), response_headers.get('last-modified')
        return page


class GenericOfficialConnector(ContestSourceProvider):
    pass


class FGVConnector(GenericOfficialConnector):
    name = 'fgv'

    def normalize(self, html, url):
        page = super().normalize(html, url)
        # FGV lists documents as anchors; normalize relative /sites/default/files
        # paths through the shared parser. No assumptions about a specific exam.
        return page


class CebraspeConnector(GenericOfficialConnector):
    name = 'cebraspe'

    def normalize(self, html, url):
        return super().normalize(html, url)


def provider_for(url):
    host = urlsplit(url).hostname or ''
    if host == 'conhecimento.fgv.br' or host.endswith('.conhecimento.fgv.br'): return FGVConnector()
    if host == 'cebraspe.org.br' or host.endswith('.cebraspe.org.br'): return CebraspeConnector()
    return GenericOfficialConnector()
