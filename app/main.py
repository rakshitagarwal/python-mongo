from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, cart, categories, orders, products, users

app = FastAPI(title="Ecommerce Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)


@app.get("/")
def root():
    return {"message": "Ecommerce Backend API running"}
