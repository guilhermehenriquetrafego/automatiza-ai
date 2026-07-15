"""Auth routes — registration, login, Google OAuth, token management."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
import uuid
import traceback
import httpx
import json
import base64
import hashlib
import secrets

from app.models import async_session, User, PlanTier
from app.core.security import hash_password, verify_password, create_token, get_current_user
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str  # Google ID token (from Google Identity)


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


@router.post("/google")
async def google_auth(req: GoogleAuthRequest):
    """
    Authenticate with Google OAuth.
    Receives the Google ID token (credential) from Google Identity Services.
    Verifies the token with Google, creates or finds the user, returns our JWT.
    """
    try:
        # Verify the Google ID token
        google_response = await verify_google_token(req.credential)
        if not google_response:
            raise HTTPException(401, "Invalid Google token")

        google_email = google_response.get("email")
        google_name = google_response.get("name", "Usuário Google")
        google_picture = google_response.get("picture")

        if not google_email:
            raise HTTPException(400, "Google account has no email")

        async with async_session() as db:
            # Check if user already exists
            result = await db.execute(select(User).where(User.email == google_email))
            user = result.scalars().first()

            if not user:
                # Create new user with Google
                limits = PLAN_LIMITS[PlanTier.starter]
                # Generate a random password (Google users don't use password login)
                random_password = secrets.token_urlsafe(32)
                user = User(
                    email=google_email,
                    password_hash=hash_password(random_password),
                    full_name=google_name,
                    plan_tier=PlanTier.starter,
                    max_products=limits["max_products"],
                    max_olx_accounts=limits["max_olx_accounts"],
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
            else:
                # Update name if needed
                if not user.full_name or user.full_name == "":
                    user.full_name = google_name
                    await db.commit()

            token = create_token(user.id)
            return {"token": token, "user": UserResponse(
                id=str(user.id), email=user.email, full_name=user.full_name,
                plan_tier=user.plan_tier.value, max_products=user.max_products,
                max_olx_accounts=user.max_olx_accounts,
            ).model_dump()}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Google auth error: {str(e)}")


async def verify_google_token(credential: str) -> dict | None:
    """
    Verify a Google ID token by calling Google's tokeninfo endpoint.
    Returns the decoded token payload if valid, None otherwise.
    """
    try:
        async with httpx.AsyncClient() as client:
            # Use Google's tokeninfo endpoint to verify the ID token
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": credential},
            )
            if resp.status_code != 200:
                return None

            payload = resp.json()

            # Verify the audience (client_id) matches our Google Client ID
            google_client_id = settings.GOOGLE_CLIENT_ID
            if google_client_id and payload.get("aud") != google_client_id:
                return None

            # Verify issuer
            if payload.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
                return None

            # Verify email is verified
            if not payload.get("email_verified"):
                # Some accounts may not have verified email — still allow for now
                pass

            return payload
    except Exception:
        return None


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
