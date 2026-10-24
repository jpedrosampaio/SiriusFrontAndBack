"""Lossless provider-only shape; stored/public proposals keep their original contract.

Groq's strict compiler rejects object unions with multiple enum discriminator
candidates, even when common enums have identical values in every alternative.
Only scope-specific fields belong inside the applicability union. No values,
sources, defaults or semantic applicability are inferred by this adapter.
"""
from copy import deepcopy
from pydantic import ConfigDict, model_validator
from jsonschema import Draft202012Validator, ValidationError as SchemaValidationError
from edital_pipeline_contracts import (Contract, Citation, ProposedFact, SemanticKind,
    SemanticLevel, RoleApplicability, BlockClassification, InventoryUnit, classification_scope_schema)


def field(model, name):
    """Reuse bounds/defaults without retaining the overridden field's old type."""
    result = deepcopy(model.model_fields[name])
    result.annotation = None
    return result


class ScopeEvidenceTransport(Contract):
    model_config = ConfigDict(json_schema_extra=classification_scope_schema)
    scope: RoleApplicability = field(BlockClassification, 'scope')
    role_references: list[ProposedFact] = field(BlockClassification, 'role_references')
    scope_sources: list[Citation] = field(BlockClassification, 'scope_sources')


class ClassificationTransport(Contract):
    block_id: str = field(BlockClassification, 'block_id')
    end_block_id: str | None = field(BlockClassification, 'end_block_id')
    kind: SemanticKind = field(BlockClassification, 'kind')
    level: SemanticLevel = field(BlockClassification, 'level')
    title: ProposedFact = field(BlockClassification, 'title')
    applicability: ScopeEvidenceTransport


class InventoryTransport(InventoryUnit):
    classifications: list[ClassificationTransport] = field(InventoryUnit, 'classifications')

    def as_canonical(self):
        payload = self.model_dump(mode='json')
        for row in payload['classifications']:
            scope = row.pop('applicability')
            # Closed wire objects forbid conflicting flat keys. Transfer only
            # those three validated values, without changing their evidence.
            row.update(scope)
        try:
            Draft202012Validator(InventoryUnit.model_json_schema()).validate(payload)
        except SchemaValidationError as error:
            raise ValueError('Canonical inventory contract rejected') from error
        return InventoryUnit.model_validate(payload)

    @model_validator(mode='after')
    def canonical_contract(self):
        # Keep original heading/scope/Pydantic invariants inside the router's
        # validation gate, before a successful result or checkpoint is returned.
        self.as_canonical()
        return self
