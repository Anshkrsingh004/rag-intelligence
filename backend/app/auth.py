"""
Authentication: bcrypt password hashing, JWT issue/verify, a `current_user`
dependency, and the /api/auth router (register, login, me).
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_google_client_id, get_jwt_secret, settings
from .db import User, get_db
from .schemas import (
    AuthConfigResponse,
    GoogleAuthRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_bearer = HTTPBearer(auto_error=False)


# ── Password hashing ───────────────────────────────────────────
def hash_password(password: str) -> str:
    # bcrypt caps input at 72 bytes; encode + truncate defensively.
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── Tokens ─────────────────────────────────────────────────────
def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> int:
    try:
        data = jwt.decode(token, get_jwt_secret(), algorithms=[settings.jwt_algorithm])
        return int(data["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token") from e


# ── Dependencies ───────────────────────────────────────────────
def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = _decode_token(creds.credentials)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name)


# ── Router ─────────────────────────────────────────────────────
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(email=email, password_hash=hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(token=create_token(user.id), user=_user_out(user))


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = req.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return TokenResponse(token=create_token(user.id), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return _user_out(user)


# ── Google sign-in ─────────────────────────────────────────────
@router.get("/config", response_model=AuthConfigResponse)
def auth_config() -> AuthConfigResponse:
    """Public: lets the frontend know whether (and with which id) Google is enabled."""
    return AuthConfigResponse(google_client_id=get_google_client_id())


def _verify_google_credential(credential: str, client_id: str) -> dict:
    """Verify a Google ID token's signature, audience, expiry, and issuer."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    try:
        info = google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), client_id
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid Google sign-in token.") from e

    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(status_code=401, detail="Untrusted token issuer.")
    if not info.get("email") or not info.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google account email is not verified.")
    return info


@router.post("/google", response_model=TokenResponse)
def google_login(req: GoogleAuthRequest, db: Session = Depends(get_db)) -> TokenResponse:
    client_id = get_google_client_id()
    if not client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on the server.")

    info = _verify_google_credential(req.credential, client_id)
    email = info["email"].strip().lower()
    sub = str(info["sub"])
    name = info.get("name") or " ".join(
        p for p in (info.get("given_name"), info.get("family_name")) if p
    ) or None

    # Match by Google id first, then by email (links an existing password account).
    user = db.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(secrets.token_hex(24)),  # unusable — no password login
                google_sub=sub,
                name=name,
            )
            db.add(user)
        elif user.google_sub is None:
            user.google_sub = sub
    if name:  # keep the display name fresh from Google on every sign-in
        user.name = name
    db.commit()
    db.refresh(user)
    return TokenResponse(token=create_token(user.id), user=_user_out(user))
