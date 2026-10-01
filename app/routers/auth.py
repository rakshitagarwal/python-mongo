"""Auth endpoints: register, login, me.

Study notes:
- Register ALWAYS creates role="user". There is no way to register an
  admin via the API (admins come from the seed script or promotion).
  This is the #1 rule of role systems: never trust the client with roles.
- Login uses OAuth2PasswordRequestForm (username=email, password) so the
  Swagger UI "Authorize" button works out of the box.
- Login response is {"access_token", "token_type": "bearer"}.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.errors import DuplicateKeyError

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    user_id_str,
    verify_password,
)
from app.database import users_collection
from app.models import TokenResponse, UserRegister, UserResponse
from app.utils import serialize_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(payload: UserRegister):
    """Create a new account. Always role='user'. 409 if email taken."""
    if users_collection.find_one({"email": payload.email}):
        raise HTTPException(status_code=409, detail="Email already registered")

    doc = {
        "name": payload.name.strip(),
        "email": payload.email,  # EmailStr already normalized/lowercased
        "age": payload.age,
        "password_hash": hash_password(payload.password),
        "role": "user",
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = users_collection.insert_one(doc)
    except DuplicateKeyError:  # race: two registers at once
        raise HTTPException(status_code=409, detail="Email already registered")
    created = users_collection.find_one({"_id": result.inserted_id})
    return serialize_user(created)


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 form login. `username` field carries the EMAIL.

    Same error for wrong email AND wrong password — otherwise attackers
    could probe which emails exist (called "user enumeration").
    """
    user = users_collection.find_one({"email": form.username})
    if not user or not verify_password(form.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(user_id_str(user), user.get("role", "user"))
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def me(user: dict = Depends(get_current_user)):
    """Who am I? Returns the profile of the token owner."""
    return serialize_user(user)
