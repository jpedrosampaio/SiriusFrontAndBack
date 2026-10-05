from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.health import WorkoutPlan, WorkoutDay, PlanExercise, WorkoutSession, SessionExercise, WorkoutLog


class HealthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_plan(self, user_id, *, name, days=None, exercises=None, **values):
        plan = WorkoutPlan(user_id=user_id, name=name, **values)
        self.session.add(plan)
        await self.session.flush()
        await self.replace_days(plan,days,exercises)
        return plan

    async def replace_days(self,plan,days=None,exercises=None):
        from sqlalchemy import delete
        user_id=plan.user_id; name=plan.name
        await self.session.execute(delete(WorkoutDay).where(WorkoutDay.user_id==user_id,WorkoutDay.plan_id==plan.id))
        day_values = days or [{'day_name':name,'day_label':name,'week':1,'exercises':exercises or []}]
        for i, data in enumerate(day_values):
            day = WorkoutDay(user_id=user_id,plan_id=plan.id,position=i,week=int(data.get('week') or 1),
                name=data.get('day_name') or f'Dia {i+1}',label=data.get('day_label') or f'Dia {i+1}',
                split_label=data.get('split_label') or '',progression_focus=data.get('progression_focus') or '',progression_notes=data.get('progression_notes') or '')
            self.session.add(day)
            await self.session.flush()
            for j, ex in enumerate(data.get('exercises') or []):
                self.session.add(PlanExercise(user_id=user_id,day_id=day.id,position=j,
                    name=ex.get('name',''),sets=int(ex.get('sets') or 3),reps=str(ex.get('reps') or 12),
                    weight=str(ex.get('weight') or ''),rest_seconds=int(ex['rest_seconds']) if ex.get('rest_seconds') is not None else 60,
                    muscle_group=ex.get('muscle_group') or '',tutorial=ex.get('tutorial') or '',
                    video_url=ex.get('video_url') or '',notes=ex.get('notes') or ''))
        await self.session.flush()
        self.session.expire(plan,['days'])

    async def plan(self, user_id, plan_id):
        return await self.session.scalar(select(WorkoutPlan).where(WorkoutPlan.user_id == user_id,WorkoutPlan.id == plan_id,WorkoutPlan.archived_at.is_(None))
            .options(selectinload(WorkoutPlan.days).selectinload(WorkoutDay.exercises)))

    async def active_session(self, user_id):
        return await self.session.scalar(select(WorkoutSession).where(WorkoutSession.user_id == user_id,WorkoutSession.status == 'active'))

    async def workout_session(self, user_id, session_id):
        return await self.session.scalar(select(WorkoutSession).where(WorkoutSession.user_id == user_id,WorkoutSession.id == session_id)
            .options(selectinload(WorkoutSession.exercises).selectinload(SessionExercise.actual_sets)))

    def add_session(self, **values):
        row = WorkoutSession(**values)
        self.session.add(row)
        return row

    def add_log(self, **values):
        row = WorkoutLog(**values)
        self.session.add(row)
        return row
