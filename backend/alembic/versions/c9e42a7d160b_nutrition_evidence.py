"""Add nullable nutrition provenance; retain all existing numeric history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'c9e42a7d160b'
down_revision = 'a81c9d37e502'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('meal_items', sa.Column('nutrition_evidence', postgresql.JSONB(), nullable=True))
    op.add_column('planned_foods', sa.Column('nutrition_evidence', postgresql.JSONB(), nullable=True))
    op.add_column('meals', sa.Column('source_reference', postgresql.JSONB(), nullable=True))
    op.add_column('nutrition_goals', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('nutrition_goals', sa.Column('confirmed_fields', postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column('nutrition_goals', 'confirmed_fields')
    op.drop_column('nutrition_goals', 'confirmed_at')
    op.drop_column('meals', 'source_reference')
    op.drop_column('meal_items', 'nutrition_evidence')
    op.drop_column('planned_foods', 'nutrition_evidence')
