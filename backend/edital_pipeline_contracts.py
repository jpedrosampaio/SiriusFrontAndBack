"""Versioned intermediate input and bounded, unconfirmed semantic proposals.

Document text is untrusted data. An AI response cannot confirm its own facts.
"""
from typing import Literal
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

PIPELINE_VERSION = 'edital/universal/6'
MAX_PAGES = 400
MAX_TEXT = 2_000_000
MAX_BLOCKS = 20_000
UNIT_CHARACTERS = 6_000
UNIT_OUTPUT_TOKENS = 3_072
VERIFICATION_OUTPUT_TOKENS = 1_536
MAX_PROVIDER_ATTEMPTS = 200
JOB_IR_PROVIDER = 'extracted_ir_v1'
JOB_INGEST_PROVIDER = 'edital_ingesting_v1'


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid',allow_inf_nan=False)


class SourceBlock(Contract):
    id: str = Field(max_length=64)
    page: int = Field(ge=1, le=MAX_PAGES)
    text: str = Field(min_length=1, max_length=2400)
    bbox: tuple[float, float, float, float]
    kind: Literal['line', 'heading_hint', 'table_row'] = 'line'
    column: int = Field(default=0, ge=0, le=2)
    table_id: str | None = None
    table_header_hint: list[str] = Field(default_factory=list, max_length=40)
    cells: list[str] = Field(default_factory=list, max_length=40)
    continuation_of: str | None = None
    recurring_margin: bool = False
    paragraph_hint: str | None = Field(default=None,max_length=64)
    numbering_hint: str | None = Field(default=None,max_length=100)
    parent_heading_hint: str | None = Field(default=None,max_length=64)


class SourcePage(Contract):
    page: int = Field(ge=1, le=MAX_PAGES)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    quality: Literal['text', 'low_text', 'requires_ocr', 'blank']
    characters: int = Field(ge=0)
    column_hint: int = Field(default=1, ge=1, le=2)
    image_count: int = Field(default=0,ge=0,le=1000)
    blocks: list[SourceBlock] = Field(default_factory=list, max_length=2000)


class DocumentIR(Contract):
    version: Literal['pdf-layout/1'] = 'pdf-layout/1'
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    size_bytes: int = Field(ge=1, le=20*1024*1024)
    pages: list[SourcePage] = Field(min_length=1, max_length=MAX_PAGES)
    ocr_available: bool = False
    warnings: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def bounded_source(self):
        blocks = [block for page in self.pages for block in page.blocks]
        if sum(page.characters for page in self.pages) > MAX_TEXT or len(blocks) > MAX_BLOCKS:
            raise ValueError('Document extraction exceeds operational limits')
        if len({b.id for b in blocks}) != len(blocks):
            raise ValueError('Source block identifiers must be unique')
        if [p.page for p in self.pages] != list(range(1,len(self.pages)+1)):
            raise ValueError('Page coverage must be contiguous')
        if any(b.page != p.page for p in self.pages for b in p.blocks):
            raise ValueError('Source block must belong to its page')
        return self


class Citation(Contract):
    page: int = Field(ge=1, le=MAX_PAGES)
    block_id: str = Field(min_length=1, max_length=64)
    quote: str = Field(min_length=1, max_length=1200)


class ProposedFact(Contract):
    # Preserve the documentary spelling/units. Numeric normalization is separate.
    value: str | None = Field(default=None, max_length=1200)
    state: Literal['extracted', 'missing', 'ambiguous'] = 'missing'
    sources: list[Citation] = Field(default_factory=list, max_length=6)

    @model_validator(mode='after')
    def evidence_required(self):
        if self.state == 'missing':
            if self.value is not None or self.sources:
                raise ValueError('Missing information is not zero or a sourced value')
        elif not self.value or not self.sources:
            raise ValueError('A proposed value requires documentary evidence')
        return self


class RolePart(Contract):
    name: ProposedFact
    code: ProposedFact = Field(default_factory=ProposedFact)
    vacancies: ProposedFact = Field(default_factory=ProposedFact)
    salary: ProposedFact = Field(default_factory=ProposedFact)
    requirements: ProposedFact = Field(default_factory=ProposedFact)


SemanticKind = Literal['general', 'roles', 'requirements', 'registration', 'exam_rules',
    'program', 'schedule', 'annex', 'external_reference', 'other', 'uncertain']


class BlockClassification(Contract):
    block_id: str = Field(min_length=1, max_length=64)
    end_block_id: str | None = Field(default=None,max_length=64)
    kind: SemanticKind
    level: Literal['section','role','knowledge_group','discipline','topic','unspecified'] = 'unspecified'
    title: ProposedFact = Field(default_factory=ProposedFact)
    scope: Literal['all_roles','named_roles','except_roles','unspecified'] = 'unspecified'
    role_references: list[ProposedFact] = Field(default_factory=list,max_length=12)
    scope_sources: list[Citation] = Field(default_factory=list, max_length=3)

    @model_validator(mode='after')
    def sourced_scope(self):
        if self.level!='unspecified' and self.title.value is None:
            raise ValueError('A semantic heading requires its sourced title')
        if self.scope!='unspecified' and not self.scope_sources:
            raise ValueError('Semantic applicability requires source evidence')
        if self.scope in ('named_roles','except_roles') and not self.role_references:
            raise ValueError('Named-role applicability requires documentary references')
        return self


GeneralField = Literal['exam_name', 'board', 'exam_date', 'registration_start', 'registration_end',
    'fee', 'schedule_event', 'external_reference', 'document_relationship']


class NamedFact(Contract):
    key: GeneralField
    fact: ProposedFact


class InventoryUnit(Contract):
    roles: list[RolePart] = Field(default_factory=list, max_length=12)
    classifications: list[BlockClassification] = Field(min_length=1, max_length=60)
    facts: list[NamedFact] = Field(default_factory=list, max_length=12)
    warnings: list[str] = Field(default_factory=list, max_length=8)


class SectionBinding(Contract):
    section_key: str = Field(min_length=1,max_length=64)
    decision: Literal['include','exclude','ambiguous']
    sources: list[Citation] = Field(default_factory=list,max_length=6)
    reason: str = Field(min_length=1,max_length=400)

    @model_validator(mode='after')
    def documentary_decision(self):
        if self.decision!='ambiguous' and not self.sources:
            raise ValueError('A proposed scope decision requires evidence')
        return self


class ScopeUnit(Contract):
    bindings: list[SectionBinding] = Field(min_length=1,max_length=60)


class TopicPart(Contract):
    key: str = Field(min_length=1,max_length=64)
    title: ProposedFact
    parent_key: str | None = Field(default=None,max_length=64)
    numbering: str | None = Field(default=None,max_length=80)


class DisciplinePart(Contract):
    name: ProposedFact
    stage: ProposedFact = Field(default_factory=ProposedFact)
    group: ProposedFact = Field(default_factory=ProposedFact)
    topics: list[TopicPart] = Field(default_factory=list, max_length=24)


class ExamRulePart(Contract):
    target_scope: Literal['stage', 'group', 'discipline']
    target: ProposedFact
    kind: Literal['question_count', 'weight', 'penalty', 'blank_score', 'time_limit', 'evaluation_criterion']
    fact: ProposedFact


class DetailUnit(Contract):
    applicability: Literal['shared', 'selected_role', 'other_role', 'ambiguous']
    scope_sources: list[Citation] = Field(default_factory=list, max_length=6)
    covered_block_ids: list[str] = Field(min_length=1, max_length=60)
    disciplines: list[DisciplinePart] = Field(default_factory=list, max_length=6)
    rules: list[ExamRulePart] = Field(default_factory=list, max_length=12)
    warnings: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode='after')
    def applicable_proposals(self):
        if (self.disciplines or self.rules) and self.applicability not in ('shared','selected_role'):
            raise ValueError('Ambiguous/other-role content cannot become selected-role facts')
        if self.applicability in ('shared','selected_role') and not self.scope_sources:
            raise ValueError('Role applicability requires documentary evidence')
        nodes={}
        for discipline in self.disciplines:
            for node in discipline.topics:
                if node.key in nodes:raise ValueError('Topic keys must be unique within a unit')
                nodes[node.key]=node.parent_key
        for key in nodes:
            seen=set();point=key
            while point in nodes:
                if point in seen or len(seen)>8:raise ValueError('Cyclic or unbounded topic hierarchy')
                seen.add(point);point=nodes[point]
        return self


class VerificationFinding(Contract):
    kind: Literal['missing_role', 'missing_discipline', 'missing_topic', 'ambiguous_association',
        'contradiction', 'unsupported_value', 'hierarchy_gap', 'unknown_structure']
    severity: Literal['warning','blocker']
    subject: ProposedFact = Field(default_factory=ProposedFact)
    description: str = Field(min_length=1,max_length=500)
    sources: list[Citation] = Field(min_length=1,max_length=4)


class VerificationUnit(Contract):
    # A second bounded comparison is still an AI proposal, not human review,
    # an official correction or a calibrated confidence score.
    reviewed_unit_key: str = Field(pattern=r'^[0-9a-f]{64}$')
    covered_block_ids: list[str] = Field(min_length=1,max_length=120)
    findings: list[VerificationFinding] = Field(default_factory=list,max_length=12)


PipelineStatus = Literal['not_started','processing','waiting_provider','quota_paused','awaiting_review',
    'completed','recoverable_failure','cancelled','ocr_required']


class CanonicalFact(Contract):
    value: str | None = Field(default=None,max_length=2000)
    state: Literal['extracted','missing','ambiguous','corrected_by_user'] = 'missing'
    sources: list[Citation] = Field(default_factory=list,max_length=200)
    verification: Literal['awaiting_review','confirmed'] = 'awaiting_review'
    alternatives: list[ProposedFact] = Field(default_factory=list,max_length=200)
    origin: Literal['document','human_declared'] = 'document'
    human_note: str | None = Field(default=None,max_length=1000)
    confirmed_at: datetime | None = None


class CanonicalNamedFact(Contract):
    id: str = Field(min_length=1,max_length=64)
    key: GeneralField
    fact: CanonicalFact


class IdentifiedRole(Contract):
    id: str = Field(min_length=1,max_length=64)
    source_name: str | None = Field(default=None,max_length=1200)
    source_code: str | None = Field(default=None,max_length=1200)
    source_keys: list[str] = Field(default_factory=list,max_length=200)
    name: CanonicalFact
    code: CanonicalFact = Field(default_factory=CanonicalFact)
    vacancies: CanonicalFact = Field(default_factory=CanonicalFact)
    salary: CanonicalFact = Field(default_factory=CanonicalFact)
    requirements: CanonicalFact = Field(default_factory=CanonicalFact)
    issues: list[str] = Field(default_factory=list,max_length=30)


class ProgramTopic(Contract):
    id: str = Field(max_length=64)
    title: CanonicalFact
    parent_id: str | None = Field(default=None,max_length=64)
    numbering: str | None = Field(default=None,max_length=80)


class ProgramDiscipline(Contract):
    id: str = Field(max_length=64)
    name: CanonicalFact
    stage: CanonicalFact = Field(default_factory=CanonicalFact)
    group: CanonicalFact = Field(default_factory=CanonicalFact)
    topics: list[ProgramTopic] = Field(default_factory=list,max_length=3000)


class ProgramRule(Contract):
    id: str = Field(max_length=64)
    target_scope: Literal['stage','group','discipline']
    target: CanonicalFact
    kind: Literal['question_count','weight','penalty','blank_score','time_limit','evaluation_criterion']
    fact: CanonicalFact


class CompiledProgram(Contract):
    disciplines: list[ProgramDiscipline] = Field(default_factory=list,max_length=300)
    rules: list[ProgramRule] = Field(default_factory=list,max_length=300)
    issues: list[str] = Field(default_factory=list,max_length=100)
    unit_digest: str | None = Field(default=None,max_length=64)


class HumanCorrection(Contract):
    value: str | None = Field(max_length=2000)
    note: str = Field(min_length=1,max_length=1000)
    recorded_at: datetime


class ProgramEdits(Contract):
    # Explicit owner changes overlay proposals, including after a reanalysis.
    added_disciplines: list[ProgramDiscipline] = Field(default_factory=list,max_length=300)
    added_topics: dict[str,list[ProgramTopic]] = Field(default_factory=dict,max_length=300)
    removed_disciplines: list[str] = Field(default_factory=list,max_length=300)
    removed_topics: list[str] = Field(default_factory=list,max_length=3000)
    topic_parents: dict[str,str|None] = Field(default_factory=dict,max_length=3000)
    added_rules: list[ProgramRule] = Field(default_factory=list,max_length=300)
    removed_rules: list[str] = Field(default_factory=list,max_length=300)


class ContentScope(Contract):
    generation: UUID
    status: PipelineStatus = 'not_started'
    program: CompiledProgram = Field(default_factory=CompiledProgram)
    topic_keys: dict[str,str] = Field(default_factory=dict,max_length=30000)
    observed_rule_ids: list[str] = Field(default_factory=list,max_length=300)
    findings: dict[str,VerificationFinding] = Field(default_factory=dict,max_length=1000)
    finding_resolutions: dict[str,HumanCorrection] = Field(default_factory=dict,max_length=1000)
    bindings: dict[str,SectionBinding] = Field(default_factory=dict,max_length=10000)
    # Only the owner writes these decisions; their note/time never comes from AI.
    binding_corrections: dict[str,HumanCorrection] = Field(default_factory=dict,max_length=10000)
    previous_confirmed: CompiledProgram | None = None
    corrections: dict[str,HumanCorrection] = Field(default_factory=dict,max_length=10000)
    edits: ProgramEdits = Field(default_factory=ProgramEdits)
    issue_resolutions: dict[str,HumanCorrection] = Field(default_factory=dict,max_length=100)
    unapplied_corrections: list[str] = Field(default_factory=list,max_length=10000)
    confirmed_at: datetime | None = None
    confirmed_digest: str | None = Field(default=None,max_length=64)
    imports: dict[str,str] = Field(default_factory=dict,max_length=100)


class InventoryState(Contract):
    generation: UUID
    status: PipelineStatus = 'not_started'
    roles: list[IdentifiedRole] = Field(default_factory=list,max_length=500)
    sections: list[BlockClassification] = Field(default_factory=list,max_length=10000)
    facts: list[CanonicalNamedFact] = Field(default_factory=list,max_length=1000)
    issues: list[str] = Field(default_factory=list,max_length=100)
    corrections: dict[str,HumanCorrection] = Field(default_factory=dict,max_length=3000)
    findings: dict[str,VerificationFinding] = Field(default_factory=dict,max_length=1000)
    finding_resolutions: dict[str,HumanCorrection] = Field(default_factory=dict,max_length=1000)
    issue_resolutions: dict[str,HumanCorrection] = Field(default_factory=dict,max_length=100)


class DocumentSummary(Contract):
    hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    format: Literal['pdf'] = 'pdf'
    ir_version: Literal['pdf-layout/1'] = 'pdf-layout/1'
    pages: int = Field(ge=1,le=MAX_PAGES)
    characters: int = Field(ge=0,le=MAX_TEXT)
    blocks: int = Field(ge=0,le=MAX_BLOCKS)
    size_bytes: int = Field(ge=1,le=20*1024*1024)
    ocr_required_pages: list[int] = Field(default_factory=list,max_length=MAX_PAGES)
    low_text_pages: list[int] = Field(default_factory=list,max_length=MAX_PAGES)
    image_pages: list[int] = Field(default_factory=list,max_length=MAX_PAGES)
    warnings: list[str] = Field(default_factory=list,max_length=30)
    original_available: bool = False


class ProcessingBudget(Contract):
    provider_limit: int = Field(default=120,ge=1,le=MAX_PROVIDER_ATTEMPTS)
    reserved_attempts: int = Field(default=0,ge=0)
    leaf_unit_limit: int = Field(default=200,ge=1,le=400)
    # Values are only provider-reported usage; unavailable attempts stay unknown.
    reported_usage: dict[str,int] = Field(default_factory=dict,max_length=12)
    usage_incomplete: bool = False


class RelatedDocument(Contract):
    analysis_id: UUID
    relation: Literal['opening','annex','rectification','supplement']
    note: str = Field(min_length=1,max_length=1000)
    recorded_at: datetime
    # Relationships are explicit proposals; never silently replace content.
    applied: Literal[False] = False


class PipelineManifest(Contract):
    version: Literal['edital/universal/6'] = PIPELINE_VERSION
    source: DocumentSummary
    status: PipelineStatus = 'not_started'
    phase: Literal['ingest','layout','inventory','selection','disciplines','program','evidence','review','result'] = 'ingest'
    inventory: InventoryState
    selected_role_id: str | None = Field(default=None,max_length=64)
    scopes: dict[str,ContentScope] = Field(default_factory=dict,max_length=500)
    budget: ProcessingBudget = Field(default_factory=ProcessingBudget)
    related_documents: list[RelatedDocument] = Field(default_factory=list,max_length=30)
    error_kind: str | None = Field(default=None,max_length=80)
    retry_at: datetime | None = None
