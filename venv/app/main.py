from fastapi import FastAPI, HTTPException
from bson import ObjectId
from fastapi.middleware.cors import CORSMiddleware

from app.database import users_collection
from app.models import UserCreate, UserResponse


app = FastAPI(title="Python MongoDB CRUD API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# CREATE
# -------------------------

@app.post("/users", response_model=UserResponse)
def create_user(user: UserCreate):

    result = users_collection.insert_one(
        user.model_dump()
    )

    created_user = users_collection.find_one(
        {"_id": result.inserted_id}
    )

    return {
        "id": str(created_user["_id"]),
        "name": created_user["name"],
        "email": created_user["email"],
        "age": created_user["age"]
    }


# -------------------------
# READ ALL
# -------------------------

@app.get("/users")
def get_users():

    users = users_collection.find()

    return [
        {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "age": user["age"]
        }
        for user in users
    ]


# -------------------------
# READ ONE
# -------------------------

@app.get("/users/{user_id}")
def get_user(user_id: str):

    try:
        user = users_collection.find_one(
            {"_id": ObjectId(user_id)}
        )
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID"
        )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "age": user["age"]
    }


# -------------------------
# UPDATE
# -------------------------

@app.put("/users/{user_id}")
def update_user(
    user_id: str,
    user: UserCreate
):

    try:
        object_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID"
        )

    result = users_collection.update_one(
        {"_id": object_id},
        {
            "$set": user.model_dump()
        }
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    updated_user = users_collection.find_one(
        {"_id": object_id}
    )

    return {
        "id": str(updated_user["_id"]),
        "name": updated_user["name"],
        "email": updated_user["email"],
        "age": updated_user["age"]
    }


# -------------------------
# DELETE
# -------------------------

@app.delete("/users/{user_id}")
def delete_user(user_id: str):

    try:
        object_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID"
        )

    result = users_collection.delete_one(
        {"_id": object_id}
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "message": "User deleted successfully"
    }