from db.study_attempts import answered_attempt
from collections import defaultdict
from datetime import timedelta
from uuid import UUID
from fastapi import APIRouter,Request
from sqlalchemy import select,func,Date
from db.session import unit_of_work
from db.models.studies import Notebook,StudySession,Flashcard,StudyTask,StudyTaskCheck,QuestionAttempt
from db.models.exams import Exam,ExamAttempt
from services.auth_routes import account
from services.studies_catalog import notebooks
from services.study_activity_routes import streak_summary
from services.time import local_today
from services import study_cards,study_tasks

router=APIRouter(prefix='/study')


async def notebook_data(uid):
    async with unit_of_work() as session: return await notebooks(session,UUID(uid))


@router.get('/stats')
async def study_stats(request: Request):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        books=await notebooks(session,uid); time_by_name=defaultdict(int)
        for book in books: time_by_name[book['name']]+=book['total_study_time_minutes']
        total=await session.scalar(select(func.coalesce(func.sum(StudySession.duration_minutes),0)).where(StudySession.user_id==uid,StudySession.completed.is_(True)))
        daily=dict((await session.execute(select(StudySession.date,func.sum(StudySession.duration_minutes)).where(
            StudySession.user_id==uid,StudySession.completed.is_(True),StudySession.date>=today-timedelta(days=6),StudySession.date<=today)
            .group_by(StudySession.date))).all())
        streak=await streak_summary(session,uid,user['timezone'])
        cards,due,mastered=(await session.execute(select(func.count(),func.count().filter(Flashcard.next_review<=today),
            func.count().filter(Flashcard.interval_days>21)).select_from(Flashcard).join(Notebook,
                (Notebook.id==Flashcard.notebook_id)&(Notebook.user_id==Flashcard.user_id)).where(
                    Flashcard.user_id==uid,Flashcard.archived_at.is_(None),Notebook.archived_at.is_(None)))).one()
        quiz_count,score=(await session.execute(select(func.count(),func.avg(ExamAttempt.score)).select_from(ExamAttempt).join(Exam,
            (Exam.id==ExamAttempt.exam_id)&(Exam.user_id==ExamAttempt.user_id)).where(ExamAttempt.user_id==uid,Exam.kind=='quiz'))).one()
        done=select(StudyTaskCheck.id).where(StudyTaskCheck.user_id==uid,StudyTaskCheck.task_id==StudyTask.id).exists()
        tasks=await session.scalar(select(func.count()).select_from(StudyTask).where(StudyTask.user_id==uid,StudyTask.archived_at.is_(None),StudyTask.recurrence=='once',done))
        return {'total_study_time_minutes':total,'total_study_time_hours':round(total/60,1),'notebooks_count':len(books),
            'time_by_notebook':dict(time_by_name),'daily_time_last_7_days':{day.isoformat():minutes for day,minutes in daily.items()},
            'streak':{'current':streak['current_streak'],'best':streak['best_streak'],'total_days':streak['total_study_days']},
            'flashcards':{'total':cards,'due_today':due,'mastered':mastered},'quizzes':{'total_attempts':quiz_count,'average_score':round(score or 0,1)},
            'tasks_completed':tasks}


@router.get('/overall-stats')
async def overall(request: Request):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone']); start=today-timedelta(days=6)
    async with unit_of_work() as session:
        books=await notebooks(session,uid)
        focus=(await session.execute(select(StudySession.date,func.sum(StudySession.duration_minutes),func.count()).where(
            StudySession.user_id==uid,StudySession.source=='focus',StudySession.completed.is_(True),StudySession.date>=start,StudySession.date<=today)
            .group_by(StudySession.date))).all()
        day=func.timezone(user['timezone'],QuestionAttempt.answered_at).cast(Date)
        questions=(await session.execute(select(day,func.sum(QuestionAttempt.total),func.sum(QuestionAttempt.correct)).where(
            QuestionAttempt.user_id==uid,day>=start,day<=today,answered_attempt()).group_by(day))).all()
        by_focus={d:(minutes,count) for d,minutes,count in focus}; by_question={d:(total,correct) for d,total,correct in questions}
        focus_daily=[]; question_daily=[]
        for offset in range(7):
            d=start+timedelta(days=offset); minutes,count=by_focus.get(d,(0,0)); total,correct=by_question.get(d,(0,0))
            base={'day':d.strftime('%a'),'date':d.isoformat()}
            focus_daily.append({**base,'minutos':minutes,'sessoes':count})
            question_daily.append({**base,'questoes':total,'acertos':correct,'acuracia':round(correct/total*100,1) if total else 0})
        disciplines=[]; total_time=total_questions=total_correct=0
        for book in books:
            minutes=book['total_study_time_minutes']; total=book['total_questions']; correct=book['correct_questions']
            total_time+=minutes; total_questions+=total; total_correct+=correct
            if minutes or total: disciplines.append({'nome':book['name'],'tempo_horas':round(minutes/60,1),'questoes':total,
                'acertos':correct,'acuracia':round(correct/total*100,1) if total else 0,'color':book['color']})
        return {'disciplinas':sorted(disciplines,key=lambda d:d['tempo_horas'],reverse=True),'focus_daily':focus_daily,'question_daily':question_daily,
            'totals':{'tempo_total_horas':round(total_time/60,1),'questoes_total':total_questions,'acertos_total':total_correct,
                'acuracia_geral':round(total_correct/total_questions*100,1) if total_questions else 0,'disciplinas_ativas':len(disciplines)}}


@router.post('/ai-suggestions')
async def suggestions(request: Request):
    user=await account(request); stats=await study_stats(request); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        pending=await study_tasks.rows(session,UUID(user['user_id']),today,completed=False,limit=50)
        books=await notebooks(session,UUID(user['user_id']))
    least=sorted(books,key=lambda b:b['total_study_time_minutes'])[:3]
    prompt=f'''Com base nos dados de estudo, forneça sugestões personalizadas:
Tempo total: {stats['total_study_time_hours']} horas. Streak: {stats['streak']['current']} dias.
Flashcards para revisar: {stats['flashcards']['due_today']}. Tarefas pendentes: {len(pending)}.
Média nos quizzes: {stats['quizzes']['average_score']}%.
Matérias menos estudadas: {[(b['name'],b['total_study_time_minutes']) for b in least]}.
Tarefas e prazos: {[(t['title'],t['deadline']) for t in pending[:5]]}.
Forneça análise breve, 3-5 sugestões práticas, matérias que precisam de atenção, dicas de repetição espaçada e motivação. Responda de forma concisa em português.'''
    response=await study_cards._llm(prompt,session_id=user['user_id'],system_message='Você é um coach de estudos especializado em aprendizado eficiente e repetição espaçada. Seja motivador e prático.',
        user_id=user['user_id'],task='study_explanation')
    return {'suggestions':response,'due_flashcards_count':stats['flashcards']['due_today'],'pending_tasks_count':len(pending),
        'least_studied_notebooks':[b['name'] for b in least]}
