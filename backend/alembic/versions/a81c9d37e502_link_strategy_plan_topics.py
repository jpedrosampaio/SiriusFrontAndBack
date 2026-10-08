"""Optional owned topic identity for adaptive study blocks; legacy blocks retained."""
from alembic import op
import sqlalchemy as sa

revision = 'a81c9d37e502'
down_revision = 'b73a16ce9024'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('study_plan_entries', sa.Column('topic_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(op.f('fk_study_plan_entries_user_id_study_topics'),
        'study_plan_entries', 'study_topics', ['user_id', 'topic_id'], ['user_id', 'id'], ondelete='RESTRICT')


def downgrade():
    op.drop_constraint(op.f('fk_study_plan_entries_user_id_study_topics'), 'study_plan_entries', type_='foreignkey')
    op.drop_column('study_plan_entries', 'topic_id')
