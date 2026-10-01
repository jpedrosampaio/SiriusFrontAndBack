from datetime import datetime
from uuid import UUID
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base, Identity, Timestamps
from db.models.planning import Owned


class FileRecord(Identity, Owned, Timestamps, Base):
    __tablename__ = 'files'
    storage_provider: Mapped[str]
    storage_key: Mapped[str | None]
    filename: Mapped[str]
    mime_type: Mapped[str]
    size_bytes: Mapped[int]
    sha256: Mapped[str]
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (UniqueConstraint('user_id','id'), UniqueConstraint('user_id','sha256'),
        CheckConstraint('size_bytes >= 0', name='size'),
        CheckConstraint("storage_key IS NOT NULL OR storage_provider = 'metadata_only'", name='storage_reference'))


class EditalAnalysis(Identity, Owned, Timestamps, Base):
    __tablename__ = 'edital_analyses'
    file_id: Mapped[UUID | None]
    content_hash: Mapped[str]
    status: Mapped[str]
    analysis_version: Mapped[str]
    structured_payload: Mapped[dict] = mapped_column(JSONB)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str | None]
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    from_cache: Mapped[bool] = mapped_column(default=False)
    pages: Mapped[list] = mapped_column(JSONB, default=list)
    revision: Mapped[int] = mapped_column(default=0)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','file_id'], ['files.user_id','files.id'], ondelete='RESTRICT'),
        Index('ix_analysis_owner_hash_version','user_id','content_hash','analysis_version'))


class RagSource(Identity, Owned, Timestamps, Base):
    __tablename__ = 'rag_sources'
    file_id: Mapped[UUID | None]
    analysis_id: Mapped[UUID | None]
    notebook_id: Mapped[UUID | None]
    generation: Mapped[str]
    source_type: Mapped[str]
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','file_id'], ['files.user_id','files.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['user_id','analysis_id'], ['edital_analyses.user_id','edital_analyses.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['user_id','notebook_id'], ['study_notebooks.user_id','study_notebooks.id'], ondelete='CASCADE'),
        CheckConstraint('num_nonnulls(file_id, analysis_id, notebook_id) = 1', name='one_source'))


class EditalJob(Identity, Owned, Timestamps, Base):
    __tablename__ = 'edital_jobs'
    filename: Mapped[str]
    storage_provider: Mapped[str]
    storage_key: Mapped[str | None]
    content_hash: Mapped[str]
    force: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(default='queued')
    phase: Mapped[str] = mapped_column(default='Na fila')
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analysis_id: Mapped[UUID | None] = mapped_column(ForeignKey('edital_analyses.id',ondelete='SET NULL'))
    __table_args__ = (Index('ix_edital_jobs_status_created','status','created_at'),
        ForeignKeyConstraint(['user_id','analysis_id'],['edital_analyses.user_id','edital_analyses.id']),
        CheckConstraint("status IN ('queued','running','failed','completed')",name='status'))


class RagChunk(Identity, Owned, Base):
    __tablename__ = 'rag_chunks'
    source_id: Mapped[UUID]
    chunk_index: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str]
    terms: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (ForeignKeyConstraint(['user_id','source_id'], ['rag_sources.user_id','rag_sources.id'], ondelete='CASCADE'),
        UniqueConstraint('user_id','source_id','chunk_index'), Index('ix_rag_owner_hash','user_id','content_hash'),
        Index('ix_rag_terms', 'terms', postgresql_using='gin'))
