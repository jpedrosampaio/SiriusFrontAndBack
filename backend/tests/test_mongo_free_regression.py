"""Keep legacy persistence dependencies out of the normal server runtime."""
import ast
from pathlib import Path
import unittest
import logging


class RuntimeBoundary(unittest.TestCase):
    def test_runtime_has_no_mongo_import_or_configuration(self):
        root=Path(__file__).resolve().parents[1]
        found=[]
        for path in root.rglob('*.py'):
            if any(part in {'tests','scripts','alembic','__pycache__'} for part in path.relative_to(root).parts):continue
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
                modules=[alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                if any(module.split('.')[0] in {'motor','pymongo','bson','gridfs'} for module in modules):found.append(str(path))
                if isinstance(node,ast.Constant) and node.value in ('MONGO_URL','DB_NAME'):found.append(str(path))
        requirements=(root/'requirements.txt').read_text().lower()
        self.assertNotIn('motor',requirements);self.assertNotIn('pymongo',requirements)
        self.assertEqual(found,[])

    def test_telegram_tokens_are_removed_from_http_logs(self):
        from operations import RedactTelegramToken
        record=logging.LogRecord('httpx',logging.INFO,'',0,'HTTP Request: %s %s',('POST','https://api.telegram.org/botsecret-token/sendMessage'),None)
        RedactTelegramToken().filter(record)
        self.assertNotIn('secret-token',record.getMessage());self.assertIn('[redacted]',record.getMessage())
