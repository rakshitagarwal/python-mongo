"""ONE-TIME migration: string `category` -> `category_id` reference.

Before: products = {name, ..., category: "audio"}   (free text)
After:  products = {name, ..., category_id: ObjectId, category_name: "audio"}
        + a real document in the `categories` collection per distinct name.

Safe to re-run: existing categories are matched by slug, products that
already have `category_id` are skipped.

Usage:  venv\\Scripts\\python.exe scripts\\migrate_categories.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import categories_collection, products_collection
from app.utils import slugify


def main() -> None:
    # 1. Collect every distinct legacy category string.
    names = sorted(
        {p.get("category", "general") or "general" for p in products_collection.find()}
    )
    print(f"Distinct legacy categories: {names}")

    # 2. Ensure one category doc per name (match by slug = idempotent).
    slug_to_id = {}
    for name in names:
        slug = slugify(name)
        doc = categories_collection.find_one({"slug": slug})
        if doc:
            slug_to_id[slug] = doc["_id"]
        else:
            new_id = categories_collection.insert_one(
                {
                    "name": name,
                    "slug": slug,
                    "description": f"Migrated from legacy '{name}' products.",
                }
            ).inserted_id
            slug_to_id[slug] = new_id
            print(f"  + category '{name}' (slug={slug})")

    # 3. Point products at their category doc (skip already-migrated ones).
    migrated = 0
    for product in products_collection.find():
        if product.get("category_id"):
            continue
        legacy = product.get("category", "general") or "general"
        cat_id = slug_to_id[slugify(legacy)]
        cat = categories_collection.find_one({"_id": cat_id})
        products_collection.update_one(
            {"_id": product["_id"]},
            {
                "$set": {"category_id": cat_id, "category_name": cat["name"]},
                "$unset": {"category": ""},
            },
        )
        migrated += 1
    print(f"Migrated {migrated} product(s). Done.")


if __name__ == "__main__":
    main()
