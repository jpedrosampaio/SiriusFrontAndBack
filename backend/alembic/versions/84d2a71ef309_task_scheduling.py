"""Optional civil task time and duration.

Revision ID: 84d2a71ef309
Revises: 126b856daebb
"""
from alembic import op
import sqlalchemy as sa

revision = '84d2a71ef309'
down_revision = '126b856daebb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tasks', sa.Column('scheduled_time', sa.Time(timezone=False), nullable=True))
    op.add_column('tasks', sa.Column('duration_minutes', sa.Integer(), nullable=True))
    op.create_check_constraint(op.f('ck_tasks_duration_minutes'), 'tasks', 'duration_minutes BETWEEN 5 AND 720')


def downgrade():
    op.drop_constraint(op.f('ck_tasks_duration_minutes'), 'tasks', type_='check')
    op.drop_column('tasks', 'duration_minutes')
    op.drop_column('tasks', 'scheduled_time')
