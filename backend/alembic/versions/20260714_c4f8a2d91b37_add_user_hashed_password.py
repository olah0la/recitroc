"""add user hashed_password

Revision ID: c4f8a2d91b37
Revises: abd5ed073b85
Create Date: 2026-07-14

TEACHING NOTE — adding a NOT NULL column to a table that may already have
rows is a two-step dance: first add it WITH a server_default (so existing
rows get a value and the NOT NULL constraint can be satisfied), then drop
the default (so future inserts must supply a real value). The backfilled
empty string is deliberately an *unusable* credential: bcrypt can never
verify against it, so pre-auth accounts simply cannot log in until they
get a password through a proper flow.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f8a2d91b37"
down_revision: Union[str, None] = "abd5ed073b85"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "hashed_password", sa.String(length=255), nullable=False, server_default=""
        ),
    )
    op.alter_column("users", "hashed_password", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "hashed_password")
