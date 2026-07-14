"""postings replace items and listings

Revision ID: b2d84fa61c53
Revises: e7a31f5c9d02
Create Date: 2026-07-14

TEACHING NOTE — a destructive consolidation, done deliberately:
`items` (owned, no geo) and `listings` (geo, no owner) were prototypes;
`postings` (owned AND geolocated, with kind/category) replaces both. The
RT-2 ticket originally planned to carry listings over as offers, but a
posting REQUIRES an owner and listings never had one — there is nothing
truthful to backfill. Dropping dev-only data beats inventing owners.
The downgrade restores the SCHEMAS of both old tables, not their rows:
write that in the docstring whenever a migration cannot round-trip data,
so nobody discovers it during an incident.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2d84fa61c53"
down_revision: Union[str, None] = "e7a31f5c9d02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Defined once, reused by upgrade AND downgrade. create_table() creates
# postgres ENUM types automatically; dropping them back out is manual —
# see downgrade().
posting_kind = sa.Enum("offer", "need", name="postingkind")
posting_category = sa.Enum("goods", "service", name="postingcategory")


def upgrade() -> None:
    op.drop_index(op.f("ix_items_owner_email"), table_name="items")
    op.drop_index(op.f("ix_items_title"), table_name="items")
    op.drop_table("items")
    op.drop_index(op.f("ix_listings_city"), table_name="listings")
    op.drop_table("listings")

    op.create_table(
        "postings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_email", sa.String(length=255), nullable=False),
        sa.Column("kind", posting_kind, nullable=False),
        sa.Column("category", posting_category, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # JSONB on postgres (the model uses a JSON->JSONB variant).
        sa.Column("tags", postgresql.JSONB(), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_email"],
            ["users.email"],
            name=op.f("fk_postings_users_owner_email"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_postings")),
    )
    op.create_index(
        op.f("ix_postings_owner_email"), "postings", ["owner_email"], unique=False
    )
    op.create_index(op.f("ix_postings_city"), "postings", ["city"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_postings_city"), table_name="postings")
    op.drop_index(op.f("ix_postings_owner_email"), table_name="postings")
    op.drop_table("postings")
    # drop_table does NOT drop the enum types it left behind — without
    # this, re-running upgrade would fail with "type already exists".
    posting_kind.drop(op.get_bind(), checkfirst=True)
    posting_category.drop(op.get_bind(), checkfirst=True)

    # Restore the old tables' schemas (their data is gone for good).
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_email", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_email"],
            ["users.email"],
            name=op.f("fk_items_users_owner_email"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_items")),
    )
    op.create_index(op.f("ix_items_owner_email"), "items", ["owner_email"])
    op.create_index(op.f("ix_items_title"), "items", ["title"])

    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listings")),
    )
    op.create_index(op.f("ix_listings_city"), "listings", ["city"])
