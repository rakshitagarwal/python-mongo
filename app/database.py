import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "crud_db")

client = MongoClient(MONGO_URI)

db = client[DATABASE_NAME]

users_collection = db["users"]