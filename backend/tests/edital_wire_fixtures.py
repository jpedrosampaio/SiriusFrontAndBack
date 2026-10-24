"""Synthetic provider fixtures only; never used to repair runtime responses."""
from edital_pipeline_contracts import InventoryUnit


def inventory_wire(payload):
    data=InventoryUnit.model_validate(payload).model_dump(mode='json')
    for row in data['classifications']:
        row['applicability']={name:row.pop(name) for name in ('scope','role_references','scope_sources')}
    return data
