"""Reproducible synthetic baseline. Only a named localhost disposable DB."""
import asyncio, json, os, pathlib, statistics, sys, time, gzip
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

repo = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / 'backend'))
from urllib.parse import urlsplit
connection = os.environ.get('HARDENING_TEST_DATABASE_URL', '')
parsed = urlsplit(connection)
if os.environ.get('RUN_POSTGRES_TESTS') != 'true' or parsed.scheme not in ('postgresql', 'postgres') or parsed.hostname not in ('localhost', '127.0.0.1', '::1') or not parsed.path.endswith('_test') or parsed.query or parsed.fragment or any(os.environ.get(key) for key in ('PGHOSTADDR','PGSERVICE','PGSERVICEFILE')):
    raise SystemExit('Refusing benchmark: RUN_POSTGRES_TESTS=true and a named localhost *_test database are required.')
os.environ['DATABASE_URL'] = connection
os.environ['DATABASE_URL_DIRECT'] = os.environ['DATABASE_URL']
from sqlalchemy import event
from db.session import unit_of_work
from db.engine import get_engine, dispose_engine
from db.repositories.identity import IdentityRepository
from db.models.planning import Task, CalendarEvent, Habit, Goal
from db.models.finance import FinancialTransaction, MonthlyBill
from db.models.studies import StudyArea, StudyProgram, Notebook, StudyPlan, StudyPlanEntry
from db.models.health import WorkoutPlan
from services.command_center import home

async def main():
    now = datetime.now(timezone.utc).replace(hour=13, minute=0, second=0, microsecond=0)
    day = now.date()
    async with unit_of_work() as s:
        user = await IdentityRepository(s).create(email=f'baseline-{uuid4()}@example.test', name='Synthetic baseline', password_hash='test-only')
        uid = user.id
        workout = WorkoutPlan(user_id=uid, name='Synthetic training', generated_by_ai=False, generation_parameters={})
        area = StudyArea(user_id=uid, name='Synthetic contest')
        s.add_all([workout, area]); await s.flush()
        program = StudyProgram(user_id=uid, area_id=area.id, name='Synthetic preparation')
        s.add(program); await s.flush()
        book = Notebook(user_id=uid, area_id=area.id, program_id=program.id, name='Synthetic discipline')
        plan = StudyPlan(user_id=uid, program_id=program.id, start_date=day, end_date=day, availability=[60]*7, block_minutes=30)
        s.add_all([book, plan]); await s.flush()
        s.add(StudyPlanEntry(user_id=uid, plan_id=plan.id, notebook_id=book.id, date=day, name='Synthetic review', minutes=30, kind='review', fixed=False))
        user.preferences = {'life_availability': {'weekdays': [[{'start_minute':480,'end_minute':1260}]]*7,
            'training_plan_id':str(workout.id),'training_weekdays':[day.weekday()], 'duration_estimates':{'training':45,'habits':5}}}
        s.add(CalendarEvent(user_id=uid, title='Synthetic fixed work', start_at=now-timedelta(hours=2), end_at=now+timedelta(hours=1)))
        s.add(Habit(user_id=uid, name='Synthetic habit'))
        s.add(Goal(user_id=uid, title='Synthetic goal', target_date=day, progress=25))
        s.add(MonthlyBill(user_id=uid, month=day.replace(day=1), description='Synthetic bill', amount=Decimal('10.01'), category='food'))
        s.add(FinancialTransaction(user_id=uid, date=day, type='expense', category='food', amount=Decimal('0.30')))
        s.add_all([Task(user_id=uid, date=day, title=f'Synthetic task {i}', duration_minutes=20, priority='medium') for i in range(10)])
    counts = []
    def count(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('SELECT'): counts.append((statement, parameters))
    engine = get_engine().sync_engine
    event.listen(engine, 'before_cursor_execute', count)
    results = []
    try:
        for size in (10,100):
            if size == 100:
                async with unit_of_work() as s:
                    s.add_all([Task(user_id=uid, date=day, title=f'Synthetic task {i}', duration_minutes=20, priority='medium') for i in range(10,100)])
            await home(uid, now=now) # Warmup excluded from timing and count.
            trials=[]
            for _ in range(5):
                counts.clear(); started=time.perf_counter(); data=await home(uid,now=now)
                trials.append({'selects':len(counts),'ms':round((time.perf_counter()-started)*1000,2),
                    'json_bytes':len(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode())})
            results.append({'tasks':size,'trials':trials,'median_ms':statistics.median(t['ms'] for t in trials)})
        plans=[]
        async with get_engine().connect() as connection:
            for statement,parameters in counts.copy():
                explained=(await connection.exec_driver_sql('EXPLAIN (FORMAT JSON) '+statement,parameters)).scalar_one()[0]['Plan']
                nodes=[]
                def walk(node):
                    nodes.append({k:node[k] for k in ('Node Type','Relation Name','Index Name','Plan Rows') if k in node})
                    for child in node.get('Plans',[]):walk(child)
                walk(explained)
                plans.append({'total_cost':explained['Total Cost'],'nodes':nodes})
    finally:
        event.remove(engine,'before_cursor_execute',count); await dispose_engine()
    build=repo/'frontend/build'
    bundles=[{'file':p.name,'bytes':p.stat().st_size,'gzip_bytes':len(gzip.compress(p.read_bytes()))} for p in (build/'static/js').glob('*.js')]
    print(json.dumps({'fixture':'synthetic cross-domain day; nutrition unknown, no provider calls',
        'database':'localhost disposable only','home':results,'query_plans':plans,'bundles':sorted(bundles,key=lambda b:b['bytes'],reverse=True)[:6]},ensure_ascii=True))

if sys.platform=='win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
