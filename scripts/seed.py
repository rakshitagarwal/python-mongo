"""Dev seed: admin + user + categories + products. Idempotent (re-runnable).

Accounts (passwords frank on purpose — LOCAL DEV ONLY):
  admin@shop.com / admin123   (role=admin)
  user@shop.com  / user123    (role=user)

Usage:  venv\\Scripts\\python.exe scripts\\seed.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import hash_password
from app.database import categories_collection, products_collection, users_collection
from app.utils import slugify

ADMIN = {"name": "Shop Admin", "email": "admin@shop.com", "password": "admin123"}
USER = {"name": "Demo User", "email": "user@shop.com", "password": "user123"}

CATEGORIES = [
    ("Electronics", "Gadgets, TVs and computers."),
    ("Audio", "Headphones, speakers and more."),
    ("Home", "Everyday home goods."),
    ("Fashion", "Clothing and accessories."),
    ("Sports", "Fitness and outdoor gear."),
]

PRODUCTS = [
    # (name, description, price, stock, category_name, image_url)
    ("Wireless Headphones", "Noise-cancelling over-ear.", 99.99, 25, "Audio", None),
    ("Bluetooth Speaker", "Portable speaker, 12h battery.", 49.99, 40, "Audio", None),
    ("Smart TV 43 inch", "4K UHD smart TV.", 349.99, 10, "Electronics", None),
    ("Laptop Stand", "Aluminium ergonomic stand.", 29.99, 60, "Electronics", None),
    ("Coffee Mug", "Ceramic 350ml mug.", 9.99, 200, "Home", None),
    ("Desk Lamp", "LED lamp with 3 modes.", 19.99, 80, "Home", None),
    ("Cotton T-Shirt", "100% cotton, unisex.", 14.99, 150, "Fashion", None),
    ("Running Shoes", "Lightweight road runners.", 79.99, 35, "Fashion", None),
    ("Yoga Mat", "Non-slip 6mm mat.", 24.99, 70, "Sports", None),
    ("Dumbbell Set", "Adjustable 2x12kg.", 89.99, 20, "Sports", None),
    ("Earbuds Pro", "True wireless with ANC.", 59.99, 50, "Audio", None),
    ("Mechanical Keyboard", "Hot-swap, RGB.", 69.99, 30, "Electronics", None),
]


def ensure_user(name: str, email: str, password: str, role: str, age: int) -> None:
    if users_collection.find_one({"email": email}):
        print(f"  = user {email} already exists")
        return
    users_collection.insert_one(
        {
            "name": name,
            "email": email,
            "age": age,
            "password_hash": hash_password(password),
            "role": role,
            "created_at": datetime.now(timezone.utc),
        }
    )
    print(f"  + user {email} (role={role})")


def ensure_category(name: str, description: str):
    slug = slugify(name)
    doc = categories_collection.find_one({"slug": slug})
    if doc:
        return doc
    doc_id = categories_collection.insert_one(
        {"name": name, "slug": slug, "description": description}
    ).inserted_id
    print(f"  + category {name}")
    return categories_collection.find_one({"_id": doc_id})


def main() -> None:
    print("Seeding users...")
    ensure_user(ADMIN["name"], ADMIN["email"], ADMIN["password"], "admin", 30)
    ensure_user(USER["name"], USER["email"], USER["password"], "user", 25)

    print("Seeding categories + products...")
    cats = {name: ensure_category(name, desc) for name, desc in CATEGORIES}
    added = 0
    for name, desc, price, stock, cat_name, image in PRODUCTS:
        if products_collection.find_one({"name": name}):
            continue
        cat = cats[cat_name]
        products_collection.insert_one(
            {
                "name": name,
                "description": desc,
                "price": price,
                "stock_quantity": stock,
                "category_id": cat["_id"],
                "category_name": cat["name"],
                "image_url": image,
                "created_at": datetime.now(timezone.utc),
            }
        )
        added += 1
    print(f"Added {added} new product(s). Done.")
    print("Login: admin@shop.com/admin123  or  user@shop.com/user123")


if __name__ == "__main__":
    main()
