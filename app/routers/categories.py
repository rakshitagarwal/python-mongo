"""Category CRUD. Public read, admin write.

Study notes:
- Categories live in their OWN collection; products store `category_id`
  (a reference, like a foreign key). This is why deleting a category that
  still has products is blocked with 409 — no orphaned references.
- `product_count` is computed at read time with count_documents, not
  stored (stored counters drift out of sync; counting is cheap here).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import require_admin
from app.database import categories_collection, products_collection
from app.models import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    Page,
    paginate,
)
from app.utils import parse_oid, serialize_category, slugify

router = APIRouter(prefix="/categories", tags=["categories"])


def _with_count(doc) -> dict:
    count = products_collection.count_documents({"category_id": doc["_id"]})
    return serialize_category(doc, product_count=count)


@router.get("", response_model=Page[CategoryResponse])
def list_categories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Public. Alphabetical, paginated."""
    skip = (page - 1) * page_size
    total = categories_collection.count_documents({})
    cursor = categories_collection.find().sort("name", 1).skip(skip).limit(page_size)
    return paginate([_with_count(c) for c in cursor], total, page, page_size)


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: str):
    """Public. Single category with its product count."""
    doc = categories_collection.find_one({"_id": parse_oid(category_id, "category ID")})
    if not doc:
        raise HTTPException(status_code=404, detail="Category not found")
    return _with_count(doc)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, admin: dict = Depends(require_admin)):
    """Admin. Slug auto-generated from name if omitted; must be unique."""
    slug = (payload.slug or slugify(payload.name)).lower()
    if categories_collection.find_one({"slug": slug}):
        raise HTTPException(status_code=409, detail=f"Slug '{slug}' already exists")
    result = categories_collection.insert_one(
        {"name": payload.name.strip(), "slug": slug, "description": payload.description}
    )
    created = categories_collection.find_one({"_id": result.inserted_id})
    return _with_count(created)


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: str, payload: CategoryUpdate, admin: dict = Depends(require_admin)
):
    """Admin. Renaming also updates the denormalized `category_name` on products."""
    oid = parse_oid(category_id, "category ID")
    doc = categories_collection.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Category not found")

    update: dict = {}
    if payload.name is not None:
        update["name"] = payload.name.strip()
    if payload.slug is not None:
        new_slug = payload.slug.lower().strip()
        clash = categories_collection.find_one({"slug": new_slug, "_id": {"$ne": oid}})
        if clash:
            raise HTTPException(
                status_code=409, detail=f"Slug '{new_slug}' already exists"
            )
        update["slug"] = new_slug
    if payload.description is not None:
        update["description"] = payload.description
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")

    categories_collection.update_one({"_id": oid}, {"$set": update})

    # Keep product display names in sync (denormalized copy).
    if "name" in update:
        products_collection.update_many(
            {"category_id": oid}, {"$set": {"category_name": update["name"]}}
        )
    return _with_count(categories_collection.find_one({"_id": oid}))


@router.delete("/{category_id}")
def delete_category(category_id: str, admin: dict = Depends(require_admin)):
    """Admin. Blocked with 409 while any product uses this category."""
    oid = parse_oid(category_id, "category ID")
    if not categories_collection.find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail="Category not found")
    in_use = products_collection.count_documents({"category_id": oid})
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {in_use} product(s) still use this category",
        )
    categories_collection.delete_one({"_id": oid})
    return {"message": "Category deleted successfully"}
