"""Aggregate full histories in MongoDB, without silently truncating totals."""
import asyncio
from datetime import datetime, timedelta


async def aggregate_one(collection, query, fields):
    rows = await collection.aggregate([{'$match': query}, {'$group': {'_id': None, **fields}}]).to_list(1)
    return rows[0] if rows else {}


async def dashboard_snapshot(db, user, today):
    from task_recurrence import task_day_counts
    own = {'user_id': user.user_id}
    day = {**own, 'date': today}
    start = today[:7] + '-01'
    parsed = datetime.strptime(start, '%Y-%m-%d')
    next_month = (parsed.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%Y-%m-%d')
    sums = lambda *names: {name: {'$sum': f'${name}'} for name in names}
    (task_counts, habits, finances, goals, workouts, meals, water, nutrition_goal,
     studies, focus, streak, cards, due, notebooks, simulations, attempts, questions) = await asyncio.gather(
        task_day_counts(db, user.user_id, today),
        aggregate_one(db.habits, own, {'count': {'$sum': 1}, 'done': {'$sum': {'$cond': [{'$in': [today, {'$ifNull': ['$completions', []]}]}, 1, 0]}}}),
        aggregate_one(db.transactions, {**own, 'date': {'$gte': start, '$lt': next_month}}, {
            kind: {'$sum': {'$cond': [{'$eq': ['$type', kind]}, '$amount', 0]}} for kind in ('income', 'expense')}),
        aggregate_one(db.goals, own, {'count': {'$sum': 1}, 'progress': {'$avg': {'$min': [100, {'$max': [0, {'$ifNull': ['$progress', 0]}]}]}}}),
        aggregate_one(db.workout_logs, {**own, 'completed': True, 'date': {'$gte': (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=6)).strftime('%Y-%m-%d'), '$lte': today}}, {'count': {'$sum': 1}, **sums('duration_minutes', 'calories', 'xp_earned')}),
        aggregate_one(db.meals, day, {'count': {'$sum': 1}, **sums('total_calories', 'total_protein')}),
        aggregate_one(db.water_logs, day, sums('amount_ml')),
        db.nutrition_goals.find_one(own, {'_id': 0}),
        aggregate_one(db.study_sessions, day, sums('duration_minutes')),
        aggregate_one(db.focus_sessions, {**day, 'completed': True}, sums('focus_minutes')),
        db.study_streaks.find_one(own, {'_id': 0}),
        db.flashcards.count_documents(own),
        db.flashcards.count_documents({**own, '$or': [{'next_review': {'$lte': today}}, {'next_review': {'$exists': False}}]}),
        db.notebooks.count_documents(own), db.simulados.count_documents(own),
        aggregate_one(db.simulado_attempts, own, {'count': {'$sum': 1}, 'average': {'$avg': '$score'}, 'best': {'$max': '$score'}, **sums('correct_count', 'total_questions')}),
        aggregate_one(db.question_logs, own, sums('total', 'correct')),
    )
    nutrition_goal = nutrition_goal or {}
    streak = streak or {}
    accuracy = lambda correct, total: round(correct / total * 100, 1) if total else 0
    return {
        'user': {'name': user.name, 'xp': user.xp, 'rank': user.rank, 'picture': user.picture},
        'tasks_today': task_counts[0], 'tasks_completed_today': task_counts[1],
        'habits_total': habits.get('count', 0), 'habits_completed_today': habits.get('done', 0),
        'income': finances.get('income', 0), 'expenses': finances.get('expense', 0), 'balance': finances.get('income', 0) - finances.get('expense', 0),
        'goals_total': goals.get('count', 0), 'goals_avg_progress': goals.get('progress', 0),
        'workout_stats': {'workouts_this_week': workouts.get('count', 0), 'total_duration_minutes': workouts.get('duration_minutes', 0), 'total_calories_burned': workouts.get('calories', 0), 'total_xp_earned': workouts.get('xp_earned', 0)},
        'nutrition_stats': {'calories_consumed': meals.get('total_calories', 0), 'calories_goal': nutrition_goal.get('daily_calories', 2000), 'protein_consumed': round(meals.get('total_protein', 0), 1), 'protein_goal': nutrition_goal.get('daily_protein', 150), 'water_consumed_ml': water.get('amount_ml', 0), 'water_goal_ml': nutrition_goal.get('water_goal_ml', 2000), 'meals_count': meals.get('count', 0)},
        'study_stats': {'study_time_today_minutes': studies.get('duration_minutes', 0) + focus.get('focus_minutes', 0), 'current_streak': streak.get('current_streak', 0), 'longest_streak': streak.get('best_streak', 0), 'flashcards_due': due, 'total_flashcards': cards, 'notebooks_count': notebooks},
        'simulado_stats': {'total_simulados': simulations, 'total_attempts': attempts.get('count', 0), 'average_score': round(attempts.get('average') or 0, 1), 'best_score': round(attempts.get('best') or 0, 1), 'total_questions_answered': attempts.get('total_questions', 0), 'total_correct': attempts.get('correct_count', 0), 'accuracy_rate': accuracy(attempts.get('correct_count', 0), attempts.get('total_questions', 0))},
        'question_overview': {'total_answered': questions.get('total', 0), 'total_correct': questions.get('correct', 0), 'accuracy_rate': accuracy(questions.get('correct', 0), questions.get('total', 0))},
    }
