"""Auth routes — registration, login, token management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
import uuid
import traceback

from app.models import async_session, User, PlanTier
from app.core.security import hash_password, verify_password, create_token, get_current_user

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    plan_tier: str
    max_products: int
    max_olx_accounts: int


PLAN_LIMITS = {
    PlanTier.starter: {"max_products": 10, "max_olx_accounts": 1},
    PlanTier.pro: {"max_products": 30, "max_olx_accounts": 2},
    PlanTier.business: {"max_products": 80, "max_olx_accounts": 5},
    PlanTier.enterprise: {"max_products": 200, "max_olx_accounts": 999},
}


@router.post("/register")
async def register(req: RegisterRequest):
    try:
        async with async_session() as db:
            existing = await db.execute(select(User).where(User.email == req.email))
            if existing.scalars().first():
                raise HTTPException(400, "Email already registered")

            limits = PLAN_LIMITS[PlanTier.starter]
            user = User(
                email=req.email,
                password_hash=hash_password(req.password),
                full_name=req.full_name,
                phone=req.phone,
                plan_tier=PlanTier.starter,
                max_products=limits["max_products"],
                max_olx_accounts=limits["max_olx_accounts"],
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            token = create_token(user.id)
            return {"token": token, "user": UserResponse(
                id=str(user.id), email=user.email, full_name=user.full_name,
                plan_tier=user.plan_tier.value, max_products=user.max_products,
                max_olx_accounts=user.max_olx_accounts,
            ).model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Register error: {str(e)}\n{traceback.format_exc()}")


@router.post("/login")
async def login(req: LoginRequest):
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == req.email))
        user = result.scalars().first()
        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(401, "Invalid credentials")

        token = create_token(user.id)
        return {"token": token, "user": UserResponse(
            id=str(user.id), email=user.email, full_name=user.full_name,
            plan_tier=user.plan_tier.value, max_products=user.max_products,
            max_olx_accounts=user.max_olx_accounts,
        ).model_dump()}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id), email=user.email, full_name=user.full_name,
        plan_tier=user.plan_tier.value, max_products=user.max_products,
        max_olx_accounts=user.max_olx_accounts,
    ).model_dump()


@router.post("/upgrade")
async def upgrade_plan(tier: str, user: User = Depends(get_current_user)):
    """Upgrade user's plan tier."""
    try:
        new_tier = PlanTier(tier)
    except ValueError:
        raise HTTPException(400, "Invalid plan tier")

    limits = PLAN_LIMITS[new_tier]
    async with async_session() as db:
        db_user = await db.get(User, user.id)
        db_user.plan_tier = new_tier
        db_user.max_products = limits["max_products"]
        db_user.max_olx_accounts = limits["max_olx_accounts"]
        await db.commit()

    return {"status": "upgraded", "plan": tier}
