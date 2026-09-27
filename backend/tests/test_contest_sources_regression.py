import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contest_sources import validate_url, public_addresses, provider_for, trust, GenericOfficialConnector, SourceUnavailable


class ContestSourceTests(unittest.TestCase):
    def test_private_credentials_non_https_and_ports_rejected(self):
        for url in ['http://example.com', 'https://127.0.0.1/a', 'https://169.254.169.254/', 'https://localhost/', 'https://a:b@example.com/', 'https://example.com:8080/', 'file:///etc/passwd', 'https://10.0.0.1/', 'https://example.com\r\nHeader: value']:
            with self.subTest(url=url), self.assertRaises(SourceUnavailable): validate_url(url)

    def test_dns_mixed_public_and_private_rejected(self):
        with patch('contest_sources.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443)), (2, 1, 6, '', ('10.0.0.1', 443))]):
            with self.assertRaises(SourceUnavailable): public_addresses('example.com')

    def test_generic_normalization_dedup_trust_and_dates(self):
        html = '<script>SECRET</script><a href="/docs/edital.pdf">Edital de abertura</a><a href="/docs/edital.pdf">Duplicado</a><a href="https://news.example.com/prova.pdf">Prova</a><a href="javascript:alert(1)">Edital</a>'
        page = GenericOfficialConnector().normalize(html, 'https://orgao.gov.br/concurso')
        self.assertNotIn('SECRET', page.text)
        self.assertEqual(len(page.documents), 2)
        self.assertTrue(page.documents[0]['official'])
        self.assertFalse(page.documents[1]['official'])
        self.assertIsNone(page.documents[0]['published_at'])
        self.assertEqual(page.documents[0]['hash_basis'], 'url_and_title')

    def test_provider_selection_not_specific_to_contest(self):
        for exam in ['trt22', 'receita', 'academico']:
            self.assertEqual(provider_for(f'https://conhecimento.fgv.br/concursos/{exam}').name, 'fgv')
        self.assertEqual(provider_for('https://www.cebraspe.org.br/concursos/teste').name, 'cebraspe')
        self.assertEqual(provider_for('https://university.example.com/exam').name, 'generic')
        self.assertEqual(trust('https://fgv.br.attacker.com/'), 'USER_PROVIDED')

    def test_robots_disallow_and_access_blocks_never_fetch_page(self):
        for response in [(200, {}, b'User-agent: *\nDisallow: /'), (403, {}, b''), (429, {}, b''), (503, {}, b'')]:
            with self.subTest(response=response), patch('contest_sources.fetch_public', return_value=response) as fetch:
                with self.assertRaises(SourceUnavailable): GenericOfficialConnector().poll('https://example.com/contest')
                self.assertEqual(fetch.call_count, 1)

    def test_conditional_fetch_and_unchanged_content(self):
        with patch('contest_sources.fetch_public', side_effect=[(404, {}, b''), (304, {}, b'')]) as fetch:
            self.assertIsNone(GenericOfficialConnector().poll('https://example.com/contest', 'v1', 'yesterday'))
            self.assertEqual(fetch.call_args.args[1], {'If-None-Match': 'v1', 'If-Modified-Since': 'yesterday'})

    def test_pdf_uses_content_hash_even_without_extractable_text(self):
        from io import BytesIO
        from pypdf import PdfWriter
        import hashlib
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        buffer = BytesIO(); writer.write(buffer)
        content = buffer.getvalue()
        with patch('contest_sources.fetch_public', side_effect=[(404, {}, b''), (200, {'content-type': 'application/pdf'}, content)]):
            page = GenericOfficialConnector().poll('https://example.com/edital.pdf')
        self.assertEqual(page.content_hash, hashlib.sha256(content).hexdigest())
        self.assertEqual(page.documents[0]['hash_basis'], 'document_bytes')
        self.assertEqual(page.documents[0]['text_extraction'], 'unavailable')


if __name__ == '__main__': unittest.main()
