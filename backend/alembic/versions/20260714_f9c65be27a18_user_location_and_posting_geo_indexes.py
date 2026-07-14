"""user location + posting lat/lng indexes

Revision ID: f9c65be27a18
Revises: b2d84fa61c53
Create Date: 2026-07-14

TEACHING NOTE — the lat/lng indexes exist for the nearby query's bounding
box (see crud/posting.py list_nearby): `latitude BETWEEN x AND y` is a
classic range scan, exactly what a b-tree accelerates. Two separate
single-column b-trees are enough at this scale — postgres bitmap-ANDs
them; a real spatial index (PostGIS GiST) is the documented escape hatch
if this ever measures slow, not the starting point.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9c65be27a18"
down_revision: Union[str, None] = "b2d84fa61c53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # All nullable: existing users simply have no location yet.
    op.add_column("users", sa.Column("city", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("country", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("longitude", sa.Float(), nullable=True))

    op.create_index(op.f("ix_postings_latitude"), "postings", ["latitude"])
    op.create_index(op.f("ix_postings_longitude"), "postings", ["longitude"])


def downgrade() -> None:
    op.drop_index(op.f("ix_postings_longitude"), table_name="postings")
    op.drop_index(op.f("ix_postings_latitude"), table_name="postings")

    op.drop_column("users", "longitude")
    op.drop_column("users", "latitude")
    op.drop_column("users", "country")
    op.drop_column("users", "city")
