"""Optional seed for a local disposable DB. Never called by startup/deploy."""
import asyncio
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from db.engine import database_url,dispose_engine
from services.auth import AuthService


async def main():
    if database_url().host not in ('127.0.0.1','localhost','::1') or os.getenv('RENDER'):
        raise SystemExit('Development seed is restricted to a local database')
    email = input('Development email: ').strip()
    password = getpass.getpass('Development password: ')
    try:
        result = await AuthService().register(email=email,name='Sirius Dev',password=password)
        print('Created development user:',result['user']['user_id'])
    finally:
        await dispose_engine()


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
