"""Recognize explicit read-only queries before the financial/AI parser."""
import unicodedata
from datetime import timedelta
from services.event_queue import utc_now


def query_kind(message):
    text=''.join(c for c in unicodedata.normalize('NFD',message.lower()) if unicodedata.category(c)!='Mn')
    text=' '.join(text.strip(' ?!.').split())
    return {'/hoje':'today','o que faco hoje':'today','o que devo fazer hoje':'today','o que devo fazer agora':'today',
        '/treino':'training','qual meu treino':'training','qual e meu treino':'training',
        '/semana':'finance','quanto gastei esta semana':'finance',
        '/revisoes':'reviews','quais revisoes estao atrasadas':'reviews','revisoes atrasadas':'reviews'}.get(text)


async def answer(uid,kind):
    if kind=='today':
        from services.event_reports import briefing, render_text
        return render_text((await briefing(uid)).model_dump(mode='json'))
    if kind=='training':
        from services.life_state import snapshot
        state=await snapshot(uid)
        training=next(d for d in state.domains if d.domain=='training')
        lines=['Treino de hoje:']
        lines.extend(c.title for c in training.candidates[:5])
        if not training.candidates:lines.append('Nenhum treino flexível elegível; confira o plano e os dias configurados no Sirius.')
        active=training.facts.get('active_session')
        if active:lines.append('Há uma sessão ativa; retome pelo Sirius.')
        lines.extend(training.warnings[:3])
        return '\n'.join(lines)[:3900]
    from db.session import unit_of_work
    from db.models.identity import User
    from zoneinfo import ZoneInfo
    async with unit_of_work() as session:
        user=await session.get(User,uid);day=utc_now().astimezone(ZoneInfo(user.timezone)).date()
        if kind=='finance':
            from services.telegram import totals
            start=day-timedelta(days=day.weekday())
            _,expense=await totals(session,uid,start,day)
            return f'Despesas registradas de {start} a {day}: R$ {expense:.2f}. Fonte: suas transações; não é saldo bancário.'
        from services.study_evidence import latest_reviews
        rows=await latest_reviews(session,uid,due=day,limit=21)
        return ('Revisões vencidas registradas (até 20):\n'+'\n'.join(f"{r['title']} · {r['due_date']}" for r in rows[:20])+
            ('\nHá mais revisões; abra Preparação.' if len(rows)>20 else ''))[:3900] if rows else 'Nenhuma revisão vencida registrada nos tópicos ativos.'
