"""create_initial_schema

Revision ID: 279cc9eb6db1
Revises: 
Create Date: 2026-10-14 22:45:32.690539

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.models import Base

# revision identifiers, used by Alembic.
revision: str = '279cc9eb6db1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all schema tables for MindScan (PostgreSQL / SQLite)."""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Drop all MindScan tables."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
