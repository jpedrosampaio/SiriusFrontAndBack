"""Synthetic provider fixtures only; never used to repair runtime responses."""
from edital_pipeline_contracts import InventoryUnit


def inventory_wire(payload):
    data=InventoryUnit.model_validate(payload).model_dump(mode='json')
    for row in data['classifications']:
        row['applicability']={name:row.pop(name) for name in ('scope','role_references','scope_sources')}
    return data


def partition_wire(payload, primary_ids):
    """Synthetic span fixtures only; runtime never repairs a provider proposal."""
    from copy import deepcopy
    from edital_transport_contracts import InventoryTransport
    rows=payload.get('classifications',[])
    if rows and 'applicability' in rows[0]:data=InventoryTransport.model_validate(payload).as_canonical().model_dump(mode='json')
    else:data=InventoryUnit.model_validate(payload).model_dump(mode='json')
    result={key:deepcopy(value) for key,value in data.items() if key!='classifications'}
    result.update(classes=[],coverage={})
    for index,row in enumerate(data['classifications']):
        first=primary_ids.index(row['block_id']);last=primary_ids.index(row['end_block_id'] or row['block_id'])
        model={key:deepcopy(value) for key,value in row.items() if key not in ('block_id','end_block_id','scope','role_references','scope_sources')}
        model['applicability']={key:deepcopy(row[key]) for key in ('scope','role_references','scope_sources')}
        result['classes'].append(model)
        for identity in primary_ids[first:last+1]:
            if identity in result['coverage']:raise AssertionError('Overlapping synthetic coverage')
            result['coverage'][identity]=index
    if set(result['coverage'])!=set(primary_ids):raise AssertionError('Missing synthetic coverage')
    return result
