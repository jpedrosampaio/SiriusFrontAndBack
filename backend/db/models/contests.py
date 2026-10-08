from datetime import datetime
from uuid import UUID
from sqlalchemy import CheckConstraint,DateTime,ForeignKeyConstraint,Index,Text,UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped,mapped_column
from db.base import Base,Identity,Timestamps
from db.models.planning import Owned


class ContestSource(Identity,Owned,Timestamps,Base):
    __tablename__='contest_sources'
    program_id: Mapped[UUID]
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str]
    title: Mapped[str]
    trust: Mapped[str]
    provider: Mapped[str]
    source_kind: Mapped[str] = mapped_column(default='unknown',server_default='unknown')
    terms_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_poll: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None]
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(default='pending')
    failures: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None]
    snapshot: Mapped[str] = mapped_column(Text,default='')
    content_hash: Mapped[str | None]
    etag: Mapped[str | None]
    modified: Mapped[str | None]
    __table_args__=(UniqueConstraint('user_id','id'),UniqueConstraint('user_id','program_id','url_hash'),
        CheckConstraint("source_kind IN ('unknown','official_page','board','official_pdf','rectification','announcement','result','calendar')",name='source_kind'),
        ForeignKeyConstraint(['user_id','program_id'],['study_programs.user_id','study_programs.id'],ondelete='RESTRICT'),
        Index('ix_contest_sources_enabled_next','enabled','next_poll'))


class ContestUpdate(Identity,Owned,Base):
    __tablename__='contest_updates'
    program_id: Mapped[UUID]
    source_id: Mapped[UUID]
    version_id: Mapped[UUID | None]
    source: Mapped[str]
    title: Mapped[str]
    url: Mapped[str] = mapped_column(Text)
    document_url: Mapped[str | None] = mapped_column(Text)
    document_type: Mapped[str]
    content_hash: Mapped[str]
    hash_basis: Mapped[str]
    source_type: Mapped[str]
    official: Mapped[bool]
    published_at: Mapped[str | None]
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str]
    changes: Mapped[dict | None] = mapped_column(JSONB)
    text_extraction: Mapped[str | None]
    text_partial: Mapped[bool | None]
    __table_args__=(UniqueConstraint('user_id','source_id','content_hash'),
        ForeignKeyConstraint(['user_id','source_id','version_id'],['contest_source_versions.user_id','contest_source_versions.source_id','contest_source_versions.id'],ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','source_id'],['contest_sources.user_id','contest_sources.id'],ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','program_id'],['study_programs.user_id','study_programs.id'],ondelete='RESTRICT'),
        Index('ix_contest_updates_owner_program_detected','user_id','program_id','detected_at'))


class ContestSourceVersion(Identity,Owned,Base):
    __tablename__='contest_source_versions'
    source_id: Mapped[UUID]
    previous_id: Mapped[UUID | None]
    claim_token: Mapped[UUID | None]
    content_hash: Mapped[str]
    hash_basis: Mapped[str]
    snapshot_text: Mapped[str] = mapped_column(Text)
    partial: Mapped[bool] = mapped_column(default=False)
    official: Mapped[bool]
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict] = mapped_column(JSONB,default=dict)
    impact: Mapped[dict] = mapped_column(JSONB,default=dict)
    dates: Mapped[list] = mapped_column(JSONB,default=list)
    __table_args__=(UniqueConstraint('user_id','source_id','id'),UniqueConstraint('user_id','source_id','claim_token'),
        ForeignKeyConstraint(['user_id','source_id'],['contest_sources.user_id','contest_sources.id'],ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','source_id','previous_id'],['contest_source_versions.user_id','contest_source_versions.source_id','contest_source_versions.id'],ondelete='RESTRICT'),
        CheckConstraint('char_length(snapshot_text) <= 200000',name='snapshot_bound'),
        CheckConstraint("hash_basis IN ('page_text','page_text_and_links','document_bytes','legacy_snapshot')",name='hash_basis'),
        Index('ix_contest_versions_owner_source_detected','user_id','source_id','detected_at','id'))


class ContestHostLimit(Base):
    __tablename__='contest_host_limits'
    host: Mapped[str] = mapped_column(primary_key=True)
    next_poll: Mapped[datetime] = mapped_column(DateTime(timezone=True))
