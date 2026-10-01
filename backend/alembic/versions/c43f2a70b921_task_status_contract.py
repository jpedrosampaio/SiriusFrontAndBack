"""Preserve the existing todo/in_progress/done Kanban contract."""
from alembic import op

revision = 'c43f2a70b921'
down_revision = '65872ffe48c9'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f('ck_task_instances_status'), 'task_instances', type_='check')
    op.create_check_constraint('status', 'task_instances', "status IN ('todo','in_progress','done')")


def downgrade():
    op.drop_constraint(op.f('ck_task_instances_status'), 'task_instances', type_='check')
    op.create_check_constraint('status', 'task_instances', "status IN ('pending','done','skipped')")
