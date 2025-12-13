"""add_quota_to_campaigns

Revision ID: 004_add_quota
Revises: 003_add_bid_unique
Create Date: 2025-12-13

This migration adds a quota field to campaigns table.
The quota stores the initial product stock at campaign creation time,
so that winner determination works correctly after settlement
(when product.stock has been decremented to 0).

Bug fix: After settlement, product.stock becomes 0, causing all users
to show as "未得標" because rank <= 0 is always false.
Solution: Use campaign.quota instead of product.stock for winner determination.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_quota'
down_revision: Union[str, None] = '003_add_bid_unique'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add quota column as nullable first
    op.add_column('campaigns', sa.Column('quota', sa.Integer(), nullable=True,
                  comment='得標名額 (創建時從 product.stock 快照)'))

    # Backfill existing campaigns with product stock
    op.execute("""
        UPDATE campaigns c
        SET quota = (SELECT p.stock FROM products p WHERE p.product_id = c.product_id)
    """)

    # Make quota non-nullable after backfill
    op.alter_column('campaigns', 'quota', nullable=False)


def downgrade() -> None:
    op.drop_column('campaigns', 'quota')
