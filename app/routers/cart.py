"""Cart: one cart per user, ALWAYS the token owner's cart.

Study note: this is the payoff of auth. Old design had /cart/{user_id},
so anyone could pass ANY id and read/mutate someone else's cart.
Now there is no user_id parameter at all — `get_current_user` tells us
who is calling, and every query is scoped to that id.
"""

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import carts_collection, products_collection
from app.models import CartAddItem, CartResponse, CartUpdateItem
from app.utils import parse_oid

router = APIRouter(prefix="/cart", tags=["cart"])


def _build_cart_response(user_oid: ObjectId, cart_doc) -> dict:
    items = []
    total = 0.0
    for line in (cart_doc.get("items") if cart_doc else []) or []:
        product = products_collection.find_one({"_id": line["product_id"]})
        if not product:
            continue  # product deleted after being added
        line_total = product["price"] * line["quantity"]
        total += line_total
        items.append(
            {
                "product_id": str(product["_id"]),
                "name": product["name"],
                "price": product["price"],
                "quantity": line["quantity"],
                "line_total": line_total,
            }
        )
    return {"user_id": str(user_oid), "items": items, "total_amount": total}


@router.get("", response_model=CartResponse)
def get_cart(user: dict = Depends(get_current_user)):
    """Own cart (empty cart object if never added anything)."""
    cart = carts_collection.find_one({"user_id": user["_id"]})
    return _build_cart_response(user["_id"], cart)


@router.post("/items", response_model=CartResponse)
def add_to_cart(item: CartAddItem, user: dict = Depends(get_current_user)):
    """Add quantity to own cart. 400 if it would exceed stock."""
    user_oid = user["_id"]
    product_oid = parse_oid(item.product_id, "product ID")

    product = products_collection.find_one({"_id": product_oid})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart = carts_collection.find_one({"user_id": user_oid})
    existing_qty = 0
    if cart:
        for line in cart.get("items", []):
            if line["product_id"] == product_oid:
                existing_qty = line["quantity"]
                break

    if existing_qty + item.quantity > product["stock_quantity"]:
        raise HTTPException(
            status_code=400,
            detail=f"Only {product['stock_quantity']} in stock "
            f"({existing_qty} already in cart)",
        )

    if cart:
        if existing_qty:
            carts_collection.update_one(
                {"user_id": user_oid, "items.product_id": product_oid},
                {
                    "$inc": {"items.$.quantity": item.quantity},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
            )
        else:
            carts_collection.update_one(
                {"user_id": user_oid},
                {
                    "$push": {
                        "items": {
                            "product_id": product_oid,
                            "quantity": item.quantity,
                        }
                    },
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
            )
    else:
        carts_collection.insert_one(
            {
                "user_id": user_oid,
                "items": [{"product_id": product_oid, "quantity": item.quantity}],
                "updated_at": datetime.now(timezone.utc),
            }
        )

    return _build_cart_response(user_oid, carts_collection.find_one({"user_id": user_oid}))


@router.put("/items/{product_id}", response_model=CartResponse)
def update_cart_item(
    product_id: str, item: CartUpdateItem, user: dict = Depends(get_current_user)
):
    """Set exact quantity. quantity=0 removes the line."""
    user_oid = user["_id"]
    product_oid = parse_oid(product_id, "product ID")

    cart = carts_collection.find_one({"user_id": user_oid})
    if not cart or not any(
        line["product_id"] == product_oid for line in cart.get("items", [])
    ):
        raise HTTPException(status_code=404, detail="Item not in cart")

    if item.quantity == 0:
        carts_collection.update_one(
            {"user_id": user_oid},
            {
                "$pull": {"items": {"product_id": product_oid}},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )
    else:
        product = products_collection.find_one({"_id": product_oid})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        if item.quantity > product["stock_quantity"]:
            raise HTTPException(
                status_code=400,
                detail=f"Only {product['stock_quantity']} in stock",
            )
        carts_collection.update_one(
            {"user_id": user_oid, "items.product_id": product_oid},
            {
                "$set": {
                    "items.$.quantity": item.quantity,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    return _build_cart_response(user_oid, carts_collection.find_one({"user_id": user_oid}))


@router.delete("/items/{product_id}", response_model=CartResponse)
def remove_cart_item(product_id: str, user: dict = Depends(get_current_user)):
    """Remove one line from own cart."""
    user_oid = user["_id"]
    carts_collection.update_one(
        {"user_id": user_oid},
        {
            "$pull": {"items": {"product_id": parse_oid(product_id, "product ID")}},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    return _build_cart_response(user_oid, carts_collection.find_one({"user_id": user_oid}))


@router.delete("")
def clear_cart(user: dict = Depends(get_current_user)):
    """Empty own cart."""
    carts_collection.delete_one({"user_id": user["_id"]})
    return {"message": "Cart cleared"}
