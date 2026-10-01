"""Orders. Users act on their OWN orders; admins see/manage everything.

Study notes:
- POST /orders takes NO body: it checks out the CALLER's cart. The user
  comes from the token, so you can never order on someone else's behalf.
- GET /orders is paginated. Regular users only ever see their own rows
  (the query is forced to user_id=self); admins may pass ?user_id= to
  inspect one customer, plus ?status= to filter.
- PATCH status: owners may only CANCEL their own pending order.
  Admins may run any VALID_TRANSITIONS step. Cancelling restocks.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.database import (
    carts_collection,
    orders_collection,
    products_collection,
)
from app.models import OrderResponse, OrderStatusUpdate, Page, paginate
from app.utils import parse_oid, serialize_order

router = APIRouter(prefix="/orders", tags=["orders"])

VALID_TRANSITIONS = {
    "pending": {"shipped", "cancelled"},
    "shipped": {"delivered", "cancelled"},
    "delivered": set(),
    "cancelled": set(),
}


@router.post("", response_model=OrderResponse)
def create_order(user: dict = Depends(get_current_user)):
    """Checkout: snapshot own cart into an order, decrement stock, clear cart."""
    user_oid = user["_id"]
    cart = carts_collection.find_one({"user_id": user_oid})
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Validate stock + snapshot prices
    order_items = []
    total = 0.0
    for line in cart["items"]:
        product = products_collection.find_one({"_id": line["product_id"]})
        if not product:
            raise HTTPException(
                status_code=400,
                detail=f"Product {line['product_id']} no longer exists",
            )
        if line["quantity"] > product["stock_quantity"]:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product['name']}': "
                f"requested {line['quantity']}, "
                f"available {product['stock_quantity']}",
            )
        line_total = product["price"] * line["quantity"]
        total += line_total
        order_items.append(
            {
                "product_id": str(product["_id"]),
                "name": product["name"],
                "price_at_purchase": product["price"],
                "quantity": line["quantity"],
                "line_total": line_total,
            }
        )

    order_doc = {
        "user_id": user_oid,
        "items": order_items,
        "total_amount": total,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
    }
    result = orders_collection.insert_one(order_doc)

    # Decrement stock, then clear cart.
    # NOTE: not a multi-doc transaction (needs replica set); v1 keeps it simple.
    for line in cart["items"]:
        products_collection.update_one(
            {"_id": line["product_id"]},
            {"$inc": {"stock_quantity": -line["quantity"]}},
        )
    carts_collection.delete_one({"user_id": user_oid})

    return serialize_order(orders_collection.find_one({"_id": result.inserted_id}))


@router.get("", response_model=Page[OrderResponse])
def list_orders(
    user_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Paginated, newest first. Users see only their own orders.

    Admins: omit user_id to see EVERYONE's, or pass ?user_id= to filter.
    Non-admins: ?user_id= is ignored — the query is forced to self.
    """
    query: dict = {}
    if user.get("role") == "admin":
        if user_id:
            query["user_id"] = parse_oid(user_id, "user ID")
    else:
        query["user_id"] = user["_id"]
    if status:
        query["status"] = status

    skip = (page - 1) * page_size
    total = orders_collection.count_documents(query)
    cursor = (
        orders_collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    )
    return paginate([serialize_order(o) for o in cursor], total, page, page_size)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, user: dict = Depends(get_current_user)):
    """Owner or admin. Users get 404 (not 403) for others' orders — safer."""
    order = orders_collection.find_one({"_id": parse_oid(order_id, "order ID")})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.get("role") != "admin" and order["user_id"] != user["_id"]:
        raise HTTPException(status_code=404, detail="Order not found")
    return serialize_order(order)


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: str, payload: OrderStatusUpdate, user: dict = Depends(get_current_user)
):
    """Status machine with role rules:
    - owner: may only cancel their OWN 'pending' order,
    - admin: any transition in VALID_TRANSITIONS.
    Cancelling restocks the products.
    """
    order = orders_collection.find_one({"_id": parse_oid(order_id, "order ID")})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    is_owner = order["user_id"] == user["_id"]
    is_admin = user.get("role") == "admin"
    if not is_admin:
        if not is_owner:
            raise HTTPException(status_code=404, detail="Order not found")
        if payload.status != "cancelled" or order["status"] != "pending":
            raise HTTPException(
                status_code=403,
                detail="You can only cancel your own pending orders",
            )

    current = order["status"]
    if payload.status == current:
        return serialize_order(order)
    if payload.status not in VALID_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move order from '{current}' to '{payload.status}'",
        )

    # Restock if an order is cancelled
    if payload.status == "cancelled" and current in {"pending", "shipped"}:
        for item in order["items"]:
            products_collection.update_one(
                {"_id": parse_oid(item["product_id"], "product ID")},
                {"$inc": {"stock_quantity": item["quantity"]}},
            )

    orders_collection.update_one(
        {"_id": order["_id"]}, {"$set": {"status": payload.status}}
    )
    return serialize_order(orders_collection.find_one({"_id": order["_id"]}))
