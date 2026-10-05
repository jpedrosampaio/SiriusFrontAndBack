"""Aggregate full histories in MongoDB, without silently truncating totals."""
import asyncio
from datetime import datetime, timedelta


async def aggregate_one(collection, query, fields):
    rows = await collection.aggregate([{'$match': query}, {'$group': {'_id': None, **fields}}]).to_list(1)
    return rows[0] if rows else {}
