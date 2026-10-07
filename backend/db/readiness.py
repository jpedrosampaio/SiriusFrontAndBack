"""Read-only schema readiness. Deploy migrations explicitly, never at boot."""
from functools import lru_cache
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from db.engine import get_engine


@lru_cache(maxsize=1)
def schema_heads():
    config=Config();config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'alembic'))
    return set(ScriptDirectory.from_config(config).get_heads())


async def verify_database():
    try:
        async with get_engine().connect() as connection:
            versions=set((await connection.execute(text('SELECT version_num FROM alembic_version'))).scalars())
    except SQLAlchemyError:
        raise RuntimeError('PostgreSQL unavailable or schema missing. Configure DATABASE_URL and run Alembic with DATABASE_URL_DIRECT before deployment.') from None
    if versions!=schema_heads():raise RuntimeError('PostgreSQL schema out of date. Run alembic upgrade head before deployment.')
    return {'database':'postgresql','schema':'ready'}
