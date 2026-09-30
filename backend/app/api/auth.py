from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.schemas.user import UserRegister, UserLogin
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.database.deps import get_db
from app.models.user import User
from app.models.session import Session as UserSession

auth_router = APIRouter()


@auth_router.get("/")
async def home():
    return {"message": "Hello"}


@auth_router.post("/register")
async def register(user: UserRegister, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    existing_user_flag = result.scalar_one_or_none()

    if existing_user_flag:
        return {"error": "User Already Exist"}

    hashed_password = hash_password(user.password)
    new_user_add = User(username=user.username, email=user.email, password=hashed_password)
    db.add(new_user_add)
    await db.commit()
    await db.refresh(new_user_add)

    return {"message": "User Created", "username": user.username, "email": user.email, "user_id": new_user_add.id}


@auth_router.post("/login")
async def login(request: Request, user: UserLogin, db: AsyncSession = Depends(get_db)):
    ip_address = str(request.client.host)
    result = await db.execute(select(User).where(User.email == user.email))
    db_user = result.scalar_one_or_none()

    if not db_user:
        return {"error": "Invalid credentials"}

    if not verify_password(user.password, db_user.password):
        return {"error": "Invalid credentials"}

    access_token = create_access_token({"sub": db_user.email})

    session_add = UserSession(user_id=db_user.id, access_token=access_token, ip_address=ip_address)
    db.add(session_add)
    await db.commit()
    await db.refresh(session_add)

    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.post("/logout")
async def logout(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == current_user.id)
        .values(is_active=False)
    )
    await db.commit()
    return {"message": "Logged out successfully"}