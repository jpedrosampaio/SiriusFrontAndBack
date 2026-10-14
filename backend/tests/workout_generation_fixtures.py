"""Synthetic provider proposals with explicit apparatus/level facts."""
def bases(labels=('A','B','C'),kind='resistencia',equipment=None,count=3,minutes=30):
    equipment=['halteres'] if equipment is None else equipment
    sessions=[]
    for label in labels:
        exercises=[]
        for index in range(count):
            exercises.append({'name':f'Exercício {label}-{index}','sets':3,'reps':'8-12','weight':'40 kg',
                'rest_seconds':60,'muscle_group':'cardio' if kind=='corrida' else ('pernas' if index%2==0 else 'peito'),
                'tutorial':'Execute de forma controlada. Reveja a proposta com orientação.',
                'required_equipment':equipment,'difficulty':'iniciante','exercise_kind':kind})
        sessions.append({'label':label,'name':f'Base {label}','session_kind':'corrida' if kind=='corrida' else 'forca',
            'estimated_minutes':minutes,'exercises':exercises})
    return {'name':'Proposta de IA','description':'Bases variadas para consistência.','base_sessions':sessions}
