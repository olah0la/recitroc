"""add matches

Revision ID: a8f04dc37e91
Revises: d61e2b9a4c70
Create Date: 2026-07-14

TEACHING NOTE — note the two DIFFERENT delete rules in one table:
users cascade (no user, no match) but postings SET NULL (the match — a
human connection — outlives the posting that sparked it). Every FK's
ondelete is a product decision, not boilerplate.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8f04dc37e91"
down_revision: Union[str, None] = "d61e2b9a4c70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

match_status = sa.Enum("active", "archived", name="matchstatus")


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_a_email", sa.String(length=255), nullable=False),
        sa.Column("user_b_email", sa.String(length=255), nullable=False),
        sa.Column("posting_a_id", sa.Integer(), nullable=True),
        sa.Column("posting_b_id", sa.Integer(), nullable=True),
        sa.Column("status", match_status, server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_a_email"],
            ["users.email"],
            name=op.f("fk_matches_users_user_a_email"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_b_email"],
            ["users.email"],
            name=op.f("fk_matches_users_user_b_email"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["posting_a_id"],
            ["postings.id"],
            name=op.f("fk_matches_postings_posting_a_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["posting_b_id"],
            ["postings.id"],
            name=op.f("fk_matches_postings_posting_b_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matches")),
        sa.UniqueConstraint("user_a_email", "user_b_email", name="uq_matches_pair"),
        sa.CheckConstraint(
            "user_a_email < user_b_email", name=op.f("ck_matches_ordered_pair")
        ),
    )
    op.create_index(op.f("ix_matches_user_a_email"), "matches", ["user_a_email"])
    op.create_index(op.f("ix_matches_user_b_email"), "matches", ["user_b_email"])


def downgrade() -> None:
    op.drop_index(op.f("ix_matches_user_b_email"), table_name="matches")
    op.drop_index(op.f("ix_matches_user_a_email"), table_name="matches")
    op.drop_table("matches")
    match_status.drop(op.get_bind(), checkfirst=True)
