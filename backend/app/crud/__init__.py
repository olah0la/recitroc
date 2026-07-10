"""Data-access layer.

TEACHING NOTE — why a CRUD/repository layer exists:
Endpoints translate HTTP <-> Python; this layer talks to the database.
Keeping them separate means:
- queries are reusable (a CLI script or background job can call
  `crud.user.create` without faking an HTTP request),
- endpoints stay small and readable,
- tests can exercise data logic without spinning up the API.
Nothing in this package may import from `app.api` — dependencies point
inward only (api -> crud -> models).
"""

from app.crud import item, user

__all__ = ["item", "user"]
