"""Shared SQL predicate: legacy counted evidence remains valid; explicit blanks do not."""
from sqlalchemy import func
from db.models.studies import QuestionAttempt


def answered_attempt():
    return func.coalesce(QuestionAttempt.evidence['answered'].as_boolean(),True)
