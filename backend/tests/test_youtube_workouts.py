import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch
import httpx
from fastapi import HTTPException
from fastapi import FastAPI
from services import youtube_workouts as yt


class YouTubeWorkouts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        yt.cache.clear(); yt.pending.clear()

    async def test_no_key_and_invalid_input(self):
        with patch.dict(os.environ, {'YOUTUBE_API_KEY': ''}):
            self.assertEqual((await yt.search('Supino'))['status'], 'not_configured')
        for value in ('', 'https://example.org', '<script>', 'a' * 101, 'Supino\n?q=test'):
            with self.assertRaises(HTTPException): await yt.search(value)

    async def test_official_query_projection_and_secret_not_serialized(self):
        response = httpx.Response(200, json={'items': [{'id': {'videoId': 'abcdefghijk'}, 'snippet': {'title': 'Supino &amp; execução', 'channelTitle': 'Canal'}}] * 5})
        with patch.dict(os.environ, {'YOUTUBE_API_KEY': 'secret-test'}), patch.object(httpx.AsyncClient, 'get', AsyncMock(return_value=response)) as get:
            result = await yt.search(' Supino   reto ', 'Peito')
        args = get.call_args.kwargs['params']
        self.assertNotIn('key', args)
        self.assertEqual(get.call_args.kwargs['headers']['X-Goog-Api-Key'], 'secret-test')
        self.assertEqual(args['q'], 'Supino reto Peito execução correta musculação')
        for k, v in {'type': 'video', 'maxResults': 3, 'videoEmbeddable': 'true', 'videoSyndicated': 'true'}.items(): self.assertEqual(args[k], v)
        self.assertEqual(len(result['videos']), 3)
        self.assertNotIn('secret-test', str(result))
        self.assertEqual(result['videos'][0]['title'], 'Supino & execução')

    async def test_cache_coalesces_and_expires(self):
        async def slow(*args):
            await asyncio.sleep(.01)
            return {'status': 'ok', 'videos': []}
        with patch.object(yt, 'fetch', side_effect=slow) as fetch:
            await asyncio.gather(*(yt.search('Supino', 'Peito') for _ in range(10)))
            await yt.search('supino', 'peito')
            self.assertEqual(fetch.call_count, 1)
            key = yt.key_for('Supino', 'Peito'); yt.cache[key] = (0, yt.cache[key][1])
            await yt.search('Supino', 'Peito'); self.assertEqual(fetch.call_count, 2)
        self.assertFalse(yt.pending)

    async def test_failures_and_empty_results(self):
        for code in (403, 429, 500):
            with patch.dict(os.environ, {'YOUTUBE_API_KEY': 'secret'}), patch.object(httpx.AsyncClient, 'get', AsyncMock(return_value=httpx.Response(code))):
                self.assertEqual((await yt.fetch('Supino', ''))['status'], 'unavailable')
        with patch.dict(os.environ, {'YOUTUBE_API_KEY': 'secret'}), patch.object(httpx.AsyncClient, 'get', AsyncMock(side_effect=httpx.ReadTimeout('timeout'))):
            self.assertEqual((await yt.fetch('Supino', ''))['status'], 'unavailable')
        with patch.dict(os.environ, {'YOUTUBE_API_KEY': 'secret'}), patch.object(httpx.AsyncClient, 'get', AsyncMock(return_value=httpx.Response(200, json={'items': []}))):
            self.assertEqual((await yt.fetch('Supino', ''))['videos'], [])

    async def test_bounded_cache(self):
        with patch.object(yt, 'MAX_CACHE', 2), patch.object(yt, 'fetch', AsyncMock(return_value={'status': 'ok', 'videos': []})):
            for name in ('Supino', 'Remada', 'Agachamento'): await yt.search(name)
        self.assertEqual(len(yt.cache), 2)

    async def test_endpoint_requires_authentication_before_search(self):
        app=FastAPI(); app.include_router(yt.router,prefix='/api')
        async def denied(request):raise HTTPException(401,'Sessão expirada')
        with patch.object(yt,'account',side_effect=denied),patch.object(yt,'fetch',AsyncMock()) as fetch:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='https://test.local') as client:
                response=await client.get('/api/workouts/tutorial-videos',params={'exercise':'Supino'})
            self.assertEqual(response.status_code,401);fetch.assert_not_called()
