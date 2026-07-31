"""ORM models package.

TEACHING NOTE — why import models here:
A model's table is only registered on `Base.metadata` when its module is
*imported*. Importing them all here gives the rest of the codebase (and
Alembic's env.py) a single import — `import app.models` — that guarantees
every table is known before `create_all` or migration autogeneration runs.
Forgetting this import is the #1 cause of "Alembic generated an empty
migration".
"""

from app.models.match import Match, MatchStatus
from app.models.message import Message
from app.models.posting import Posting, PostingCategory, PostingKind
from app.models.swipe import Swipe, SwipeDirection
from app.models.user import User

__all__ = [
    "Match",
    "MatchStatus",
    "Message",
    "Posting",
    "PostingCategory",
    "PostingKind",
    "Swipe",
    "SwipeDirection",
    "User",
]
