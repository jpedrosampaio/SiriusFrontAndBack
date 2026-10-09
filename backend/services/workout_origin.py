"""Stable, server-written session provenance in the existing feedback JSON column."""
from uuid import UUID

ORIGIN_KEY = '_training_origin_v1'


def snapshot(plan_id, day_id, day_index):
    return {ORIGIN_KEY: {'version': 1, 'plan_id': str(plan_id), 'day_id': str(day_id), 'day_index': day_index}}


def day_identity(row):
    origin = row.feedback.get(ORIGIN_KEY) if isinstance(row.feedback, dict) else None
    if (not isinstance(origin, dict) or type(origin.get('version')) is not int or origin['version'] != 1
        or origin.get('plan_id') != str(row.plan_id) or type(origin.get('day_index')) is not int
        or origin['day_index'] != row.day_index):
        return None
    try:
        return str(UUID(origin['day_id']))
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


def public_feedback(row):
    if not isinstance(row.feedback, dict) or ORIGIN_KEY not in row.feedback:
        return row.feedback
    result = {k: v for k, v in row.feedback.items() if k != ORIGIN_KEY}
    return result if result else None
