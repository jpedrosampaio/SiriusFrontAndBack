"""Owned question forensic suggestions; original attempts remain unchanged."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='b73a16ce9024'
down_revision='6f12b8e4a903'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('question_insights',
        sa.Column('id',sa.Uuid(),nullable=False),sa.Column('user_id',sa.Uuid(),nullable=False),
        sa.Column('program_id',sa.Uuid(),nullable=False),sa.Column('fingerprint',sa.String(),nullable=False),
        sa.Column('status',sa.String(),nullable=False),sa.Column('details',postgresql.JSONB(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id',name=op.f('pk_question_insights')),
        sa.ForeignKeyConstraint(['user_id'],['users.id'],name=op.f('fk_question_insights_user_id_users'),ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id','program_id'],['study_programs.user_id','study_programs.id'],name=op.f('fk_question_insights_user_id_study_programs'),ondelete='RESTRICT'),
        sa.UniqueConstraint('user_id','program_id','fingerprint',name=op.f('uq_question_insights_user_id_program_id_fingerprint')),
        sa.CheckConstraint("status IN ('active','dismissed','superseded')",name=op.f('ck_question_insights_status')))
    op.create_index(op.f('ix_question_insights_user_id'),'question_insights',['user_id'])
    op.create_index('ix_question_insights_owner_program_status','question_insights',['user_id','program_id','status'])


def downgrade():
    op.drop_index('ix_question_insights_owner_program_status',table_name='question_insights')
    op.drop_index(op.f('ix_question_insights_user_id'),table_name='question_insights')
    op.drop_table('question_insights')
