"""add swipes

Revision ID: d61e2b9a4c70
Revises: f9c65be27a18
Create Date: 2026-07-14

TEACHING NOTE — the composite UNIQUE constraint doubles as an index: the
deck query's NOT EXISTS anti-join probes exactly (swiper_email,
posting_id), so the constraint that guarantees one-verdict-per-posting
also makes that probe an index lookup. One definition, two jobs.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d61e2b9a4c70"
down_revision: Union[str, None] = "f9c65be27a18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

swipe_direction = sa.Enum("like", "pass", name="swipedirection")


def upgrade() -> None:
    op.create_table(
        "swipes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("swiper_email", sa.String(length=255), nullable=False),
        sa.Column("posting_id", sa.Integer(), nullable=False),
        sa.Column("direction", swipe_direction, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["swiper_email"],
            ["users.email"],
            name=op.f("fk_swipes_users_swiper_email"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["posting_id"],
            ["postings.id"],
            name=op.f("fk_swipes_postings_posting_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_swipes")),
        sa.UniqueConstraint("swiper_email", "posting_id", name="uq_swipes_verdict"),
    )
    op.create_index(op.f("ix_swipes_swiper_email"), "swipes", ["swiper_email"])
    op.create_index(op.f("ix_swipes_posting_id"), "swipes", ["posting_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_swipes_posting_id"), table_name="swipes")
    op.drop_index(op.f("ix_swipes_swiper_email"), table_name="swipes")
    op.drop_table("swipes")
    swipe_direction.drop(op.get_bind(), checkfirst=True)
