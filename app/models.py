"""Pydantic schemas: what goes IN (requests) and what comes OUT (responses).

Study notes:
- `...Create` models = request bodies the client sends.
- `...Response` models = what the API returns (never include secrets!).
- `Page[T]` = generic paginated envelope: every list endpoint returns
  {items, total, page, page_size, total_pages} instead of a bare array.
  The frontend needs `total` to render page numbers.
"""

from datetime import datetime
from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, EmailStr, Field, PositiveFloat, PositiveInt

Role = Literal["admin", "user"]

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic paginated response. Usage: Page[ProductResponse]."""

    items: List[T]
    total: int = Field(ge=0)  # total matching docs (ignoring page/page_size)
    page: int = Field(ge=1)  # 1-based page number the client asked for
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


def paginate(items: list, total: int, page: int, page_size: int) -> dict:
    """Build a Page dict. `math.ceil(total / page_size)` for total_pages."""
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# -------------------------
# Auth
# -------------------------


class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(ge=0, le=150)
    password: str = Field(min_length=8, max_length=128)
    # NOTE: no `role` field here on purpose — clients can only ever
    # register as "user". Admins are created via seed script or promotion.


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# -------------------------
# Users
# -------------------------


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    age: int
    role: Role
    # NOTE: password_hash is stored in Mongo but NEVER appears here.


class RoleUpdate(BaseModel):
    role: Role


# -------------------------
# Categories (own collection; products reference category_id)
# -------------------------


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    slug: Optional[str] = Field(default=None, max_length=80)
    description: str = ""


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    product_count: int = 0  # computed at read time, not stored


# -------------------------
# Products (category_id FK -> categories._id)
# -------------------------


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    price: PositiveFloat
    stock_quantity: int = Field(ge=0)
    category_id: str  # must reference an existing category
    image_url: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[PositiveFloat] = None
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    category_id: Optional[str] = None
    image_url: Optional[str] = None


class ProductResponse(BaseModel):
    id: str
    name: str
    description: str
    price: float
    stock_quantity: int
    category_id: str
    category_name: str = ""  # denormalized copy for cheap display
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None


class StockUpdate(BaseModel):
    stock_quantity: int = Field(ge=0)


# -------------------------
# Cart (one cart per user; user comes from the JWT, not the URL)
# -------------------------


class CartAddItem(BaseModel):
    product_id: str
    quantity: PositiveInt


class CartUpdateItem(BaseModel):
    quantity: int = Field(ge=0)  # 0 removes the line item


class CartItemResponse(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int
    line_total: float


class CartResponse(BaseModel):
    user_id: str
    items: List[CartItemResponse] = []
    total_amount: float = 0.0


# -------------------------
# Orders
# -------------------------

OrderStatus = Literal["pending", "shipped", "delivered", "cancelled"]


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderItemSnapshot(BaseModel):
    product_id: str
    name: str
    price_at_purchase: float
    quantity: int
    line_total: float


class OrderResponse(BaseModel):
    id: str
    user_id: str
    items: List[OrderItemSnapshot]
    total_amount: float
    status: str
    created_at: datetime
