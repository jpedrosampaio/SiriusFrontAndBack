"""Literal SQL search, owned joins and independent bounded keyset pages."""
from uuid import UUID
from urllib.parse import urlencode
from fastapi import APIRouter, Request, Query, HTTPException
from sqlalchemy import select, or_, func, case
from db.session import unit_of_work
from db.models.finance import FinancialTransaction
from db.models.planning import Task, Habit, Goal, CalendarEvent
from db.models.health import WorkoutPlan, PlanExercise, WorkoutDay, WorkoutLog, Meal
from db.models.studies import StudyNote, Notebook, StudyProgram, StudyTarget, StudyTopic, QuestionAttempt, ReviewEvent
from db.models.exams import Question
from db.models.files import FileRecord, EditalAnalysis, RagSource, RagChunk
from ai.rag import terms
from db.models.agent import Conversation, Message
from services.auth_routes import account
from command_contracts import SearchItem, SearchGroup, SearchResults

router = APIRouter()
DOMAINS = ('tasks', 'finance', 'habits', 'goals', 'calendar', 'workouts', 'exercises',
    'training_history', 'nutrition', 'notes', 'programs', 'targets', 'notebooks', 'topics',
    'questions', 'errors', 'reviews', 'materials', 'editais', 'conversations')


async def search_owned(uid, needle, *, domain=None, cursor=None, limit=5):
    groups = []
    def match(*columns):
        return or_(*(column.icontains(needle, autoescape=True) for column in columns))
    def study_link(book=None, **params):
        if book: params['notebook'] = str(book)
        return '/studies?' + urlencode(params)
    async with unit_of_work() as session:
        async def group(name, model, title, subtitle, link, kind, *, extra=(), joins=(), filters=(), searchable=(), display=None, indexed=None):
            if domain and domain != name: return
            predicate=match(title,*searchable)
            if indexed is not None:predicate=or_(predicate,indexed)
            statement = select(model.id, func.left(title,240), *extra).where(model.user_id == uid, predicate, *filters)
            for other, clause in joins: statement = statement.join(other, clause)
            if hasattr(model, 'archived_at'): statement = statement.where(model.archived_at.is_(None))
            if cursor: statement = statement.where(model.id > cursor)
            rows = (await session.execute(statement.order_by(model.id).limit(limit + 1))).all()
            values = [SearchItem(id=r[0], type=kind, domain=name, title=display(r) if display else (r[1] or '')[:240],
                subtitle=subtitle(r) if callable(subtitle) else subtitle,
                link=link(r) if callable(link) else link) for r in rows[:limit]]
            groups.append(SearchGroup(domain=name, results=values,
                next_cursor=rows[limit-1][0] if len(rows) > limit else None))
        await group('tasks', Task, Task.title, 'Tarefa registrada', '/tasks', 'task')
        await group('finance', FinancialTransaction, func.coalesce(FinancialTransaction.description, FinancialTransaction.category),
            lambda r: f'{r[2]} · R$ {r[3]:.2f} · {r[4]}', '/finance', 'transaction',
            extra=(FinancialTransaction.category, FinancialTransaction.amount, FinancialTransaction.date),
            searchable=(FinancialTransaction.category,),display=lambda r:f'{r[1]} - R$ {r[3]:.2f}')
        await group('habits', Habit, Habit.name, 'Hábito', '/habits', 'habit')
        await group('goals', Goal, Goal.title, 'Meta registrada', '/goals', 'goal')
        await group('calendar', CalendarEvent, CalendarEvent.title, 'Compromisso', '/calendar', 'calendar_commitments')
        await group('workouts', WorkoutPlan, WorkoutPlan.name, 'Plano de treino', '/workouts', 'workout_plan',
            searchable=(WorkoutPlan.description,))
        await group('exercises', PlanExercise, PlanExercise.name, 'Exercício do plano',
            lambda r: '/workouts?'+urlencode({'exercise':str(r[0]),'plan':str(r[2])}), 'exercise',
            extra=(WorkoutDay.plan_id,), joins=((WorkoutDay,(WorkoutDay.id==PlanExercise.day_id)&(WorkoutDay.user_id==uid)),
                (WorkoutPlan,(WorkoutPlan.id==WorkoutDay.plan_id)&(WorkoutPlan.user_id==uid)&WorkoutPlan.archived_at.is_(None))))
        await group('training_history', WorkoutLog, WorkoutLog.name, 'Histórico de treino', '/workouts', 'workout_log')
        await group('nutrition', Meal, Meal.name, 'Refeição registrada', '/nutrition', 'meal')
        book_join=lambda column: ((Notebook,(Notebook.id==column)&(Notebook.user_id==uid)&Notebook.archived_at.is_(None)),)
        await group('notes', StudyNote, StudyNote.title, 'Nota de estudo', lambda r: study_link(r[2],view='estudar'),
            'note', extra=(StudyNote.notebook_id,), joins=book_join(StudyNote.notebook_id),searchable=(StudyNote.content,))
        await group('programs', StudyProgram, StudyProgram.name, 'Programa',lambda r: study_link(program=str(r[0])),
            'study_programs',searchable=(StudyProgram.description,))
        await group('targets', StudyTarget, StudyTarget.name, 'Preparação',lambda r: study_link(program=str(r[2])),
            'study_targets',extra=(StudyTarget.program_id,),joins=((StudyProgram,(StudyProgram.id==StudyTarget.program_id)&
                (StudyProgram.user_id==uid)&StudyProgram.archived_at.is_(None)),),
            searchable=(StudyTarget.institution,StudyTarget.board,StudyTarget.position))
        await group('notebooks', Notebook, Notebook.name, 'Matéria',lambda r:study_link(r[0],view='estudar'),
            'notebooks',searchable=(Notebook.description,))
        await group('topics',StudyTopic,StudyTopic.name,'Tópico',lambda r:study_link(r[2],topic=r[3],view='estudar'),
            'topic',extra=(StudyTopic.notebook_id,StudyTopic.topic_key),joins=book_join(StudyTopic.notebook_id))
        await group('questions',Question,Question.statement,'Questão',
            lambda r:study_link(r[2],question=str(r[0]),view='questoes'),'question',extra=(Question.notebook_id,),
            filters=(Question.notebook_id.is_(None)|select(Notebook.id).where(Notebook.id==Question.notebook_id,
                Notebook.user_id==uid,Notebook.archived_at.is_(None)).exists(),))
        error_label=case({'knowledge_gap':'Lacuna de conhecimento','concept_confusion':'Confusão de conceitos',
            'interpretation':'Interpretação','attention':'Desatenção','calculation':'Cálculo','memory':'Memória',
            'time_management':'Gestão do tempo'},value=QuestionAttempt.error_cause,else_=QuestionAttempt.error_cause)
        error_statement=select(Question.id).where(Question.user_id==uid,Question.id==QuestionAttempt.question_id,
            match(Question.statement)).correlate(QuestionAttempt).exists()
        await group('errors',QuestionAttempt,func.coalesce(error_label,'Erro registrado'),'Erro registrado',
            lambda r:study_link(r[2],view='questoes'),'question_error',extra=(QuestionAttempt.notebook_id,),
            filters=(QuestionAttempt.correct<QuestionAttempt.total,),indexed=error_statement)
        await group('reviews',ReviewEvent,StudyTopic.name,'Revisão registrada',
            lambda r:study_link(r[2],topic=r[3],view='revisoes'),'review',extra=(StudyTopic.notebook_id,StudyTopic.topic_key),
            joins=((StudyTopic,(StudyTopic.id==ReviewEvent.topic_id)&(StudyTopic.user_id==uid)&StudyTopic.archived_at.is_(None)),
                *book_join(StudyTopic.notebook_id)))
        tokens=sorted(terms(needle))[:12]
        def indexed(model,field):
            if not tokens:return None
            return select(RagChunk.id).join(RagSource,(RagSource.id==RagChunk.source_id)&(RagSource.user_id==uid)).where(
                RagChunk.user_id==uid,field==model.id,RagChunk.terms.contains(tokens)).correlate(model).exists()
        await group('materials',FileRecord,FileRecord.filename,'Material enviado · busca lexical quando indexado',
            lambda r:study_link(attachment=str(r[0]),view='library'),'material',indexed=indexed(FileRecord,RagSource.file_id))
        await group('editais',EditalAnalysis,EditalAnalysis.filename,'Análise de edital',
            lambda r:study_link(analysis=str(r[0]),view='library'),'edital',indexed=indexed(EditalAnalysis,RagSource.analysis_id))
        # EXISTS searches content without copying the messages or conversation history.
        if not domain or domain=='conversations':
            messages=select(Message.id).where(Message.user_id==uid,Message.conversation_id==Conversation.id,
                Message.role.in_(('user','assistant')),match(Message.content)).correlate(Conversation).exists()
            statement=select(Conversation.id,Conversation.title).where(Conversation.user_id==uid,
                or_(match(Conversation.title),messages))
            if cursor:statement=statement.where(Conversation.id>cursor)
            rows=(await session.execute(statement.order_by(Conversation.id).limit(limit+1))).all()
            groups.append(SearchGroup(domain='conversations',results=[SearchItem(id=r.id,type='conversation',
                domain='conversations',title=r.title[:240],subtitle='Conversa privada',
                link='/chat?'+urlencode({'conversation':str(r.id)})) for r in rows[:limit]],
                next_cursor=rows[limit-1].id if len(rows)>limit else None))
    return SearchResults(results=[r for g in groups for r in g.results],groups=groups,query=needle)


@router.get('/search/global', response_model=SearchResults)
async def search(request:Request,q:str=Query('',max_length=100),domain:str|None=None,
                 cursor:UUID|None=None,limit:int=Query(5,ge=1,le=10)):
    user=await account(request);needle=q.strip()
    if domain is not None and domain not in DOMAINS:raise HTTPException(422,'Domínio de busca inválido.')
    if cursor and not domain:raise HTTPException(422,'Escolha um domínio para continuar a página.')
    if len(needle)<2:return SearchResults(results=[],groups=[],query=needle)
    return await search_owned(UUID(user['user_id']),needle,domain=domain,cursor=cursor,limit=limit)
