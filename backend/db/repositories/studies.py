from datetime import date, datetime, timezone
from sqlalchemy import func, select
from db.models.studies import Notebook, QuestionAttempt, StudySession, StudyTopic, ReviewEvent, FlashcardReview


class StudiesRepository:
    def __init__(self,session):
        self.session = session

    async def notebook(self,user_id,notebook_id):
        return await self.session.scalar(select(Notebook).where(Notebook.user_id == user_id,Notebook.id == notebook_id,Notebook.archived_at.is_(None)))

    async def topic(self,user_id,notebook_id,topic_key):
        return await self.session.scalar(select(StudyTopic).where(StudyTopic.user_id == user_id,
            StudyTopic.notebook_id == notebook_id,StudyTopic.topic_key == topic_key,StudyTopic.archived_at.is_(None)))

    async def add_attempt(self,user_id,**values):
        row = QuestionAttempt(user_id=user_id,**values)
        self.session.add(row)
        await self.session.flush()
        return row

    async def attempts(self,user_id,*,notebook_id=None,topic_id=None,before=None,limit=200):
        query = select(QuestionAttempt).where(QuestionAttempt.user_id == user_id)
        if notebook_id:
            query = query.where(QuestionAttempt.notebook_id == notebook_id)
        if topic_id:
            query = query.where(QuestionAttempt.topic_id == topic_id)
        if before:
            from sqlalchemy import tuple_
            query = query.where(tuple_(QuestionAttempt.answered_at,QuestionAttempt.id) < tuple_(*before))
        return list((await self.session.scalars(query.order_by(QuestionAttempt.answered_at.desc(),QuestionAttempt.id.desc()).limit(min(max(limit,1),500)))).all())

    async def program_facts(self,user_id,program_id):
        notebooks = select(Notebook.id).where(Notebook.user_id == user_id,Notebook.program_id == program_id,Notebook.archived_at.is_(None))
        minutes = await self.session.scalar(select(func.coalesce(func.sum(StudySession.duration_minutes),0))
            .where(StudySession.user_id == user_id,StudySession.notebook_id.in_(notebooks),StudySession.completed.is_(True)))
        total,correct = (await self.session.execute(select(func.coalesce(func.sum(QuestionAttempt.total),0),
            func.coalesce(func.sum(QuestionAttempt.correct),0)).where(QuestionAttempt.user_id == user_id,
            QuestionAttempt.notebook_id.in_(notebooks)))).one()
        return {'studied_minutes':minutes,'total_questions':total,'correct_questions':correct,
            'accuracy':round(correct/total*100,1) if total else None}

    async def add_review(self,user_id,topic_id,result,next_review=None):
        row = ReviewEvent(user_id=user_id,topic_id=topic_id,result=result,
            reviewed_at=datetime.now(timezone.utc),next_review=next_review)
        self.session.add(row)
        await self.session.flush()
        return row
