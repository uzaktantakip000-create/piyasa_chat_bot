"""add_performance_indexes_session15

Revision ID: c0f071ac6aaa
Revises: fe686589d4eb
Create Date: 2025-11-01 18:13:20.780165

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0f071ac6aaa'
down_revision: Union[str, Sequence[str], None] = 'fe686589d4eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add performance indexes for Session 15.

    Target queries:
    - Bot.is_enabled filter (used every tick)
    - Chat.is_enabled filter (used every tick)
    - Setting.key lookup (used frequently)

    Expected impact: Faster bot/chat selection, faster settings access.
    """
    # Bot is_enabled index
    op.create_index(
        'ix_bots_is_enabled',
        'bots',
        ['is_enabled'],
        unique=False
    )

    # Chat is_enabled index
    op.create_index(
        'ix_chats_is_enabled',
        'chats',
        ['is_enabled'],
        unique=False
    )

    # Setting key index (for fast settings lookup)
    op.create_index(
        'ix_settings_key',
        'settings',
        ['key'],
        unique=False
    )


def downgrade() -> None:
    """Remove performance indexes"""
    op.drop_index('ix_settings_key', table_name='settings')
    op.drop_index('ix_chats_is_enabled', table_name='chats')
    op.drop_index('ix_bots_is_enabled', table_name='bots')
