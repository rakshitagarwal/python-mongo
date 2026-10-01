"""ONE-TIME script: wipe legacy passwordless users (fresh start).

Old users have {name, email, age} but NO password_hash and NO role, so
they can never log in. Per the plan we delete them plus their carts and
orders. Products and categories are NOT touched.

Usage:  venv\\Scripts\\python.exe scripts\\wipe_users.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import carts_collection, orders_collection, users_collection


def main() -> None:
    n_users = users_collection.count_documents({})
    n_carts = carts_collection.count_documents({})
    n_orders = orders_collection.count_documents({})
    print(f"Found {n_users} users, {n_carts} carts, {n_orders} orders.")

    answer = input("Delete ALL users + carts + orders? type YES to confirm: ")
    if answer.strip() != "YES":
        print("Aborted. Nothing deleted.")
        return

    users_collection.delete_many({})
    carts_collection.delete_many({})
    orders_collection.delete_many({})
    print("Wiped users, carts, orders. Products/categories kept.")


if __name__ == "__main__":
    main()
