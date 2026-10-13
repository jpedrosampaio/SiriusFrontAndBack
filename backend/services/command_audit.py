"""Audit and conflict-aware undo inside the existing user-serialized transaction."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from db.models.command import CommandAudit
from db.models.planning import CalendarEvent
from command_contracts import Why


async def record(session, uid, *, event, action, entity_type, entity_id=None,
                 evidence=(), constraints=(), limitations=(), before=None, after=None, undo_kind=None):
    row = CommandAudit(user_id=uid, event=event, action=action, entity_type=entity_type,
        entity_id=entity_id, reason=Why(evidence=list(evidence)[:12], constraints=list(constraints)[:12],
        limitations=list(limitations)[:12], source=event).model_dump(), before=before,
        after=after, undo_kind=undo_kind)
    session.add(row)
    await session.flush()
    return str(row.id)


def public(row):
    # Content snapshots stay server-side; the user sees references and factual reasons.
    changes=None
    if row.event=='preparation.plan.updated':
        changes={'before':row.before,'after':{k:v for k,v in (row.after or {}).items() if k!='settings'}}
        changes['after'].update({k:row.after['settings'].get(k) for k in ('start_date','end_date','adaptive','block_minutes')})
    elif row.event=='preparation.entry.updated':changes={'before':row.before,'after':row.after}
    elif row.undo_kind=='allocations':changes={'after':{'allocated_count':len((row.after or {}).get('allocations',[]))}}
    return {'id': str(row.id), 'actor': row.actor, 'event': row.event, 'action': row.action,
        'entity_type': row.entity_type, 'entity_id': str(row.entity_id) if row.entity_id else None,
        'created_at': row.created_at.isoformat(), 'why': row.reason,'changes':changes,
        'undo_available': bool(row.undo_kind and not row.undone_at),
        'undone_at': row.undone_at.isoformat() if row.undone_at else None}


def calendar_snapshot(row):
    return {'id': str(row.id), 'title': row.title, 'start_at': row.start_at.astimezone(timezone.utc).isoformat(),
        'end_at': row.end_at.astimezone(timezone.utc).isoformat(), 'source_type': row.source_type,
        'source_id': str(row.source_id) if row.source_id else None, 'details': row.details,
        'updated_at':row.updated_at.astimezone(timezone.utc).isoformat()}


async def undo(session, user, audit_id):
    row = await session.scalar(select(CommandAudit).where(CommandAudit.user_id == user.id,
        CommandAudit.id == audit_id).with_for_update())
    if row is None: raise HTTPException(404, 'Registro não encontrado.')
    if row.undone_at: return {'audit_id': str(row.id), 'already_undone': True, 'xp_earned': 0}
    if row.undo_kind == 'availability':
        prefs = dict(user.preferences or {})
        if prefs.get('life_availability') != row.after['availability'] or prefs.get('life_availability_revision') != row.after['revision']:
            raise HTTPException(409, 'Disponibilidade alterada desde esta ação. Confira o estado atual.')
        if row.before['availability'] is None: prefs.pop('life_availability', None)
        else:
            from life_contracts import Availability
            from pydantic import ValidationError
            from db.models.health import WorkoutPlan
            try:previous=Availability.model_validate(row.before['availability'])
            except ValidationError:raise HTTPException(409,'A configuração anterior é inválida; configure a disponibilidade atual.') from None
            if previous.training_plan_id:
                owned=await session.scalar(select(WorkoutPlan.id).where(WorkoutPlan.user_id==user.id,
                    WorkoutPlan.id==previous.training_plan_id,WorkoutPlan.archived_at.is_(None)))
                if owned is None:raise HTTPException(409,'O plano de treino anterior não está mais disponível.')
            prefs['life_availability'] = row.before['availability']
        from uuid import uuid4
        prefs['life_availability_revision']=str(uuid4())
        user.preferences = prefs
    elif row.undo_kind == 'allocations':
        from uuid import UUID
        expected = row.after['allocations']
        ids = [UUID(value['id']) for value in expected]
        current = (await session.scalars(select(CalendarEvent).where(CalendarEvent.user_id == user.id,
            CalendarEvent.id.in_(ids)).with_for_update())).all()
        by_id = {str(value.id): value for value in current}
        if len(current) != len(expected) or any(calendar_snapshot(by_id[value['id']]) != value
            for value in expected): raise HTTPException(409, 'O planejamento mudou; não é possível desfazer esta versão.')
        if any(value.source_type != 'global_plan' or value.start_at <= datetime.now(timezone.utc) for value in current):
            raise HTTPException(409, 'Só alocações flexíveis futuras e intactas podem ser desfeitas.')
        for value in current: await session.delete(value)
    else: raise HTTPException(409, 'Esta ação não oferece reversão segura.')
    row.undone_at = datetime.now(timezone.utc)
    await record(session, user.id, event='command.undo', action='undo', entity_type='audit',
        entity_id=row.id, evidence=['Reversão confirmada pelo proprietário; estado conferido na transação.'],
        constraints=['Históricos, XP e compromissos fixos preservados.'])
    return {'audit_id': str(row.id), 'undone': True, 'xp_earned': 0}
