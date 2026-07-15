"""OLX Account routes — add/remove accounts, login, sync limits."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, EmailStr

from app.models import async_session, User, OlxAccount, OlxAccountType, Product
from app.core.security import get_current_user

router = APIRouter()


class AddAccountRequest(BaseModel):
    email: EmailStr
    password: str
    account_type: str  # "free" | "professional"


class AccountResponse(BaseModel):
    id: str
    email: str
    account_type: str
    is_authenticated: bool
    needs_reauth: bool
    total_monthly_limit: int
    used_this_month: int
    remaining_this_month: int
    last_limit_sync: str | None = None


@router.get("/")
async def list_accounts(user: User = Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(
            select(OlxAccount).where(OlxAccount.user_id == user.id)
        )
        accounts = result.scalars().all()
        return [_to_response(a).model_dump() for a in accounts]


@router.post("/")
async def add_account(req: AddAccountRequest, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    # Check account limit
    async with async_session() as db:
        count_result = await db.execute(
            select(func.count()).where(OlxAccount.user_id == user.id)
        )
        count = count_result.scalar()
        if count >= user.max_olx_accounts:
            raise HTTPException(403, f"Account limit reached ({user.max_olx_accounts})")

        account = OlxAccount(
            user_id=user.id,
            email=req.email,
            account_type=OlxAccountType(req.account_type),
            is_authenticated=False,
        )
        db.add(account)
        await db.commit()

        # Schedule login + limit sync in background
        from app.tasks import sync_olx_limits
        background_tasks.add_task(sync_olx_limits.delay, str(account.id))

        return _to_response(account).model_dump()


@router.delete("/{account_id}")
async def remove_account(account_id: str, user: User = Depends(get_current_user)):
    async with async_session() as db:
        account = await db.get(OlxAccount, uuid.UUID(account_id))
        if not account or account.user_id != user.id:
            raise HTTPException(404, "Account not found")
        await db.delete(account)
        await db.commit()
    return {"status": "removed"}


@router.post("/{account_id}/sync-limits")
async def trigger_sync(account_id: str, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Manually trigger a limit sync for this account."""
    from app.tasks import sync_olx_limits
    background_tasks.add_task(sync_olx_limits.delay, account_id)
    return {"status": "sync_scheduled"}


def _to_response(account: OlxAccount) -> AccountResponse:
    return AccountResponse(
        id=str(account.id),
        email=account.email,
        account_type=account.account_type.value,
        is_authenticated=account.is_authenticated,
        needs_reauth=account.needs_reauth,
        total_monthly_limit=account.total_monthly_limit or 0,
        used_this_month=account.used_this_month or 0,
        remaining_this_month=account.remaining_this_month or 0,
        last_limit_sync=account.last_limit_sync.isoformat() if account.last_limit_sync else None,
    )
