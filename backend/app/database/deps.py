from app.database.db import AsyncSessionLocal


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()   # schedule routes never committed before
        except Exception:
            await session.rollback()
            raise
