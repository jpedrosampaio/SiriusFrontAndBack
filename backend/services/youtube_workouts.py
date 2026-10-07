"""On-demand official YouTube search, bounded cache and single-flight requests."""
import asyncio
import html
import os
import re
import time
import unicodedata
from collections import OrderedDict

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from services.auth_routes import account

router = APIRouter(prefix='/workouts')
TTL = 86400
MAX_CACHE = 256
MAX_PENDING = 16
cache = OrderedDict()
pending = {}
daily_searches = 0
quota_day = ''


def clean(value, maximum=100):
    value = unicodedata.normalize('NFKC', value).strip()
    if not value or len(value) > maximum or any(not (c.isalnum() or c.isspace() or c in '-(),.') for c in value):
        raise HTTPException(422, 'Informe um nome de exercício válido.')
    return ' '.join(value.split())


def key_for(exercise, group):
    return (exercise.casefold(), group.casefold())


async def fetch(exercise, group):
    global daily_searches, quota_day
    key = os.getenv('YOUTUBE_API_KEY', '').strip()
    if not key:
        return {'status': 'not_configured', 'videos': []}
    day = time.strftime('%Y-%m-%d', time.gmtime())
    if day != quota_day:
        quota_day, daily_searches = day, 0
    # Conservative per-process ceiling; never enable billing or keep trying after quota failure.
    if daily_searches >= 50:
        return {'status': 'unavailable', 'videos': []}
    daily_searches += 1
    aerobic = any(term in exercise.casefold() for term in ('corrida', 'caminhada', 'bicicleta', 'natação', 'alongamento', 'yoga'))
    query = f'{exercise} {group} execução correta' + ('' if aerobic else ' musculação')
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=3)) as client:
            response = await client.get('https://www.googleapis.com/youtube/v3/search', headers={'X-Goog-Api-Key': key}, params={
                'q': query, 'part': 'snippet', 'type': 'video', 'maxResults': 3,
                'order': 'relevance', 'relevanceLanguage': 'pt', 'regionCode': 'BR',
                'videoEmbeddable': 'true', 'videoSyndicated': 'true', 'safeSearch': 'moderate'})
        if response.status_code != 200:
            return {'status': 'unavailable', 'videos': []}
        videos = []
        for item in response.json().get('items', [])[:3]:
            vid = item.get('id', {}).get('videoId', '')
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
                continue
            snippet = item.get('snippet', {})
            videos.append({'video_id': vid, 'title': html.unescape(str(snippet.get('title', '')))[:300],
                'channel': html.unescape(str(snippet.get('channelTitle', '')))[:200],
                'thumbnail': f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg',
                'url': f'https://www.youtube.com/watch?v={vid}'})
        return {'status': 'ok', 'videos': videos}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        # Never log exception details or request headers containing the secret.
        return {'status': 'unavailable', 'videos': []}


async def _fill(key, exercise, group):
    try:
        result = await fetch(exercise, group)
        cache[key] = (time.monotonic() + (TTL if result['status'] == 'ok' else 60), result)
        cache.move_to_end(key)
        while len(cache) > MAX_CACHE:
            cache.popitem(last=False)
        return result
    finally:
        pending.pop(key, None)


async def search(exercise, group=''):
    exercise = clean(exercise)
    group = clean(group, 60) if group.strip() else ''
    key = key_for(exercise, group)
    current = cache.get(key)
    if current and current[0] > time.monotonic():
        cache.move_to_end(key)
        return {'exercise': exercise, **current[1]}
    if key not in pending:
        if len(pending) >= MAX_PENDING:
            return {'exercise': exercise, 'status': 'unavailable', 'videos': []}
        pending[key] = asyncio.create_task(_fill(key, exercise, group))
    return {'exercise': exercise, **await asyncio.shield(pending[key])}


@router.get('/tutorial-videos')
async def tutorial_videos(request: Request, exercise: str = Query(min_length=1, max_length=100),
                          muscle_group: str = Query(default='', max_length=60)):
    await account(request)
    return await search(exercise, muscle_group)
