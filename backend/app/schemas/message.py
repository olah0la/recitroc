"""Message schemas.

TEACHING NOTE — validation lives at the EDGE: the body's length and
non-emptiness are enforced here, in the request schema, so no deeper
layer (crud, model) ever sees an invalid message. By the time data
crosses the schema boundary, it is known-good.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class MessageCreate(BaseModel):
    # strip_whitespace runs BEFORE min_length, so "   " is rejected as
    # empty rather than sneaking through as three spaces.
    body: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    sender_email: str
    body: str
    created_at: datetime
    # NULL until the recipient marks the thread read; the SENDER polls
    # this to render read receipts.
    read_at: datetime | None
