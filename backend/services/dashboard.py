"""Dashboard aggregates over the same SQL facts used by domain routes."""
from datetime import date,timedelta
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select,func
from db.models.identity import User
from db.models.planning import Habit,HabitCheck,Goal
from db.models.finance import FinancialTransaction
from db.models.studies import StudySession,Notebook,Flashcard,QuestionAttempt
from db.models.exams import Exam,ExamAttempt
from db.models.health import WorkoutLog
from db.repositories.planning import PlanningRepository
from db.session import unit_of_work
from services.auth_routes import account
from services.time import local_today
from services.nutrition import period
from services.study_activity_routes import streak_summary
from cross_module_rules import suggestions_from_snapshot

router=APIRouter()


def accuracy(correct,total):return round(correct/total*100,1) if total else 0


async def dashboard_snapshot(user_id,today=None):
    uid=UUID(str(user_id))
    async with unit_of_work() as session:
        user=await session.get(User,uid)
        if user is None:raise HTTPException(404,'User not found')
        day=date.fromisoformat(today) if isinstance(today,str) else today or local_today(user.timezone)
        month=day.replace(day=1);next_month=(month.replace(day=28)+timedelta(days=4)).replace(day=1)
        pairs=await PlanningRepository(session).tasks_on_date(uid,day)
        habits,done=(await session.execute(select(func.count(),func.count(HabitCheck.id)).select_from(Habit).outerjoin(HabitCheck,
            (HabitCheck.habit_id==Habit.id)&(HabitCheck.user_id==Habit.user_id)&(HabitCheck.date==day)).where(Habit.user_id==uid,Habit.archived_at.is_(None)))).one()
        finances=dict((await session.execute(select(FinancialTransaction.type,func.sum(FinancialTransaction.amount)).where(
            FinancialTransaction.user_id==uid,FinancialTransaction.date>=month,FinancialTransaction.date<next_month).group_by(FinancialTransaction.type))).all())
        income=finances.get('income',Decimal(0));expenses=finances.get('expense',Decimal(0))
        goals,progress=(await session.execute(select(func.count(),func.coalesce(func.avg(Goal.progress),0)).where(Goal.user_id==uid,Goal.archived_at.is_(None)))).one()
        workouts,minutes,calories,xp=(await session.execute(select(func.count(),*[func.coalesce(func.sum(field),0) for field in
            (WorkoutLog.duration_minutes,WorkoutLog.calories,WorkoutLog.xp_earned)]).where(WorkoutLog.user_id==uid,WorkoutLog.completed.is_(True),
            WorkoutLog.date.between(day-timedelta(days=6),day)))).one()
        meals,water,nutrition_goal=await period(session,uid,day,day);nutrition=meals.get(day,{})
        study=await session.scalar(select(func.coalesce(func.sum(StudySession.duration_minutes),0)).where(
            StudySession.user_id==uid,StudySession.completed.is_(True),StudySession.date==day))
        streak=await streak_summary(session,uid,user.timezone)
        cards,due=(await session.execute(select(func.count(),func.count().filter(Flashcard.next_review<=day)).select_from(Flashcard).join(Notebook,
            (Notebook.id==Flashcard.notebook_id)&(Notebook.user_id==Flashcard.user_id)).where(Flashcard.user_id==uid,Flashcard.archived_at.is_(None),Notebook.archived_at.is_(None)))).one()
        notebooks=await session.scalar(select(func.count()).select_from(Notebook).where(Notebook.user_id==uid,Notebook.archived_at.is_(None)))
        simulations=await session.scalar(select(func.count()).select_from(Exam).where(Exam.user_id==uid,Exam.kind=='simulado',Exam.archived_at.is_(None)))
        attempts,average,best,correct,total=(await session.execute(select(func.count(),func.avg(ExamAttempt.score),func.max(ExamAttempt.score),
            func.coalesce(func.sum(ExamAttempt.result_details['correct_count'].as_integer()),0),func.coalesce(func.sum(ExamAttempt.result_details['total_questions'].as_integer()),0))
            .select_from(ExamAttempt).join(Exam,(Exam.id==ExamAttempt.exam_id)&(Exam.user_id==ExamAttempt.user_id)).where(ExamAttempt.user_id==uid,Exam.kind=='simulado'))).one()
        answered,right=(await session.execute(select(func.coalesce(func.sum(QuestionAttempt.total),0),func.coalesce(func.sum(QuestionAttempt.correct),0))
            .where(QuestionAttempt.user_id==uid,func.coalesce(QuestionAttempt.evidence['answered'].as_boolean(),True)))).one()
        return {'user':{'name':user.name,'xp':user.xp,'rank':user.rank,'picture':user.picture},
            'tasks_today':len(pairs),'tasks_completed_today':sum(bool(instance and instance.completed) for task,instance in pairs),
            'habits_total':habits,'habits_completed_today':done,'income':income,'expenses':expenses,'balance':income-expenses,
            'goals_total':goals,'goals_avg_progress':progress,
            'workout_stats':{'workouts_this_week':workouts,'total_duration_minutes':minutes,'total_calories_burned':calories,'total_xp_earned':xp},
            'nutrition_stats':{'calories_consumed':nutrition.get('calories',0),'calories_goal':nutrition_goal['daily_calories'],
                'protein_consumed':round(nutrition.get('protein',0),1),'protein_goal':nutrition_goal['daily_protein'],
                'water_consumed_ml':water.get(day,0),'water_goal_ml':nutrition_goal['water_goal_ml'],'meals_count':nutrition.get('meals_count',0)},
            'study_stats':{'study_time_today_minutes':study,'current_streak':streak['current_streak'],'longest_streak':streak['best_streak'],
                'flashcards_due':due,'total_flashcards':cards,'notebooks_count':notebooks},
            'simulado_stats':{'total_simulados':simulations,'total_attempts':attempts,'average_score':round(average or 0,1),'best_score':round(best or 0,1),
                'total_questions_answered':total,'total_correct':correct,'accuracy_rate':accuracy(correct,total)},
            'question_overview':{'total_answered':answered,'total_correct':right,'accuracy_rate':accuracy(right,answered)}}


@router.get('/stats/dashboard')
async def stats(request: Request):
    user=await account(request);result=await dashboard_snapshot(user['user_id'])
    result['suggestions']=suggestions_from_snapshot(result)
    return jsonable_encoder(result)


@router.get('/suggestions/cross-module')
async def suggestions(request: Request):
    user=await account(request)
    return {'suggestions':suggestions_from_snapshot(await dashboard_snapshot(user['user_id']))}
