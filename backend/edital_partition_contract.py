"""Total primary-block allocation on transport; canonical ranges stay unchanged."""
from copy import deepcopy
from itertools import groupby
from pydantic import Field, model_validator
from jsonschema import Draft202012Validator, ValidationError as SchemaValidationError
from edital_pipeline_contracts import Contract,InventoryUnit,RolePart,NamedFact,SemanticKind,SemanticLevel,ProposedFact,BlockClassification,INVENTORY_PRIMARY_BLOCKS
from edital_transport_contracts import ScopeEvidenceTransport,field


class ClassificationTemplate(Contract):
    kind: SemanticKind = field(BlockClassification,'kind')
    level: SemanticLevel = field(BlockClassification,'level')
    title: ProposedFact = field(BlockClassification,'title')
    applicability: ScopeEvidenceTransport


class InventoryPartitionTransport(Contract):
    roles: list[RolePart] = field(InventoryUnit,'roles')
    classes: list[ClassificationTemplate] = Field(min_length=1,max_length=INVENTORY_PRIMARY_BLOCKS)
    coverage: dict[str,int] = Field(min_length=1,max_length=INVENTORY_PRIMARY_BLOCKS)
    facts: list[NamedFact] = field(InventoryUnit,'facts')
    warnings: list[str] = field(InventoryUnit,'warnings')

    def canonical_for(self, primary_ids):
        if set(self.coverage)!=set(primary_ids):raise ValueError('Coverage must match every primary block')
        if set(self.coverage.values())!=set(range(len(self.classes))):raise ValueError('Coverage must use exactly the supplied class indexes')
        payload=self.model_dump(mode='json',exclude={'classes','coverage'});rows=[]
        # Each block has an explicit model choice. Only adjacent choices are
        # grouped; no omitted block/default/semantic class is inferred.
        for index,group in groupby(primary_ids,key=self.coverage.__getitem__):
            ids=list(group);row=deepcopy(self.classes[index].model_dump(mode='json'))
            row.update(row.pop('applicability'))
            row.update(block_id=ids[0],end_block_id=ids[-1] if len(ids)>1 else None)
            rows.append(row)
        payload['classifications']=rows
        try:Draft202012Validator(InventoryUnit.model_json_schema()).validate(payload)
        except SchemaValidationError as error:raise ValueError('Canonical inventory contract rejected') from error
        return InventoryUnit.model_validate(payload)


def partition_contract(primary_ids):
    ids=tuple(primary_ids)
    if not ids or len(ids)>INVENTORY_PRIMARY_BLOCKS or len(ids)!=len(set(ids)):raise ValueError('Invalid primary source set')
    class UnitInventoryPartition(InventoryPartitionTransport):
        def as_canonical(self):return self.canonical_for(ids)

        @model_validator(mode='after')
        def original_contract(self):
            self.as_canonical()
            return self
    return UnitInventoryPartition
