"""Deterministic suggestions include the evidence and rule that produced them."""
def suggestions_from_snapshot(data):
    result = []
    def add(rule, title, message, link, evidence):
        result.append({'id': rule, 'rule': rule, 'title': title, 'message': message,
                       'description': message, 'link': link, 'action_link': link, 'action': 'Abrir', 'icon': '→', 'type': 'info', 'evidence': evidence})
    remaining = data['tasks_today'] - data['tasks_completed_today']
    if remaining > 0:
        add('tasks_pending_today', 'Organize o restante do dia', f'{remaining} tarefa(s) previstas ainda não concluídas.', '/tasks', {'pending': remaining})
    due = data['study_stats']['flashcards_due']
    if due:
        add('reviews_due', 'Revisões pendentes', f'{due} cartão(ões) aguardam revisão. Reserve um bloco no cronograma.', '/studies', {'due': due})
    if data['expenses'] > data['income']:
        add('monthly_negative_balance', 'Confira o orçamento', 'As despesas registradas no mês superam as receitas registradas.', '/finance', {'income': data['income'], 'expenses': data['expenses']})
    if data['workout_stats']['workouts_this_week'] and not data['nutrition_stats']['meals_count']:
        add('workout_without_food_log_today', 'Complete seus registros', 'Há treino registrado nos últimos sete dias e nenhuma refeição registrada hoje.', '/nutrition', {'workouts_last_7_days': data['workout_stats']['workouts_this_week'], 'meals_today': 0})
    return result
