"""Owned read-only lower-bound planning. No prices, retries or unknown work invented."""
from sqlalchemy import select
from db.models.edital_units import EditalUnit
from edital_pipeline_contracts import MAX_PROVIDER_ATTEMPTS
from ai.schemas import TRANSPORT_VERSION


def estimate(state,rows):
    generations={str(state.inventory.generation)}
    if state.selected_role_id in state.scopes:generations.add(str(state.scopes[state.selected_role_id].generation))
    active=[row for row in rows if str(row['generation']) in generations and row['status']!='split']
    remaining={kind:sum(row['kind']==kind and row['status']!='completed' for row in active)
        for kind in ('inventory','scope','detail','verify')}
    checked={row.get('reviewed_unit_key') for row in active if row['kind']=='verify'}
    missing=sum(row['kind'] in ('inventory','detail') and row['unit_key'] not in checked for row in active)
    remaining['verify']+=missing
    minimum=sum(remaining.values());required=state.budget.reserved_attempts+minimum
    unknown=[]
    if not state.selected_role_id:unknown=['selected_role_association','selected_role_content']
    elif remaining['inventory'] or remaining['scope']:unknown=['selected_role_content']
    validated=bool(state.provider_approval and state.provider_approval.transport_version==TRANSPORT_VERSION and state.provider_approval.pilot_validated)
    return {'stages':remaining,'minimum_remaining_attempts':minimum,'minimum_total_attempts':required,
        'remaining_budget':max(0,state.budget.provider_limit-state.budget.reserved_attempts),
        'extension_required':required>state.budget.provider_limit,'maximum_limit':MAX_PROVIDER_ATTEMPTS,
        'unknown_stages':unknown,'includes_retries':False,'live_provider_validated':validated,
        'diagnostic_cases':['text','json','inventory'] if state.phase=='inventory' and not state.selected_role_id and remaining['inventory'] and not validated else []}


async def forecast(session,analysis,state):
    records=(await session.execute(select(EditalUnit.generation,EditalUnit.kind,EditalUnit.status,
        EditalUnit.unit_key,EditalUnit.diagnostics['validation']['expected_reviewed_unit_key'].astext).where(
        EditalUnit.user_id==analysis.user_id,EditalUnit.analysis_id==analysis.id))).all()
    return estimate(state,[dict(zip(('generation','kind','status','unit_key','reviewed_unit_key'),row)) for row in records])
