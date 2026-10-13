"""Small transactional boundary for committed domain completions and expense writes."""
from zoneinfo import ZoneInfo
from sqlalchemy import select
from db.models.planning import Task, TaskInstance
from db.models.health import WorkoutLog
from db.models.studies import StudySession
from services.event_queue import enqueue, utc_now
from services.event_sources import candidate
from db.repositories.agent import AgentRepository
from ai.actions import Preferences
from event_contracts import Rule


async def emit_record(session,user,source,row):
    if source=='task_instance':
        task=await session.scalar(select(Task).where(Task.id==row.task_id,Task.user_id==user.id))
        if task is None:return
        item=candidate('task.completed',source,row.date,{'title':task.title[:200],'date':str(row.date)},'Conclusão registrada na ocorrência da tarefa.',row.id)
    elif source=='transaction':
        if row.type!='expense':return
        item=candidate('expense.created',source,row.date,{'date':str(row.date),'amount':str(row.amount),
            'category':row.category,'title':(row.description or row.category)[:200]},'Registro canônico próprio; nenhuma atividade foi alterada.',row.id)
    else:
        item=candidate('workout.completed' if source=='workout_log' else 'study.session.completed',source,row.date,
            {'date':str(row.date),'recorded_minutes':row.duration_minutes},'Registro canônico próprio; nenhuma atividade foi alterada.',row.id)
    prefs=Preferences.model_validate(await AgentRepository(session).preferences(user.id))
    rule=prefs.event_automation.rules.get(item.event_type,Rule())
    await enqueue(session,user.id,item,utc_now().astimezone(ZoneInfo(user.timezone)).date(),rule.frequency,rule.priority)


async def activity_event(session,user,kind,result):
    await session.flush()
    if kind=='task':
        row=await session.scalar(select(TaskInstance).where(TaskInstance.id==__import__('uuid').UUID(result['instance_id']),TaskInstance.user_id==user.id))
        source='task_instance'
    elif kind=='complete_session':
        row=await session.scalar(select(WorkoutLog).where(WorkoutLog.session_id==__import__('uuid').UUID(result['session_id']),WorkoutLog.user_id==user.id))
        source='workout_log'
    elif kind=='focus' and result.get('focus_id'):
        row=await session.scalar(select(StudySession).where(StudySession.id==__import__('uuid').UUID(result['focus_id']),StudySession.user_id==user.id))
        source='study_session'
    else:return False
    if row is None:return False
    await emit_record(session,user,source,row)
    return True
