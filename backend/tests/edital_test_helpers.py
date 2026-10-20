"""Low-level lifecycle fixtures start after an explicit, previously validated pilot.

Approval HTTP/worker gates are exercised independently in provider recovery tests.
No provider IO or weakening of production authorization is installed here.
"""
from db.session import unit_of_work
from db.models.files import EditalJob
from sqlalchemy import select
from edital_pipeline_contracts import ProviderApproval
from ai.schemas import TRANSPORT_VERSION
from services import edital_pipeline_store as store


async def persist_approved(uid,job_id,token,document):
    result=await store.persist_input(uid,job_id,token,document)
    async with unit_of_work() as session:
        row=await store.owned_analysis(session,uid,result['analysis_id'],lock=True)
        state=store.manifest(row)
        if state.status=='waiting_provider':
            state.status=state.inventory.status='processing';state.error_kind=None
            state.provider_approval=ProviderApproval(transport_version=TRANSPORT_VERSION,mode='full',pilot_validated=True,pilot_stop_after=0)
            store.write_manifest(row,state)
            job=await session.scalar(select(EditalJob).where(EditalJob.user_id==uid,EditalJob.id==store.uuid(job_id)))
            job.status='queued';job.finished_at=None
    return result
