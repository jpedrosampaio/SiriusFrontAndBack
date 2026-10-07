"""Persisted report snapshots from SQL metrics, with AI outside transactions."""
import json
from datetime import date
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from db.models.reports import Report
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account
from services.time import local_today
from report_metrics import report_window,period_metrics

router=APIRouter()
_llm=None
METRICS=('tasks','tasks_completed','habits','total_habits_completions','income','expenses','goals','goals_progress','goal_checks',
    'study_minutes','questions_answered','questions_correct','workouts','workout_minutes','meals','calories','protein','water_ml','definitions')


def configure(llm):
    global _llm
    _llm=llm


def report_json(row):
    data={key:getattr(row,key) for key in METRICS}
    data.update(start_date=row.start_date.isoformat(),end_date=row.end_date.isoformat())
    return jsonable_encoder({'report_id':row.id,'user_id':row.user_id,'type':row.type,'period':f'{row.start_date} a {row.end_date}',
        'data':data,'insights':row.insights,'created_at':row.created_at})


async def read_report(uid,identity):
    async with unit_of_work() as session:
        row=await session.scalar(select(Report).where(Report.user_id==uid,Report.id==identity))
        if row is None:raise HTTPException(404,'Report not found')
        return report_json(row)


@router.get('/reports')
async def reports(request: Request,type: str | None=None):
    user=await account(request)
    async with unit_of_work() as session:
        query=select(Report).where(Report.user_id==UUID(user['user_id']))
        if type:query=query.where(Report.type==type)
        return [report_json(row) for row in (await session.scalars(query.order_by(Report.created_at.desc()).limit(100))).all()]


@router.post('/reports/generate')
async def generate_report(request: Request,report_type: str,period: str='',start: str | None=None,end: str | None=None):
    user=await account(request)
    try:first,last=report_window(report_type,local_today(user['timezone']).isoformat(),start,end)
    except ValueError as exc:raise HTTPException(422,str(exc))
    data=await period_metrics(user['user_id'],first,last)
    prompt=f"Interprete em português estas métricas calculadas do relatório {report_type}, período {first} a {last}. Não invente totais nem tendências sem comparação. Respeite as definições e diferencie ausência de registros de ausência de atividade. Dados: {json.dumps(data,ensure_ascii=False,default=str)}"
    insights=await _llm(prompt,f"report_{user['user_id']}",user_id=user['user_id'],task='report_analysis')
    async def apply(session,owner):
        row=Report(user_id=owner.id,type=report_type,start_date=date.fromisoformat(first),end_date=date.fromisoformat(last),insights=insights,
            **{key:data[key] for key in METRICS})
        session.add(row);await session.flush();return report_json(row)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['report',report_type,first,last],apply)


@router.get('/reports/{report_id}/download')
async def download_report(report_id: UUID, request: Request):
    from fastapi.responses import StreamingResponse
    import io
    user = await account(request)
    report = await read_report(UUID(user['user_id']), report_id)
    content = f"SIRIUS - RELATÓRIO {report['type'].upper()}\nPeríodo: {report['period']}\nGerado em: {report['created_at']}\n\n{'=' * 60}\nDADOS DO PERÍODO\n{'=' * 60}\n\nTarefas: {report['data']['tasks_completed']}/{report['data']['tasks']}\nHábitos: {report['data']['total_habits_completions']} completações\nReceitas: R$ {report['data']['income']:.2f}\nDespesas: R$ {report['data']['expenses']:.2f}\nMetas: {report['data']['goals']} total\nProgresso Médio: {report['data']['goals_progress']:.1f}%\n\n{'=' * 60}\nINSIGHTS E SUGESTÕES\n{'=' * 60}\n\n{report['insights']}\n"
    buffer = io.BytesIO(content.encode('utf-8'))
    buffer.seek(0)
    return StreamingResponse(buffer, media_type='text/plain', headers={'Content-Disposition': f'attachment; filename=sirius_relatorio_{report_id}.txt'})
