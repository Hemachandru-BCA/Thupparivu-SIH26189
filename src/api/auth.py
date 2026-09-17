"""
auth.py
-------
JWT-based authentication for SentinelGraph AI.

Provides:
- POST /api/auth/token   – password authentication → JWT
- get_current_user       – FastAPI dependency that validates the JWT
- DEMO_MODE bypass       – when SENTINELGRAPH_DEMO_MODE=true, all
                           protected endpoints are accessible without
                           a valid token (synthetic demo_user is returned)

Design notes:
- SECRET_KEY is read from the env; if not set, a random ephemeral key is
  generated at startup and a warning is logged.  Tokens will NOT survive
  a process restart unless SECRET_KEY is explicitly set.
- The password is compared against DEMO_PASSWORD (env) via bcrypt hash.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---- secrets & config -------------------------------------------------- #

def _get_secret_key() -> str:
    key = os.environ.get("SENTINELGRAPH_SECRET_KEY", "")
    if not key:
        key = secrets.token_urlsafe(48)
        logger.warning(
            "No SENTINELGRAPH_SECRET_KEY set – using ephemeral key; "
            "tokens will not survive restart."
        )
    return key

SECRET_KEY = _get_secret_key()
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8


def _demo_mode() -> bool:
    return os.environ.get("SENTINELGRAPH_DEMO_MODE", "false").lower() in {
        "1", "true", "yes",
    }


def _demo_password() -> str:
    return os.environ.get("SENTINELGRAPH_DEMO_PASSWORD", "demo")


DEMO_USERNAME = os.environ.get("SENTINELGRAPH_DEMO_USERNAME", "demo")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

# ---- JWT helpers ------------------------------------------------------- #

try:
    import jwt as jose_jwt
except ImportError:
    try:
        from jose import jwt as jose_jwt  # type: ignore
    except ImportError:
        jose_jwt = None  # type: ignore


def _create_token(subject: str) -> str:
    if jose_jwt is None:
        # Minimal JWT-like token when jose is unavailable (demo only).
        import base64, json
        payload = {"sub": subject, "exp": int(time.time()) + TOKEN_EXPIRE_HOURS * 3600}
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    payload = {
        "sub": subject,
        "exp": int(time.time()) + TOKEN_EXPIRE_HOURS * 3600,
    }
    return jose_jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    if jose_jwt is None:
        import base64, json
        try:
            return json.loads(base64.urlsafe_b64decode(token))
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        return jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


# ---- bcrypt password check --------------------------------------------- #

try:
    from passlib.context import CryptContext  # type: ignore
    _pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception:
    _pwd_ctx = None  # type: ignore


def _hash_password(password: str) -> str:
    if _pwd_ctx is not None:
        return _pwd_ctx.hash(password)
    # Fallback: store plaintext (only used in ephemeral demo, no real security).
    return password


def _verify_password(plain: str, hashed: str) -> bool:
    if _pwd_ctx is not None:
        return _pwd_ctx.verify(plain, hashed)
    return plain == hashed


# ---- demo password hash ------------------------------------------------ #

def _demo_password_hash() -> str:
    return _hash_password(_demo_password())


# ---- User model -------------------------------------------------------- #

@dataclass
class User:
    username: str
    is_demo: bool = False


# ---- FastAPI dependency ------------------------------------------------ #

async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> User:
    """Decode JWT and return the authenticated user.  DEMO_MODE bypasses
    the check entirely, returning a synthetic demo_user for every request."""
    if _demo_mode():
        return User(username=DEMO_USERNAME, is_demo=True)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = _decode_token(token)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return User(username=username, is_demo=False)


# ---- Auth router -------------------------------------------------------- #
# NOTE: the route is registered in src/api/routers/auth.py.
# This module provides the plain `login` helper and the `get_current_user`
# dependency.  No router or @router decorators are defined here to avoid
# double-registration.


class LoginRequest(BaseModel):
    """JSON login body: {username, password}."""

    username: str = "demo"
    password: str = "demo"


def login(form: LoginRequest) -> dict:
    """Authenticate with username + password and return a JWT bearer token."""
    if _demo_mode():
        token = _create_token(form.username)
        return {"access_token": token, "token_type": "bearer"}
    if not _verify_password(form.password, _demo_password_hash()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    token = _create_token(form.username)
    return {"access_token": token, "token_type": "bearer"}