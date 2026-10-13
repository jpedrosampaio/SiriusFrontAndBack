"""Progressive portability with explicit fields, SQL ownership and bounded pages."""
import csv
import json
from datetime import date
from decimal import Decimal
from io import StringIO, BytesIO
from uuid import UUID
from xml.sax.saxutils import escape
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, func, Text, text
from db.session import unit_of_work
from db.models.finance import FinancialTransaction
from db.models.planning import Task, CalendarEvent, Habit, Goal
from db.models.health import WorkoutLog, Meal
from db.models.studies import StudySession, StudyTopic, QuestionAttempt
from db.models.agent import Memory, Conversation, Message
from db.models.files import FileRecord, EditalAnalysis
from services.auth_routes import account
from services.command_center import home

router=APIRouter(prefix='/command/export')
DATASETS={
    'finance':(FinancialTransaction,('description','type','category','amount','date'),'date'),
    'tasks':(Task,('title','description','date','priority','recurrence','duration_minutes','scheduled_time'),'date'),
    'calendar':(CalendarEvent,('title','start_at','end_at','source_type','source_id','details'),None),
    'habits':(Habit,('name','description','color','created_at'),None),
    'goals':(Goal,('title','progress','created_at'),None),
    'workouts':(WorkoutLog,('name','date','duration_minutes','completed','plan_id','session_id','notes'),'date'),
    'nutrition':(Meal,('name','date','meal_type','reported_calories','reported_protein','reported_carbs','reported_fat'),'date'),
    'study':(StudySession,('date','notebook_id','topic_id','duration_minutes','completed','source','notes'),'date'),
    'topics':(StudyTopic,('notebook_id','topic_key','name','evidence'),None),
    'attempts':(QuestionAttempt,('question_id','notebook_id','topic_id','answered_at','correct','total','duration_seconds','error_cause'),None),
    'memory':(Memory,('kind','content','provenance','created_at','updated_at'),None),
    'conversations':(Conversation,('title','created_at','updated_at'),None),
    'messages':(Message,('conversation_id','sequence','role','content','created_at'),None),
    'materials':(FileRecord,('filename','mime_type','size_bytes','created_at'),None),
    'editais':(EditalAnalysis,('filename','status','analysis_version','structured_payload','created_at'),None),
}


def wire(value):
    if isinstance(value,Decimal):return str(value)
    if isinstance(value,UUID):return str(value)
    if hasattr(value,'isoformat'):return value.isoformat()
    if isinstance(value,dict):return {k:wire(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [wire(v) for v in value]
    return value


def csv_cell(value):
    if isinstance(value,(dict,list)):value=json.dumps(value,ensure_ascii=False)
    if value is None:return ''
    value=str(value)
    # CSV is data even when opened by spreadsheet programs.
    return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r','\n')) or value.startswith(('\t','\r','\n')) else value


@router.get('/{dataset}/{format}')
async def export(request:Request,dataset:str,format:str,cursor:UUID|None=None,
                 limit:int=Query(100,ge=1,le=200),start:date|None=None,end:date|None=None):
    user=await account(request);uid=UUID(user['user_id'])
    if dataset not in DATASETS:raise HTTPException(422,'Conjunto de dados inválido.')
    if format not in ('json','csv'):raise HTTPException(422,'Formato deve ser json ou csv.')
    if start and end and (end<start or (end-start).days>366):raise HTTPException(422,'Período inválido ou superior a 366 dias.')
    model,fields,day_column=DATASETS[dataset]
    if (start or end) and not day_column:raise HTTPException(422,'Este conjunto usa páginas por ID; não aceita filtro diário.')
    statement=select(model.id,*(getattr(model,f) for f in fields)).where(model.user_id==uid)
    if model is Memory:statement=statement.where(Memory.blocked.is_(False))
    if model is Message:statement=statement.where(Message.role.in_(('user','assistant')))
    if cursor:statement=statement.where(model.id>cursor)
    if start:statement=statement.where(getattr(model,day_column)>=start)
    if end:statement=statement.where(getattr(model,day_column)<=end)
    async with unit_of_work() as session:
        await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        args=['id',model.id]
        for field in fields:args.extend((field,getattr(model,field)))
        sizes=statement.with_only_columns(model.id,func.octet_length(func.jsonb_build_object(*args).cast(Text)))
        page=(await session.execute(sizes.order_by(model.id).limit(limit+1))).all()
        if sum(r[1] for r in page[:limit])>1_800_000:
            raise HTTPException(413,'Página muito grande. Reduza o limite para exportar sem omitir registros.')
        ids=[r[0] for r in page[:limit]]
        rows=(await session.execute(statement.where(model.id.in_(ids)).order_by(model.id))).all() if ids else []
    records=[wire(dict(zip(('id',*fields),row))) for row in rows[:limit]]
    payload={'version':'sirius-export/1','dataset':dataset,'records':records,
        'next_cursor':str(page[limit-1][0]) if len(page)>limit else None,
        'scope':'authenticated_owner','order':'id ascending','unknown_values':'null',
        'excluded':'credentials, storage keys, provider prompts, hidden context and other users'}
    encoded=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    if len(encoded)>2_000_000:raise HTTPException(413,'Página muito grande. Reduza o limite para exportar.')
    headers={'Content-Disposition':f'attachment; filename="sirius_{dataset}.{format}"','Cache-Control':'no-store',
        'X-Export-Next-Cursor':payload['next_cursor'] or '', 'X-Export-Version':'sirius-export/1'}
    if format=='json':return Response(encoded,media_type='application/json',headers=headers)
    output=StringIO(newline='');writer=csv.writer(output);writer.writerow(('id',*fields))
    writer.writerows([csv_cell(record.get(f)) for f in ('id',*fields)] for record in records)
    return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers=headers)


@router.get('/daily-report.pdf')
async def daily_pdf(request:Request):
    user=await account(request);report=await home(user['user_id'])
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    buf=BytesIO();styles=getSampleStyleSheet();elements=[]
    def line(value,style='Normal'):elements.append(Paragraph(escape(str(value)),styles[style]));elements.append(Spacer(1,8))
    line('Sirius - relatório do dia','Title');line(report['date']+' · '+report['timezone'])
    line('Dados registrados e sugestões determinísticas. Sugestões não são compromissos confirmados.')
    line('Próxima ação','Heading2');line((report['next_action'] or {}).get('title','Sem ação alocada com segurança.'))
    line('Hoje','Heading2')
    for row in report['today']:line(f"{row['start_minute']//60:02}:{row['start_minute']%60:02} - {row['title']} ({'confirmado' if row['confirmed'] else 'sugestão'})")
    line('Atenção','Heading2')
    for row in report['attention']:line(row['title']+' '+(row.get('subtitle') or ''))
    line('Limites','Heading2')
    for value in report['warnings']:line(value)
    line(f"Exibição limitada: {len(report['today'])}/{report['today_count']} atividades; {len(report['attention'])}/{report['attention_count']} alertas.")
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColorRGB(.4,.4,.4)
        canvas.drawString(72,35,'Sirius - dados da conta autenticada; sugestões não aplicadas.')
        canvas.drawRightString(A4[0]-72,35,str(canvas.getPageNumber()));canvas.restoreState()
    SimpleDocTemplate(buf,pagesize=A4).build(elements,onFirstPage=footer,onLaterPages=footer)
    return Response(buf.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="sirius_dia.pdf"','Cache-Control':'no-store'})
