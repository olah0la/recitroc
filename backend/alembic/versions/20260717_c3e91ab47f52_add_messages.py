"""add messages

Revision ID: c3e91ab47f52
Revises: a8f04dc37e91
Create Date: 2026-07-17

TEACHING NOTE — the composite (match_id, id) index exists for exactly one
query: the polling fetch "messages of match M with id > cursor". Indexes
are designed from the queries backward, never added speculatively.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e91ab47f52"
down_revision: Union[str, None] = "a8f04dc37e91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("sender_email", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name=op.f("fk_messages_matches_match_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_email"],
            ["users.email"],
            name=op.f("fk_messages_users_sender_email"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index("ix_messages_match_id_id", "messages", ["match_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_messages_match_id_id", table_name="messages")
    op.drop_table("messages")
