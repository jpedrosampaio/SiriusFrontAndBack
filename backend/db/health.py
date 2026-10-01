import asyncio
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from db.engine import get_engine

router = APIRouter()


@router.get('/health/live')
async def liveness():
    return {'status':'ok'}


@router.get('/health/ready')
async def readiness():
    try:
        async with asyncio.timeout(5):
            async with get_engine().connect() as connection:
                await connection.execute(text('SELECT 1'))
    except Exception:
        raise HTTPException(503,'Database unavailable') from None
    return {'status':'ready'}
