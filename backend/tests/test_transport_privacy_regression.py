"""Real mock transport logs, never remote provider calls."""
import logging
import io
import sys
import unittest
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from operations import RedactTelegramToken


class TransportPrivacy(unittest.IsolatedAsyncioTestCase):
    async def test_mock_provider_transport_retains_status_without_url_secrets(self):
        # assertLogs clears logger filters; capture with a handler preserving production filters.
        output=io.StringIO();logger=logging.getLogger('httpx');level=logger.level
        handler=logging.StreamHandler(output);logger.addHandler(handler);logger.setLevel(logging.INFO)
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(503))) as client:
                await client.get('https://api.telegram.org/bot123:synthetic-token/sendMessage?token=synthetic-query')
        finally:
            logger.removeHandler(handler);logger.setLevel(level)
        message=output.getvalue()
        self.assertIn('503',message);self.assertIn('sendMessage',message)
        self.assertNotIn('synthetic-token',message);self.assertNotIn('synthetic-query',message)

    def test_access_formatter_argument_shape_preserved_and_oauth_query_removed(self):
        args=('127.0.0.1:123','GET','/api/auth/google-session?session_id=synthetic-session','1.1',401)
        record=logging.LogRecord('uvicorn.access',logging.INFO,'test',1,'%s - "%s %s HTTP/%s" %d',args,None)
        self.assertTrue(RedactTelegramToken().filter(record))
        self.assertEqual(len(record.args),5);self.assertEqual(record.args[-1],401)
        self.assertNotIn('synthetic-session',record.getMessage());self.assertIn('/api/auth/google-session',record.getMessage())

    def test_parameterized_transport_url_userinfo_removed_without_changing_types(self):
        record=logging.LogRecord('httpx',logging.INFO,'test',1,'HTTP %s %s status=%d',
            ('GET','https://synthetic-user:synthetic-password@example.test/file?signature=synthetic-signature',503),None)
        RedactTelegramToken().filter(record)
        message=record.getMessage()
        for secret in ('synthetic-user','synthetic-password','synthetic-signature'):self.assertNotIn(secret,message)
        self.assertIn('example.test/file',message);self.assertEqual(record.args[-1],503)
