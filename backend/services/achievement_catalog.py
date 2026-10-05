"""Presentation and targets preserved from the original achievement catalog."""


def achievement_catalog(metrics, xp):
    return [
        {'id': 'task_1', 'title': 'Primeira Missão', 'description': 'Complete sua primeira tarefa', 'icon': 'check', 'category': 'tasks', 'color': '#007AFF', 'target': 1, 'current': min(metrics['tasks_completed'], 1)},
        {'id': 'task_10', 'title': 'Executor', 'description': 'Complete 10 tarefas', 'icon': 'check-double', 'category': 'tasks', 'color': '#007AFF', 'target': 10, 'current': min(metrics['tasks_completed'], 10)},
        {'id': 'task_50', 'title': 'Produtivo', 'description': 'Complete 50 tarefas', 'icon': 'list-checks', 'category': 'tasks', 'color': '#007AFF', 'target': 50, 'current': min(metrics['tasks_completed'], 50)},
        {'id': 'task_200', 'title': 'Imparável', 'description': 'Complete 200 tarefas', 'icon': 'rocket', 'category': 'tasks', 'color': '#007AFF', 'target': 200, 'current': min(metrics['tasks_completed'], 200)},
        {'id': 'habit_create', 'title': 'Novo Hábito', 'description': 'Crie seu primeiro hábito', 'icon': 'trending-up', 'category': 'habits', 'color': '#39FF14', 'target': 1, 'current': min(metrics['habits'], 1)},
        {'id': 'habit_streak_7', 'title': 'Semana Perfeita', 'description': 'Mantenha um streak de 7 dias em um hábito', 'icon': 'flame', 'category': 'habits', 'color': '#39FF14', 'target': 7, 'current': min(metrics['max_habit_streak'], 7)},
        {'id': 'habit_streak_30', 'title': 'Mês de Ferro', 'description': 'Mantenha um streak de 30 dias', 'icon': 'flame', 'category': 'habits', 'color': '#39FF14', 'target': 30, 'current': min(metrics['max_habit_streak'], 30)},
        {'id': 'habit_streak_100', 'title': 'Disciplina Absoluta', 'description': '100 dias de streak em um hábito', 'icon': 'crown', 'category': 'habits', 'color': '#39FF14', 'target': 100, 'current': min(metrics['max_habit_streak'], 100)},
        {'id': 'fin_first', 'title': 'Primeiro Registro', 'description': 'Registre sua primeira transação', 'icon': 'dollar', 'category': 'finance', 'color': '#FF9500', 'target': 1, 'current': min(metrics['transactions'], 1)},
        {'id': 'fin_50', 'title': 'Controlador', 'description': 'Registre 50 transações', 'icon': 'wallet', 'category': 'finance', 'color': '#FF9500', 'target': 50, 'current': min(metrics['transactions'], 50)},
        {'id': 'fin_200', 'title': 'Mestre das Finanças', 'description': 'Registre 200 transações', 'icon': 'bar-chart', 'category': 'finance', 'color': '#FF9500', 'target': 200, 'current': min(metrics['transactions'], 200)},
        {'id': 'study_first', 'title': 'Primeira Sessão', 'description': 'Realize sua primeira sessão de estudo', 'icon': 'book', 'category': 'study', 'color': '#A855F7', 'target': 1, 'current': min(metrics['study_sessions'], 1)},
        {'id': 'study_hours_10', 'title': 'Estudioso', 'description': 'Acumule 10 horas de estudo', 'icon': 'clock', 'category': 'study', 'color': '#A855F7', 'target': 600, 'current': min(metrics['total_study_minutes'], 600)},
        {'id': 'study_hours_50', 'title': 'Acadêmico', 'description': 'Acumule 50 horas de estudo', 'icon': 'graduation-cap', 'category': 'study', 'color': '#A855F7', 'target': 3000, 'current': min(metrics['total_study_minutes'], 3000)},
        {'id': 'study_streak_14', 'title': 'Foco Total', 'description': '14 dias consecutivos de estudo', 'icon': 'target', 'category': 'study', 'color': '#A855F7', 'target': 14, 'current': min(metrics['longest_study_streak'], 14)},
        {'id': 'flash_100', 'title': 'Memorização', 'description': 'Crie 100 flashcards', 'icon': 'brain', 'category': 'study', 'color': '#A855F7', 'target': 100, 'current': min(metrics['flashcards'], 100)},
        {'id': 'gym_first', 'title': 'Primeiro Treino', 'description': 'Complete seu primeiro treino', 'icon': 'dumbbell', 'category': 'workouts', 'color': '#EF4444', 'target': 1, 'current': min(metrics['workout_logs'], 1)},
        {'id': 'gym_20', 'title': 'Atleta', 'description': 'Complete 20 treinos', 'icon': 'medal', 'category': 'workouts', 'color': '#EF4444', 'target': 20, 'current': min(metrics['workout_logs'], 20)},
        {'id': 'gym_hours_10', 'title': 'Forte', 'description': 'Acumule 10 horas de treino', 'icon': 'timer', 'category': 'workouts', 'color': '#EF4444', 'target': 600, 'current': min(metrics['total_workout_minutes'], 600)},
        {'id': 'meal_first', 'title': 'Primeira Refeição', 'description': 'Registre sua primeira refeição', 'icon': 'utensils', 'category': 'nutrition', 'color': '#22C55E', 'target': 1, 'current': min(metrics['meals'], 1)},
        {'id': 'meal_50', 'title': 'Alimentação Consciente', 'description': 'Registre 50 refeições', 'icon': 'apple', 'category': 'nutrition', 'color': '#22C55E', 'target': 50, 'current': min(metrics['meals'], 50)},
        {'id': 'goal_create', 'title': 'Visionário', 'description': 'Crie sua primeira meta', 'icon': 'target', 'category': 'goals', 'color': '#F59E0B', 'target': 1, 'current': min(metrics['goals'], 1)},
        {'id': 'goal_5', 'title': 'Ambicioso', 'description': 'Tenha 5 metas ativas', 'icon': 'trophy', 'category': 'goals', 'color': '#F59E0B', 'target': 5, 'current': min(metrics['goals'], 5)},
        {'id': 'xp_100', 'title': 'Soldado', 'description': 'Alcance 100 XP', 'icon': 'zap', 'category': 'xp', 'color': '#FFD700', 'target': 100, 'current': min(xp, 100)},
        {'id': 'xp_500', 'title': 'Veterano', 'description': 'Alcance 500 XP', 'icon': 'star', 'category': 'xp', 'color': '#FFD700', 'target': 500, 'current': min(xp, 500)},
        {'id': 'xp_1000', 'title': 'Lenda', 'description': 'Alcance 1000 XP', 'icon': 'crown', 'category': 'xp', 'color': '#FFD700', 'target': 1000, 'current': min(xp, 1000)},
        {'id': 'xp_3000', 'title': 'Supremo', 'description': 'Alcance 3000 XP', 'icon': 'shield', 'category': 'xp', 'color': '#FFD700', 'target': 3000, 'current': min(xp, 3000)},
    ]
