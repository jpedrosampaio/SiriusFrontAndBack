import asyncio
from fastapi import APIRouter, HTTPException
from db.readiness import verify_database

router = APIRouter()


@router.get('/health/live')
async def liveness():
    return {'status':'ok'}


@router.get('/health/ready')
async def readiness():
    try:
        async with asyncio.timeout(5):
            await verify_database()
    except Exception:
        raise HTTPException(503,'Database unavailable') from None
    return {'status':'ready'}
