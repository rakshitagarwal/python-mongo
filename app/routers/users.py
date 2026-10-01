"""User management. ALL endpoints are admin-only.

Study notes:
- Regular users manage themselves via /auth/register, /auth/login, /auth/me.
  This router is the ADMIN panel: list/search users, change roles, delete.
- Self-protection: an admin can't demote or delete THEMSELVES (otherwise
  you could lock yourself out with zero admins left).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user, require_admin, user_id_str
from app.database import carts_collection, users_collection
from app.models import Page, RoleUpdate, UserResponse, paginate
from app.utils import parse_oid, serialize_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserResponse])
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    admin: dict = Depends(require_admin),
):
    """Admin. Paginated, with optional name/email search and role filter."""
    query: dict = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
    if role:
        if role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="role must be admin|user")
        query["role"] = role

    skip = (page - 1) * page_size
    total = users_collection.count_documents(query)
    cursor = users_collection.find(query).sort("name", 1).skip(skip).limit(page_size)
    return paginate([serialize_user(u) for u in cursor], total, page, page_size)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, admin: dict = Depends(require_admin)):
    """Admin. Single user by id."""
    user = users_collection.find_one({"_id": parse_oid(user_id, "user ID")})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_user(user)


@router.patch("/{user_id}/role", response_model=UserResponse)
def set_user_role(
    user_id: str,
    payload: RoleUpdate,
    admin: dict = Depends(require_admin),
    me: dict = Depends(get_current_user),
):
    """Admin. Promote user<->admin. You cannot change your OWN role."""
    oid = parse_oid(user_id, "user ID")
    if str(oid) == user_id_str(me):
        raise HTTPException(status_code=400, detail="You cannot change your own role")
    result = users_collection.update_one({"_id": oid}, {"$set": {"role": payload.role}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_user(users_collection.find_one({"_id": oid}))


@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    admin: dict = Depends(require_admin),
    me: dict = Depends(get_current_user),
):
    """Admin. Deletes the user AND their cart. You cannot delete yourself."""
    oid = parse_oid(user_id, "user ID")
    if str(oid) == user_id_str(me):
        raise HTTPException(status_code=400, detail="You cannot delete yourself")
    result = users_collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    carts_collection.delete_one({"user_id": oid})
    return {"message": "User deleted successfully"}
