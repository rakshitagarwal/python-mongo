"""Central app configuration, read from environment (.env).

Study note: secrets (JWT_SECRET) must NEVER be hardcoded in source.
They live in `.env` (gitignored) and are read here with safe dev defaults.
"""

import os

from dotenv import load_dotenv

load_dotenv()

MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DATABASE_NAME: str = os.getenv("DATABASE_NAME", "crud_db")

# --- Auth settings ---
JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-me")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
# Access tokens expire after this many minutes (no refresh tokens in v1).
JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

if JWT_SECRET == "dev-only-insecure-secret-change-me":
    print(
        "WARNING: using default JWT_SECRET. "
        "Set a real JWT_SECRET in .env for anything beyond local dev."
    )
