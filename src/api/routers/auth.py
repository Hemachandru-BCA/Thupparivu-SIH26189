"""
routers/auth.py
---------------
Auth router: POST /api/auth/token.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.auth import (
    LoginRequest,
    login as _login,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token")
def auth_token(body: LoginRequest) -> dict:
    """Authenticate with username + password and return a JWT bearer token.

    Body: {"username": "...", "password": "..."}
    """
    return _login(body)