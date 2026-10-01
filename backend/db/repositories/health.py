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
        day_values = days or [{'day_name':name,'day_label':name,'week':1,'exercises':exercises or []}]
        for i, data in enumerate(day_values):
            day = WorkoutDay(user_id=user_id,plan_id=plan.id,position=i,week=int(data.get('week') or 1),
                name=data.get('day_name') or f'Dia {i+1}',label=data.get('day_label') or f'Dia {i+1}')
            self.session.add(day)
            await self.session.flush()
            for j, ex in enumerate(data.get('exercises') or []):
                self.session.add(PlanExercise(user_id=user_id,day_id=day.id,position=j,
                    name=ex.get('name',''),sets=int(ex.get('sets') or 3),reps=str(ex.get('reps') or 12),
                    weight=str(ex.get('weight') or ''),rest_seconds=int(ex.get('rest_seconds') or 60),
                    muscle_group=ex.get('muscle_group') or '',tutorial=ex.get('tutorial') or '',
                    video_url=ex.get('video_url') or '',notes=ex.get('notes') or ''))
        await self.session.flush()
        return plan

    async def plan(self, user_id, plan_id):
        return await self.session.scalar(select(WorkoutPlan).where(WorkoutPlan.user_id == user_id,WorkoutPlan.id == plan_id)
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
