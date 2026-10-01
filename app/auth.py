"""Authentication: password hashing, JWT tokens, and FastAPI dependencies.

Study guide — the 4 ideas in this file:
1. PASSWORDS: `hash_password` (bcrypt, salted) on register; `verify_password`
   on login. Plaintext passwords never touch the database.
2. TOKENS: `create_access_token` signs {"sub": user_id, "role": role} with
   JWT_SECRET. Anyone can READ the payload (it's base64) but only the
   server can SIGN it — that's what makes it trustworthy.
3. `get_current_user`: a FastAPI *dependency*. Add it to any endpoint with
   `user=Depends(get_current_user)` and FastAPI runs it first, rejecting
   bad/missing tokens with 401 before your code executes.
4. `require_admin`: builds on #3, adds a 403 role check.

Frontend contract: login returns {"access_token", "token_type": "bearer"}.
Every protected call sends:  Authorization: Bearer <token>
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.errors import DuplicateKeyError  # noqa: F401  (re-exported for routers)

from app.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET
from app.database import users_collection
from app.utils import parse_oid

# Reads the `Authorization: Bearer <token>` header. auto_error=False so WE
# raise the 401 (with a clear message) instead of FastAPI's default 403.
bearer_scheme = HTTPBearer(auto_error=False)


# --- 1. Passwords ---


def hash_password(plain: str) -> str:
    """bcrypt hash (salt auto-generated). Store the result, never `plain`."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """True if `plain` matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# --- 2. Tokens ---


def create_access_token(user_id: str, role: str) -> str:
    """Sign a short-lived JWT. `sub` = subject = who this token belongs to."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,  # issued-at
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Verify signature + expiry. Raises 401 on ANY problem (bad UX to leak why)."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Please log in again.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )


# --- 3 & 4. Dependencies (plug into endpoints) ---


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Return the logged-in user's Mongo doc. 401 if no/invalid token."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Send `Authorization: Bearer <token>`.",
        )
    payload = decode_token(credentials.credentials)
    user = users_collection.find_one({"_id": parse_oid(payload["sub"], "user ID")})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Same as above, plus 403 unless role == 'admin'."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only.",
        )
    return user


def user_id_str(user: dict) -> str:
    """Helper: Mongo doc -> string id for responses / sub-docs."""
    return str(user["_id"])
