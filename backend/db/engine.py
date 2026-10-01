"""One lazy engine per process; constructing it never connects or modifies schema."""
import os
from functools import lru_cache

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def database_url(*, direct: bool = False):
    value = os.environ.get('DATABASE_URL_DIRECT') if direct else None
    value = value or os.environ.get('DATABASE_URL')
    if not value:
        raise RuntimeError('DATABASE_URL is required')
    try:
        url = make_url(value)
    except Exception:
        raise RuntimeError('Invalid PostgreSQL configuration') from None
    if url.drivername not in ('postgres', 'postgresql', 'postgresql+psycopg'):
        raise RuntimeError('Only PostgreSQL with psycopg is supported')
    url = url.set(drivername='postgresql+psycopg')
    if (url.host or '').endswith('.neon.tech') and url.query.get('sslmode') not in ('require', 'verify-ca', 'verify-full'):
        raise RuntimeError('Neon requires TLS (sslmode=require or verify-full)')
    return url


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    return create_async_engine(
        database_url(), pool_size=2, max_overflow=1, pool_timeout=15,
        pool_recycle=240, pool_pre_ping=True, echo=False, hide_parameters=True,
        connect_args={'connect_timeout': 15, 'prepare_threshold': None},
    )


async def dispose_engine():
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_engine.cache_clear()
