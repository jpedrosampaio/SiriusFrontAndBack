"""Owned incremental edital checkpoints and fenced job leases.

Revision ID: a61015ed902b
Revises: f13c8a7b902d
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a61015ed902b'
down_revision = 'f13c8a7b902d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('edital_jobs',sa.Column('lease_token',sa.Uuid(),nullable=True))
    op.create_unique_constraint(op.f('uq_edital_jobs_user_id_id'),'edital_jobs',['user_id','id'])
    op.create_table('edital_analysis_units',
        sa.Column('analysis_id',sa.Uuid(),nullable=False),
        sa.Column('job_id',sa.Uuid(),nullable=False),
        sa.Column('generation',sa.Uuid(),nullable=False),
        sa.Column('scope_key',sa.String(),nullable=False),
        sa.Column('unit_key',sa.String(),nullable=False),
        sa.Column('kind',sa.String(),nullable=False),
        sa.Column('status',sa.String(),nullable=False),
        sa.Column('source_blocks',postgresql.JSONB(),nullable=False),
        sa.Column('context_blocks',postgresql.JSONB(),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),
        sa.Column('provider_calls',sa.Integer(),nullable=False),
        sa.Column('available_at',sa.DateTime(timezone=True),server_default=sa.text('now()'),nullable=False),
        sa.Column('lease_token',sa.Uuid(),nullable=True),
        sa.Column('lease_until',sa.DateTime(timezone=True),nullable=True),
        sa.Column('result',postgresql.JSONB(),nullable=True),
        sa.Column('diagnostics',postgresql.JSONB(),nullable=False),
        sa.Column('finished_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('id',sa.Uuid(),nullable=False),
        sa.Column('user_id',sa.Uuid(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('now()'),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.text('now()'),nullable=False),
        sa.PrimaryKeyConstraint('id',name=op.f('pk_edital_analysis_units')),
        sa.UniqueConstraint('user_id','analysis_id','generation','scope_key','unit_key',name=op.f('uq_edital_analysis_units_user_id_analysis_id_generation_scope_key_unit_key')),
        sa.ForeignKeyConstraint(['user_id'],['users.id'],ondelete='CASCADE',name=op.f('fk_edital_analysis_units_user_id_users')),
        sa.ForeignKeyConstraint(['user_id','analysis_id'],['edital_analyses.user_id','edital_analyses.id'],ondelete='CASCADE',name=op.f('fk_edital_analysis_units_user_id_edital_analyses')),
        sa.ForeignKeyConstraint(['user_id','job_id'],['edital_jobs.user_id','edital_jobs.id'],ondelete='CASCADE',name=op.f('fk_edital_analysis_units_user_id_edital_jobs')),
        sa.CheckConstraint("kind IN ('inventory','scope','detail','verify')",name=op.f('ck_edital_analysis_units_kind')),
        sa.CheckConstraint("status IN ('pending','running','completed','failed','quota','waiting_provider','cancelled','split')",name=op.f('ck_edital_analysis_units_status')),
        sa.CheckConstraint('attempts BETWEEN 0 AND 3 AND provider_calls BETWEEN 0 AND 12',name=op.f('ck_edital_analysis_units_attempts')),
        sa.CheckConstraint('length(unit_key) = 64 AND length(scope_key) BETWEEN 1 AND 100',name=op.f('ck_edital_analysis_units_keys')),
        sa.CheckConstraint("status != 'completed' OR (result IS NOT NULL AND jsonb_typeof(result) = 'object' AND finished_at IS NOT NULL)",name=op.f('ck_edital_analysis_units_completed_result')),
        sa.CheckConstraint("status != 'running' OR (lease_token IS NOT NULL AND lease_until IS NOT NULL)",name=op.f('ck_edital_analysis_units_running_lease')),
    )
    op.create_index('ix_edital_analysis_units_user_id','edital_analysis_units',['user_id'])
    op.create_index('ix_edital_units_claim','edital_analysis_units',['status','available_at','created_at'])
    op.create_index('ix_edital_units_scope','edital_analysis_units',['user_id','analysis_id','generation','scope_key','status'])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS (SELECT 1 FROM edital_analysis_units)')).scalar():
        raise RuntimeError('Downgrade would erase edital checkpoints/history; archive through an approved retention process first.')
    op.drop_table('edital_analysis_units')
    op.drop_constraint(op.f('uq_edital_jobs_user_id_id'),'edital_jobs',type_='unique')
    op.drop_column('edital_jobs','lease_token')
