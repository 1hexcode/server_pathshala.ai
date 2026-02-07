"""add super_admin role

Revision ID: 43a07b889584
Revises: 79eeba37b5d6
Create Date: 2026-02-07 10:23:14.526371

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43a07b889584'
down_revision: Union[str, Sequence[str], None] = '79eeba37b5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add super_admin to user_role enum."""
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'super_admin'")


def downgrade() -> None:
    """Cannot remove enum values in PostgreSQL, recreate would be needed."""
    pass
