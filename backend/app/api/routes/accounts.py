"""OLX Account routes — add/remove accounts, login, sync limits."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, EmailStr

from app.models import async_session, User, OlxAccount, OlxAccountType
from app.core.security import get_current_user

router = APIRouter()


class AddAccountRequest(BaseModel):
    email: EmailStr
    password: str
    plan_name: str | None = None  # e.g. "Diversos 250"


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
async def add_account(req: AddAccountRequest, user: User = Depends(get_current_user)):
    # Check account limit
    async with async_session() as db:
        count_result = await db.execute(
            select(func.count()).where(OlxAccount.user_id == user.id)
        )
        count = count_result.scalar()
        if count >= user.max_olx_accounts:
            raise HTTPException(403, f"Account limit reached ({user.max_olx_accounts})")

        # Create account record with default type 'free' (to be detected and updated by CDP session later),
        # with is_authenticated=False and needs_reauth=True initially.
        account = OlxAccount(
            user_id=user.id,
            email=req.email,
            account_type=OlxAccountType.free,
            is_authenticated=False,
            needs_reauth=True,
            plan_name=req.plan_name,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)

        # Simulate a CDP login session that detects the account type in the background/simulated flow
        from app.api.routes.cdp_live import cdp_sessions, cdp_activities
        from datetime import datetime, timezone

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        steps = [
            {
                "timestamp": now,
                "action": "initialize",
                "status": "connecting",
                "message": "Iniciando conexão de autenticação CDP com a OLX..."
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "open_browser",
                "status": "connecting",
                "message": "Abrindo navegador e preparando formulário de login..."
            }
        ]

        cdp_sessions[session_id] = {
            "id": session_id,
            "account_email": req.email,
            "status": "connecting",
            "current_action": "Conectando e autenticando na OLX...",
            "started_at": now,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "steps": steps,
            "olx_ad_url": None
        }

        for step in steps:
            cdp_activities.append({
                "timestamp": step["timestamp"],
                "session_id": session_id,
                "account_email": req.email,
                "action": step["action"],
                "status": step["status"],
                "message": step["message"]
            })

        # Schedule login + limit sync in background (safe — won't crash if no Redis)
        from app.tasks import safe_delay, sync_olx_limits
        safe_delay(sync_olx_limits, str(account.id))

        response_data = _to_response(account).model_dump()
        response_data["status_message"] = "Sistema conectando e autenticando com a OLX via CDP..."
        response_data["cdp_session_id"] = session_id
        return response_data


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
async def trigger_sync(account_id: str, user: User = Depends(get_current_user)):
    """Manually trigger a limit sync for this account."""
    from app.tasks import safe_delay, sync_olx_limits
    safe_delay(sync_olx_limits, account_id)
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
