"""Disposable-database smoke, run by test_postgres_startup with Mongo imports blocked."""
import asyncio
import importlib.abc
import os
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if sys.platform=='win32':asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class NoMongo(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'motor','pymongo','bson','gridfs'}:raise AssertionError('Mongo import attempted')


async def main():
    assert os.getenv('RUN_POSTGRES_TESTS')=='true','Only disposable PostgreSQL'
    assert not os.getenv('MONGO_URL') and not os.getenv('DB_NAME')
    sys.meta_path.insert(0,NoMongo())
    from sqlalchemy import event,text
    from httpx import AsyncClient,ASGITransport
    from db.engine import get_engine,dispose_engine
    from db.readiness import verify_database
    engine=get_engine()
    def no_ddl(conn,cursor,statement,parameters,context,many):
        assert statement.lstrip().split()[0].upper() not in {'CREATE','ALTER','DROP','TRUNCATE'},'Startup attempted DDL'
    event.listen(engine.sync_engine,'before_cursor_execute',no_ddl)
    async with engine.connect() as connection:
        assert (await connection.execute(text('SELECT count(*) FROM users'))).scalar()==0
    # Equivalent to concurrent namespace setup: all checks read existing migrations.
    await asyncio.gather(*(verify_database() for _ in range(4)))
    import server
    from unittest.mock import AsyncMock,patch
    assert not hasattr(server,'db') and not hasattr(server,'mongo_url')
    async with server.app.router.lifespan_context(server.app):
        async with AsyncClient(transport=ASGITransport(server.app),base_url='https://sirius.test') as client:
            assert (await client.get('/api/')).status_code==200
            assert (await client.get('/health/live')).status_code==200
            assert (await client.get('/health/ready')).status_code==200
            assert (await client.get('/api/auth/me')).status_code==401
            credentials={'email':'smoke@example.test','name':'Smoke','password':'disposable-password'}
            response=await client.post('/api/auth/register',json=credentials);assert response.status_code==200,response.text
            uid=response.json()['user']['user_id']
            for path in ('auth/me','stats/dashboard','tasks','habits','goals','transactions','notifications','telegram/status','achievements','ai/conversation',
                'study/areas','study/programs','study/notebooks','workout-plans','nutrition/meals','reports','ai/actions'):
                response=await client.get('/api/'+path);assert response.status_code==200,(path,response.status_code,response.text)
            task=await client.post('/api/tasks',json={'title':'Smoke task','date':'2026-10-05'});assert task.status_code==200,task.text
            transaction=await client.post('/api/transactions',json={'type':'expense','amount':'0.10','category':'food','date':'2026-10-05'})
            assert transaction.status_code==200,transaction.text
            area=await client.post('/api/study/areas',json={'name':'Study'});assert area.status_code==200,area.text
            program=await client.post('/api/study/programs',json={'area_id':area.json()['area_id'],'name':'Exam'});assert program.status_code==200,program.text
            notebook=await client.post('/api/study/notebooks',json={'area_id':area.json()['area_id'],'program_id':program.json()['program_id'],'name':'Law'})
            assert notebook.status_code==200,notebook.text
            plan=await client.post('/api/workout-plans',json={'name':'Smoke workout','exercises':[{'name':'Squat'}]});assert plan.status_code==200,plan.text
            meal=await client.post('/api/nutrition/meals',json={'name':'Lunch','meal_type':'lunch','date':'2026-10-05','foods':[{'name':'Rice','calories':100}]})
            assert meal.status_code==200,meal.text
            with patch.object(server.agent_runtime.agent,'respond',AsyncMock(return_value={'reply':'Smoke reply'})):
                chat=await client.post('/api/ai/chat',json={'message':'Hello','request_id':'smoke-chat-001'});assert chat.status_code==200,chat.text
            proposal=await server.agent_runtime.actions.propose(uid,'smoke-action',0,'record_expense',{'amount':'1.20','category':'food','date':'2026-10-05'},'Smoke request')
            confirmed=await client.post('/api/ai/actions/'+proposal['action_id']+'/confirm');assert confirmed.status_code==200,confirmed.text
            with patch('services.reports._llm',AsyncMock(return_value='Smoke insight; provider stub')):
                report=await client.post('/api/reports/generate',params={'report_type':'weekly'});assert report.status_code==200,report.text
            assert (await client.get('/api/sync/tasks/'+uid)).status_code==200
            assert (await client.post('/api/auth/logout')).status_code==200
            assert (await client.get('/api/auth/me')).status_code==401
            assert (await client.post('/api/auth/login',json=credentials)).status_code==200
    assert server.contest_watcher.task is None
    assert server.agent_runtime.automations.worker is None
    assert server.edital_jobs.task is None
    await dispose_engine()
    print('PASS: empty PostgreSQL, no Mongo imports/env, concurrent read-only readiness, lifespan, signup/login/dashboard, study/workout/nutrition, Agent confirmation and report; AI providers stubbed')


if __name__=='__main__':asyncio.run(main())
