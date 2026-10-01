from pymongo import MongoClient

from app.config import DATABASE_NAME, MONGO_URI

client = MongoClient(MONGO_URI)

db = client[DATABASE_NAME]

users_collection = db["users"]
products_collection = db["products"]
categories_collection = db["categories"]
carts_collection = db["carts"]
orders_collection = db["orders"]

# Indexes (safe to run on every startup; no-ops if they exist).
# Wrapped so the app still imports when Mongo is down.
try:
    users_collection.create_index("email", unique=True)
    users_collection.create_index("role")
    categories_collection.create_index("slug", unique=True)
    products_collection.create_index("category_id")
    products_collection.create_index([("name", "text"), ("description", "text")])
    carts_collection.create_index("user_id", unique=True)
    orders_collection.create_index("user_id")
    orders_collection.create_index("status")
except Exception:
    pass
