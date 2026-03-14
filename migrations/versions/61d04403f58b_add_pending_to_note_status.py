"""add_pending_to_note_status

Revision ID: 61d04403f58b
Revises: 3e58043c58cf
Create Date: 2026-02-08 12:32:03.962163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61d04403f58b'
down_revision: Union[str, Sequence[str], None] = '3e58043c58cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'pending' value to the note_status PostgreSQL enum."""
    op.execute("ALTER TYPE note_status ADD VALUE IF NOT EXISTS 'pending'")


def downgrade() -> None:
    """Cannot remove enum values in PostgreSQL; no-op."""
    pass
