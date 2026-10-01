from sqlalchemy import select
from db.models.exams import Exam, ExamQuestion, Question, ExamAttempt


class ExamRepository:
    def __init__(self,session):
        self.session = session

    async def get(self,user_id,exam_id):
        return await self.session.scalar(select(Exam).where(Exam.user_id == user_id,Exam.id == exam_id))

    async def questions(self,user_id,exam_id):
        return (await self.session.execute(select(Question,ExamQuestion.weight).join(ExamQuestion,
            (ExamQuestion.question_id == Question.id)&(ExamQuestion.user_id == Question.user_id)).where(
            ExamQuestion.user_id == user_id,ExamQuestion.exam_id == exam_id,Question.user_id == user_id).order_by(ExamQuestion.position))).all()

    async def latest_attempt(self,user_id,exam_id):
        return await self.session.scalar(select(ExamAttempt).where(ExamAttempt.user_id == user_id,ExamAttempt.exam_id == exam_id)
            .order_by(ExamAttempt.completed_at.desc(),ExamAttempt.id.desc()).limit(1))
