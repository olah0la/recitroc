"""Match schemas.

TEACHING NOTE — a PER-CALLER shape: the database stores a symmetric
(user_a, user_b) pair, but each participant wants to see "the OTHER
person and OUR two postings, from my side". The endpoint reshapes the
row for whoever is asking — same data, two honest views.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import MatchStatus
from app.schemas.posting import PostingRead
from app.schemas.user import UserRead


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: MatchStatus
    created_at: datetime

    partner: UserRead
    # Nullable: a posting may have been deleted since the match was made
    # (the FK is SET NULL) — the match itself lives on.
    my_posting: PostingRead | None
    their_posting: PostingRead | None
