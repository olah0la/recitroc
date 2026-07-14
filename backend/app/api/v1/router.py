"""Aggregates all v1 endpoint routers into one.

TEACHING NOTE — routers compose like Lego: each resource defines its own
APIRouter (with its own prefix and tags), and this module stitches them
together. `main.py` then mounts this single router under /v1. Adding a new
resource = new file in endpoints/ + one include_router line here.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, postings, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(postings.router)
