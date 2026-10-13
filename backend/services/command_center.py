"""One factual home projection over the existing Life State / Global Planner."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from sqlalchemy import select, func, text
from db.session import unit_of_work
from db.models.studies import Flashcard, Notebook, ReviewEvent, StudyTopic
from db.models.studies import StudyProgram
from db.models.contests import ContestUpdate, ContestSource
from services.life_state import collect, preview
from services.finance_intelligence import FinanceEngine
from command_contracts import Why

LINKS={'preparation':'/studies','finance':'/finance','training':'/workouts','nutrition':'/nutrition',
    'tasks':'/tasks','calendar':'/calendar','habits':'/habits','goals':'/goals'}


def explanation(evidence, state, source, *, limitations=()):
    return Why(evidence=list(evidence)[:12],
        constraints=['Compromissos fixos preservados.','Disponibilidade declarada e fuso '+state.timezone+'.'],
        limitations=list(dict.fromkeys([*state.warnings,*limitations]))[:12],source=source).model_dump()


async def home(user_id, *, now=None):
    uid=UUID(str(user_id));instant=now or datetime.now(timezone.utc)
    async with unit_of_work() as session:
        await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        state=await collect(session,uid,now=instant)
        plan=preview(state,now=instant)
        local=instant.astimezone(ZoneInfo(state.timezone));minute=local.hour*60+local.minute
        domains={d.domain:d for d in state.domains}
        attention=[]
        due=await session.scalar(select(func.count()).select_from(Flashcard).join(Notebook,
            (Notebook.id==Flashcard.notebook_id)&(Notebook.user_id==uid)).where(Flashcard.user_id==uid,
            Flashcard.archived_at.is_(None),Notebook.archived_at.is_(None),Flashcard.next_review<state.date))
        if due:attention.append({'id':'overdue-reviews','title':f'{due} flashcard(s) com revisão vencida',
            'link':'/studies?view=revisoes','why':explanation([f'next_review anterior a {state.date}; cartões ativos da conta.'],state,'flashcards')})
        latest=select(ReviewEvent.topic_id,ReviewEvent.next_review,func.row_number().over(
            partition_by=ReviewEvent.topic_id,order_by=(ReviewEvent.reviewed_at.desc(),ReviewEvent.id.desc())).label('position'))
        latest=latest.where(ReviewEvent.user_id==uid,ReviewEvent.reviewed_at<=instant).subquery()
        topics_due=await session.scalar(select(func.count()).select_from(latest).join(StudyTopic,
            (StudyTopic.id==latest.c.topic_id)&(StudyTopic.user_id==uid)).join(Notebook,
            (Notebook.id==StudyTopic.notebook_id)&(Notebook.user_id==uid)).where(latest.c.position==1,
                latest.c.next_review<state.date,StudyTopic.archived_at.is_(None),Notebook.archived_at.is_(None)))
        if topics_due:attention.append({'id':'overdue-topic-reviews','title':f'{topics_due} tópico(s) com revisão vencida',
            'link':'/studies?view=revisoes','why':explanation(['Último evento de revisão de cada tópico ativo; next_review anterior a hoje.'],state,'questions-intelligence')})
        finance=await FinanceEngine().get_state(uid,months=2,now=instant,session=session)
        if not finance.complete:state.warnings.append('Consulta financeira limitada; alertas de contas podem estar incompletos.')
        for bill in finance.upcoming_bills:
            if bill.due_date and bill.due_date<=state.date+timedelta(days=7):
                attention.append({'id':bill.source_id,'title':bill.title,'link':'/finance',
                    'subtitle':f'R$ {bill.amount:.2f} · vencimento {bill.due_date}',
                    'why':explanation([f'Vencimento {bill.due_date}; fonte {bill.due_source}.'],state,'finance-intelligence',
                        limitations=['Obrigação registrada; não representa saldo bancário.'])})
        for c in domains['tasks'].candidates:
            if c.latest<state.date:
                attention.append({'id':c.id,'title':c.title,'link':c.link,
                    'why':explanation(c.reasons,state,'life-state/tasks')})
        updates=(await session.execute(select(ContestUpdate.id,ContestUpdate.title,ContestUpdate.program_id,
            ContestUpdate.detected_at,ContestUpdate.text_partial).join(ContestSource,
                (ContestSource.id==ContestUpdate.source_id)&(ContestSource.user_id==uid)).join(StudyProgram,
                (StudyProgram.id==ContestUpdate.program_id)&(StudyProgram.user_id==uid)).where(
                ContestUpdate.user_id==uid,ContestUpdate.official.is_(True),
                ContestUpdate.document_type.in_(('rectification','retificacao')),
                ContestUpdate.detected_at>=instant-timedelta(days=7),ContestUpdate.detected_at<=instant,
                ContestSource.deleted_at.is_(None),ContestSource.enabled.is_(True),
                StudyProgram.archived_at.is_(None),StudyProgram.status=='active').order_by(
                    ContestUpdate.detected_at.desc(),ContestUpdate.id).limit(5))).all()
        if len(updates)>4:state.warnings.append('Exibindo quatro retificações recentes; consulte as demais no Radar.')
        for update in updates[:4]:attention.append({'id':str(update.id),'title':update.title[:240],
            'link':f'/studies?program={update.program_id}&view=radar',
            'why':explanation([f'Retificação de fonte oficial detectada em {update.detected_at.isoformat()}.'],state,
                'edital-intelligence',limitations=['Confira o documento; o alerta não confirma mudanças não extraídas.'])})
        today=[]
        for d in state.domains:
            for c in d.constraints:
                today.append({'id':c.id,'title':c.title,'domain':d.domain,'link':LINKS[d.domain],
                    'start_minute':c.start_minute,'end_minute':c.end_minute,'confirmed':True,
                    'ambiguous':c.civil_time_ambiguous,'why':explanation([c.reason],state,'life-state/'+d.domain)})
        today.extend({'id':b['candidate_id'],'title':b['title'],'domain':b['domain'],'link':b['link'],
            'start_minute':b['start_minute'],'end_minute':b['end_minute'],'confirmed':False,
            'why':explanation(b['reasons'],state,'global-planner/1',limitations=['Horário sugerido; ainda não confirmado.'])}
            for b in plan['blocks'])
        today.sort(key=lambda b:(b['start_minute'],not b['confirmed'],b['id']))
        remaining=[b for b in today if b['end_minute']>minute]
        next_action=next(iter(remaining),None) if state.planning_safe else None
        # Display is bounded; the planner still received every temporal constraint.
        areas=[{'domain':d.domain,'link':LINKS[d.domain],
            'facts':{k:(v[:5] if isinstance(v,list) else v) for k,v in d.facts.items()},
            'candidate_count':len(d.candidates),'truncated':d.truncated} for d in state.domains]
        return {'version':'command-center/1','date':str(state.date),'timezone':state.timezone,
            'next_action':next_action,'today':today[:12],'today_count':len(today),
            'attention':attention[:8],'attention_count':len(attention),'areas':areas,
            'planning_safe':state.planning_safe,'warnings':state.warnings,
            'unscheduled_count':len(plan['unscheduled']), 'simulation_only':True}
