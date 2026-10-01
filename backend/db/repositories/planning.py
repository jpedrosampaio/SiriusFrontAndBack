from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.planning import Task, TaskInstance, Habit, HabitCheck
from task_recurrence import expand_task_dates


class PlanningRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(self, user_id, **values):
        task = Task(user_id=user_id, **values)
        self.session.add(task)
        await self.session.flush()
        return task

    async def get_task(self, user_id, task_id):
        return await self.session.scalar(select(Task).where(Task.user_id == user_id, Task.id == task_id))

    async def task_instance(self, user_id, task_id, day):
        return await self.session.scalar(select(TaskInstance).where(TaskInstance.user_id == user_id,
            TaskInstance.task_id == task_id, TaskInstance.date == day))

    async def tasks_on_date(self, user_id, day, recurrence=None):
        query = select(Task, TaskInstance).outerjoin(TaskInstance,
            (TaskInstance.task_id == Task.id) & (TaskInstance.user_id == Task.user_id) & (TaskInstance.date == day)
        ).where(Task.user_id == user_id, Task.date <= day)
        if recurrence:
            query = query.where(Task.recurrence == recurrence)
        pairs = (await self.session.execute(query.order_by(Task.created_at,Task.id))).all()
        return [(task, instance) for task,instance in pairs if expand_task_dates(
            {'date': task.date.isoformat(), 'recurrence':task.recurrence}, day.isoformat(), day.isoformat())]

    async def create_habit(self, user_id, **values):
        row = Habit(user_id=user_id, **values)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_habit(self, user_id, habit_id):
        return await self.session.scalar(select(Habit).where(Habit.user_id == user_id, Habit.id == habit_id))

    async def habit_check(self, user_id, habit_id, day):
        return await self.session.scalar(select(HabitCheck).where(HabitCheck.user_id == user_id,
            HabitCheck.habit_id == habit_id, HabitCheck.date == day))

    async def habit_dates(self, user_id, habit_id):
        return list((await self.session.scalars(select(HabitCheck.date).where(HabitCheck.user_id == user_id,
            HabitCheck.habit_id == habit_id).order_by(HabitCheck.date))).all())
