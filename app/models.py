from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str
    email: str
    age: int


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    age: int