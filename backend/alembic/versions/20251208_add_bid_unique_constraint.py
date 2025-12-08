"""add_bid_unique_constraint

Revision ID: 003_add_bid_unique
Revises: 002_add_is_admin
Create Date: 2025-12-08

This migration adds a unique constraint on (campaign_id, user_id) for the bids table.
This enables PostgreSQL UPSERT (INSERT ... ON CONFLICT) for atomic bid operations,
eliminating race conditions in high-concurrency scenarios.

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '003_add_bid_unique'
down_revision: Union[str, None] = '002_add_is_admin'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, remove any duplicate bids (keep the one with highest score)
    # This handles existing data that might violate the unique constraint
    op.execute("""
        DELETE FROM bids b1
        USING bids b2
        WHERE b1.campaign_id = b2.campaign_id
          AND b1.user_id = b2.user_id
          AND b1.score < b2.score
    """)

    # Drop the existing non-unique index
    op.drop_index('idx_bids_campaign_user', table_name='bids')

    # Create unique constraint (this also creates an index)
    op.create_unique_constraint(
        'uq_bids_campaign_user',
        'bids',
        ['campaign_id', 'user_id']
    )


def downgrade() -> None:
    # Drop the unique constraint
    op.drop_constraint('uq_bids_campaign_user', 'bids', type_='unique')

    # Recreate the non-unique index
    op.create_index('idx_bids_campaign_user', 'bids', ['campaign_id', 'user_id'], unique=False)
