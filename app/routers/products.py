"""Products. Public reads (paginated/search/sort), admin writes.

Study notes:
- LIST pattern used everywhere in this project:
  1. build a Mongo `query` from optional filters,
  2. `count_documents(query)` for the total (BEFORE skip/limit!),
  3. `find(query).sort().skip().limit()` for the page,
  4. wrap with `paginate(...)`.
- `search` uses Mongo's text index (see database.py) — much better than
  regex for multi-word product names.
- `category_id` is validated against the categories collection on write,
  and `category_name` is denormalized (copied) so reads don't need a join.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import require_admin
from app.database import categories_collection, products_collection
from app.models import (
    Page,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StockUpdate,
    paginate,
)
from app.utils import parse_oid, serialize_product

router = APIRouter(prefix="/products", tags=["products"])

SORTS = {
    "newest": [("created_at", -1)],
    "price_asc": [("price", 1)],
    "price_desc": [("price", -1)],
    "name": [("name", 1)],
}


def _resolve_category(category_id: str) -> dict:
    """Return the category doc or 400. Products can't point at nothing."""
    cat = categories_collection.find_one(
        {"_id": parse_oid(category_id, "category ID")}
    )
    if not cat:
        raise HTTPException(status_code=400, detail="Category does not exist")
    return cat


@router.get("", response_model=Page[ProductResponse])
def list_products(
    search: Optional[str] = Query(default=None),
    category_id: Optional[str] = Query(default=None),
    category_slug: Optional[str] = Query(default=None),
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    sort: str = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
):
    """Public. Full filter/sort/pagination demo endpoint."""
    if sort not in SORTS:
        raise HTTPException(
            status_code=400, detail=f"sort must be one of {list(SORTS)}"
        )

    query: dict = {}
    if search:
        query["$text"] = {"$search": search}
    if category_id:
        query["category_id"] = parse_oid(category_id, "category ID")
    elif category_slug:
        cat = categories_collection.find_one({"slug": category_slug})
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        query["category_id"] = cat["_id"]
    if min_price is not None or max_price is not None:
        query["price"] = {}
        if min_price is not None:
            query["price"]["$gte"] = min_price
        if max_price is not None:
            query["price"]["$lte"] = max_price

    skip = (page - 1) * page_size
    total = products_collection.count_documents(query)
    cursor = (
        products_collection.find(query).sort(SORTS[sort]).skip(skip).limit(page_size)
    )
    return paginate([serialize_product(p) for p in cursor], total, page, page_size)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: str):
    """Public. Single product."""
    product = products_collection.find_one(
        {"_id": parse_oid(product_id, "product ID")}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_product(product)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductCreate, admin: dict = Depends(require_admin)):
    """Admin. category_id must exist; its name is copied onto the product."""
    cat = _resolve_category(product.category_id)
    result = products_collection.insert_one(
        {
            "name": product.name.strip(),
            "description": product.description,
            "price": product.price,
            "stock_quantity": product.stock_quantity,
            "category_id": cat["_id"],
            "category_name": cat["name"],
            "image_url": product.image_url,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return serialize_product(products_collection.find_one({"_id": result.inserted_id}))


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str, product: ProductUpdate, admin: dict = Depends(require_admin)
):
    """Admin. Partial update; changing category_id re-validates + re-copies name."""
    oid = parse_oid(product_id, "product ID")
    update_data = {
        k: v for k, v in product.model_dump().items() if v is not None
    }
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "category_id" in update_data:
        cat = _resolve_category(update_data["category_id"])
        update_data["category_id"] = cat["_id"]
        update_data["category_name"] = cat["name"]
    if "name" in update_data:
        update_data["name"] = update_data["name"].strip()

    result = products_collection.update_one({"_id": oid}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_product(products_collection.find_one({"_id": oid}))


@router.patch("/{product_id}/stock", response_model=ProductResponse)
def update_stock(
    product_id: str, stock: StockUpdate, admin: dict = Depends(require_admin)
):
    """Admin. Set absolute stock level."""
    oid = parse_oid(product_id, "product ID")
    result = products_collection.update_one(
        {"_id": oid}, {"$set": {"stock_quantity": stock.stock_quantity}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_product(products_collection.find_one({"_id": oid}))


@router.delete("/{product_id}")
def delete_product(product_id: str, admin: dict = Depends(require_admin)):
    """Admin. (Cart lines pointing at it are skipped at read time.)"""
    result = products_collection.delete_one(
        {"_id": parse_oid(product_id, "product ID")}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}
