"""Declared source kinds and durable bounded text observations.

Revision ID: 6f12b8e4a903
Revises: 84d2a71ef309
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='6f12b8e4a903'
down_revision='84d2a71ef309'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('contest_sources',sa.Column('source_kind',sa.String(),nullable=False,server_default='unknown'))
    op.create_check_constraint(op.f('ck_contest_sources_source_kind'),'contest_sources',
        "source_kind IN ('unknown','official_page','board','official_pdf','rectification','announcement','result','calendar')")
    op.create_table('contest_source_versions',
        sa.Column('id',sa.Uuid(),nullable=False),sa.Column('user_id',sa.Uuid(),nullable=False),
        sa.Column('source_id',sa.Uuid(),nullable=False),sa.Column('previous_id',sa.Uuid(),nullable=True),
        sa.Column('claim_token',sa.Uuid(),nullable=True),sa.Column('content_hash',sa.String(),nullable=False),
        sa.Column('hash_basis',sa.String(),nullable=False),sa.Column('snapshot_text',sa.Text(),nullable=False),
        sa.Column('partial',sa.Boolean(),nullable=False),sa.Column('official',sa.Boolean(),nullable=False),
        sa.Column('detected_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('details',postgresql.JSONB(),nullable=False),sa.Column('impact',postgresql.JSONB(),nullable=False),
        sa.Column('dates',postgresql.JSONB(),nullable=False),
        sa.PrimaryKeyConstraint('id',name=op.f('pk_contest_source_versions')),
        sa.UniqueConstraint('user_id','source_id','id',name=op.f('uq_contest_source_versions_user_id_source_id_id')),
        sa.UniqueConstraint('user_id','source_id','claim_token',name=op.f('uq_contest_source_versions_user_id_source_id_claim_token')),
        sa.ForeignKeyConstraint(['user_id'],['users.id'],name=op.f('fk_contest_source_versions_user_id_users'),ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id','source_id'],['contest_sources.user_id','contest_sources.id'],name=op.f('fk_contest_source_versions_user_id_contest_sources'),ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id','source_id','previous_id'],['contest_source_versions.user_id','contest_source_versions.source_id','contest_source_versions.id'],name=op.f('fk_contest_source_versions_user_id_contest_source_versions'),ondelete='RESTRICT'),
        sa.CheckConstraint('char_length(snapshot_text) <= 200000',name=op.f('ck_contest_source_versions_snapshot_bound')),
        sa.CheckConstraint("hash_basis IN ('page_text','document_bytes','legacy_snapshot')",name=op.f('ck_contest_source_versions_hash_basis')))
    op.create_index(op.f('ix_contest_source_versions_user_id'),'contest_source_versions',['user_id'])
    op.create_index('ix_contest_versions_owner_source_detected','contest_source_versions',['user_id','source_id','detected_at','id'])
    # Only the latest snapshot exists in legacy storage. Do not invent older versions.
    op.execute("""INSERT INTO contest_source_versions
        (id,user_id,source_id,previous_id,claim_token,content_hash,hash_basis,snapshot_text,partial,official,detected_at,details,impact,dates)
        SELECT gen_random_uuid(),user_id,id,NULL,NULL,content_hash,'legacy_snapshot',left(snapshot,200000),
            char_length(snapshot)>=200000,trust='OFFICIAL',coalesce(last_checked,updated_at,created_at),
            jsonb_build_object('legacy',true,'title',title,'url',url,'etag',etag,'last_modified',modified,
                'source_kind','unknown','original_available',false), '{}'::jsonb,'[]'::jsonb
        FROM contest_sources WHERE content_hash IS NOT NULL AND content_hash<>''""")
    op.add_column('contest_updates',sa.Column('version_id',sa.Uuid(),nullable=True))
    op.create_foreign_key(op.f('fk_contest_updates_user_id_contest_source_versions'),'contest_updates','contest_source_versions',
        ['user_id','source_id','version_id'],['user_id','source_id','id'],ondelete='RESTRICT')


def downgrade():
    op.drop_constraint(op.f('fk_contest_updates_user_id_contest_source_versions'),'contest_updates',type_='foreignkey')
    op.drop_column('contest_updates','version_id')
    op.drop_index('ix_contest_versions_owner_source_detected',table_name='contest_source_versions')
    op.drop_index(op.f('ix_contest_source_versions_user_id'),table_name='contest_source_versions')
    op.drop_table('contest_source_versions')
    op.drop_constraint(op.f('ck_contest_sources_source_kind'),'contest_sources',type_='check')
    op.drop_column('contest_sources','source_kind')
