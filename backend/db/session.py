"""Services own transaction boundaries. Repositories flush, never commit."""
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from db.engine import get_engine


@asynccontextmanager
async def unit_of_work():
    factory = async_sessionmaker(get_engine(), expire_on_commit=False, autoflush=False)
    async with factory() as session:
        async with session.begin():
            yield session


async def request_session():
    """FastAPI dependency for read-only requests; writes use service unit_of_work."""
    factory = async_sessionmaker(get_engine(), expire_on_commit=False, autoflush=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
