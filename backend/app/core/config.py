import os
from dotenv import load_dotenv

load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
# After
DATABASE_URL = os.getenv("DATABASE_URL") or \
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@localhost/{DB_NAME}"

STREAMLIT_BASE_URL = os.getenv("STREAMLIT_BASE_URL")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

FERNET_SECRET_KEY = os.getenv("FERNET_KEY")

