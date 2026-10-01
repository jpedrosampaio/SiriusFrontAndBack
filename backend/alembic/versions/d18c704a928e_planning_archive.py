"""Preserve completion evidence when planning templates are deleted."""
from alembic import op
import sqlalchemy as sa

revision = 'd18c704a928e'
down_revision = 'b64cd6f47873'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('tasks', 'habits'):
        op.add_column(table, sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE task_instances SET status = CASE WHEN completed THEN 'done' WHEN status = 'done' THEN 'todo' ELSE status END")
    op.create_check_constraint(op.f('ck_task_instances_completion_status'), 'task_instances', "completed = (status = 'done')")


def downgrade():
    op.drop_constraint(op.f('ck_task_instances_completion_status'), 'task_instances', type_='check')
    for table in ('habits', 'tasks'):
        op.drop_column(table, 'archived_at')
