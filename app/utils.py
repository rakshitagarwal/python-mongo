import re

from bson import ObjectId
from fastapi import HTTPException


def parse_oid(id_str: str, field_name: str = "ID") -> ObjectId:
    """Parse a string into ObjectId or raise 400."""
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}",
        )


def slugify(name: str) -> str:
    """'Home Audio' -> 'home-audio'. Used for category slugs."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "general"


def serialize_user(doc) -> dict:
    # NOTE: password_hash is deliberately NEVER included.
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "email": doc["email"],
        "age": doc["age"],
        "role": doc.get("role", "user"),
    }


def serialize_category(doc, product_count: int = 0) -> dict:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "slug": doc.get("slug", ""),
        "description": doc.get("description", ""),
        "product_count": product_count,
    }


def serialize_product(doc) -> dict:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "description": doc.get("description", ""),
        "price": doc["price"],
        "stock_quantity": doc["stock_quantity"],
        # New FK-style reference (old `category` string migrated by script).
        "category_id": (
            str(doc["category_id"])
            if doc.get("category_id") is not None
            else ""
        ),
        "category_name": doc.get("category_name", ""),
        "image_url": doc.get("image_url"),
        "created_at": doc.get("created_at"),
    }


def serialize_order(doc) -> dict:
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]),
        "items": doc["items"],
        "total_amount": doc["total_amount"],
        "status": doc["status"],
        "created_at": doc["created_at"],
    }
