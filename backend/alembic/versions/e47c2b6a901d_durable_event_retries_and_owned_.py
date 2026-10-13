"""durable event retries and owned delivery outbox

Revision ID: e47c2b6a901d
Revises: c9e42a7d160b
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e47c2b6a901d'
down_revision: Union[str, Sequence[str], None] = 'c9e42a7d160b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The composite referenced key must exist before the transport outbox.
    op.create_unique_constraint(op.f('uq_ai_events_user_id_id'), 'ai_events', ['user_id', 'id'])
    op.create_table('ai_event_deliveries',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('channel', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('lease_token', sa.Uuid(), nullable=True),
    sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('provider_receipt', sa.String(), nullable=True),
    sa.Column('last_error', sa.String(), nullable=True),
    sa.Column('recipient_link_id', sa.Uuid(), nullable=True),
    sa.Column('recipient_chat_id', sa.BigInteger(), nullable=True),
    sa.Column('history', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("channel IN ('in_app','telegram')", name=op.f('ck_ai_event_deliveries_channel')),
    sa.CheckConstraint("status IN ('pending','processing','available','delivered','failed','cancelled','uncertain')", name=op.f('ck_ai_event_deliveries_status')),
    sa.CheckConstraint('attempts >= 0 AND attempts <= 8', name=op.f('ck_ai_event_deliveries_attempts')),
    sa.ForeignKeyConstraint(['user_id', 'event_id'], ['ai_events.user_id', 'ai_events.id'], name=op.f('fk_ai_event_deliveries_user_id_ai_events'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_ai_event_deliveries_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_event_deliveries')),
    sa.UniqueConstraint('user_id', 'event_id', 'channel', name=op.f('uq_ai_event_deliveries_user_id_event_id_channel'))
    )
    op.create_index(op.f('ix_ai_event_deliveries_user_id'), 'ai_event_deliveries', ['user_id'], unique=False)
    op.create_index('ix_event_delivery_available', 'ai_event_deliveries', ['status', 'available_at', 'created_at'], unique=False)
    op.add_column('ai_events', sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('ai_events', sa.Column('attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('ai_events', sa.Column('last_error', sa.String(), nullable=True))
    op.add_column('ai_events', sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_events_available', 'ai_events', ['status', 'available_at', 'created_at'], unique=False)
    op.create_check_constraint(op.f('ck_ai_events_attempts'), 'ai_events', 'attempts >= 0 AND attempts <= 8')
    op.add_column('telegram_updates', sa.Column('binding_id', sa.Uuid(), nullable=True))
    op.add_column('telegram_updates', sa.Column('delivery_status', sa.String(), server_default='pending', nullable=False))
    op.add_column('telegram_updates', sa.Column('delivery_attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('telegram_updates', sa.Column('next_delivery_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('telegram_updates', sa.Column('delivery_error', sa.String(), nullable=True))
    op.add_column('telegram_updates', sa.Column('provider_receipt', sa.String(), nullable=True))
    op.add_column('telegram_updates', sa.Column('delivery_history', postgresql.JSONB(), server_default='[]', nullable=False))
    op.create_check_constraint(op.f('ck_telegram_updates_delivery_attempts'), 'telegram_updates', 'delivery_attempts >= 0 AND delivery_attempts <= 8')
    op.create_check_constraint(op.f('ck_telegram_updates_delivery_status'), 'telegram_updates', "delivery_status IN ('pending','processing','delivered','failed','cancelled','uncertain')")
    op.create_index('ix_telegram_delivery_ready', 'telegram_updates', ['delivery_status','next_delivery_at','lease_until'])
    # Add a status for already-confirmed historical receipts without changing their replies/timestamps.
    op.execute(sa.text("UPDATE telegram_updates SET delivery_status='delivered' WHERE delivered_at IS NOT NULL"))


def downgrade() -> None:
    connection=op.get_bind()
    if connection.execute(sa.text('SELECT 1 FROM ai_event_deliveries LIMIT 1')).first() or connection.execute(
        sa.text('SELECT 1 FROM telegram_updates WHERE delivery_attempts > 0 LIMIT 1')).first() or connection.execute(
        sa.text('SELECT 1 FROM ai_events WHERE attempts > 0 OR processed_at IS NOT NULL LIMIT 1')).first():
        raise RuntimeError('Downgrade would discard delivery audit history.')
    op.drop_index('ix_telegram_delivery_ready', table_name='telegram_updates')
    op.drop_constraint(op.f('ck_telegram_updates_delivery_status'), 'telegram_updates', type_='check')
    op.drop_constraint(op.f('ck_telegram_updates_delivery_attempts'), 'telegram_updates', type_='check')
    op.drop_column('telegram_updates', 'delivery_error')
    op.drop_column('telegram_updates', 'provider_receipt')
    op.drop_column('telegram_updates', 'delivery_history')
    op.drop_column('telegram_updates', 'next_delivery_at')
    op.drop_column('telegram_updates', 'delivery_attempts')
    op.drop_column('telegram_updates', 'delivery_status')
    op.drop_column('telegram_updates', 'binding_id')
    op.drop_constraint(op.f('ck_ai_events_attempts'), 'ai_events', type_='check')
    op.drop_index('ix_events_available', table_name='ai_events')
    op.drop_column('ai_events', 'processed_at')
    op.drop_column('ai_events', 'last_error')
    op.drop_column('ai_events', 'attempts')
    op.drop_column('ai_events', 'available_at')
    op.drop_index('ix_event_delivery_available', table_name='ai_event_deliveries')
    op.drop_index(op.f('ix_ai_event_deliveries_user_id'), table_name='ai_event_deliveries')
    op.drop_table('ai_event_deliveries')
    op.drop_constraint(op.f('uq_ai_events_user_id_id'), 'ai_events', type_='unique')
