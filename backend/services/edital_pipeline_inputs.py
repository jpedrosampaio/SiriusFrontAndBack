"""Bounded inventory packing; every primary source block remains in order."""
import json
from edital_pipeline_contracts import INVENTORY_PRIMARY_BLOCKS
from services.edital_semantics import block_dict


def compact_block(block):
    fields=('id','page','text','kind','column','table_id','table_header_hint',
        'continuation_of','parent_heading_hint','numbering_hint','paragraph_hint','recurring_margin')
    return {key:block[key] for key in fields if block.get(key) not in (None,[],'')}


def inventory_batches(blocks):
    current=[];size=2;characters=0
    for raw in blocks:
        block=block_dict(raw)
        cost=len(json.dumps(compact_block(block),ensure_ascii=False,separators=(',',':')))+1
        if current and (size+cost>16000 or characters+len(block['text'])>10000 or len(current)>=INVENTORY_PRIMARY_BLOCKS):
            yield current;current=[];size=2;characters=0
        current.append(block);size+=cost;characters+=len(block['text'])
    if current:yield current
