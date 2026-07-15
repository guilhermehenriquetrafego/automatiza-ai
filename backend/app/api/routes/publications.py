"""Publication routes — view scheduled/active ads, trigger Motor de Exposição."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from app.models import async_session, User, Publication, OlxAccount, ExposureSchedule, PublicationStatus
from app.core.security import get_current_user

router = APIRouter()


class PublicationResponse(BaseModel):
    id: str
    product_title: str | None = None
    variation_title: str | None = None
    status: str
    scheduled_for: str | None = None
    posted_at: str | None = None
    olx_ad_url: str | None = None
    error_message: str | None = None


@router.get("/")
async def list_publications(status: str | None = None, user: User = Depends(get_current_user)):
    async with async_session() as db:
        query = (
            select(Publication, OlxAccount)
            .join(OlxAccount, Publication.olx_account_id == OlxAccount.id)
            .where(OlxAccount.user_id == user.id)
        )
        if status:
            query = query.where(Publication.status == PublicationStatus(status))
        query = query.order_by(Publication.created_date.desc()).limit(100)

        result = await db.execute(query)
        rows = result.all()

        responses = []
        for pub, account in rows:
            from app.models import Product, AdVariation
            product = await db.get(Product, pub.product_id)
            variation = await db.get(AdVariation, pub.variation_id) if pub.variation_id else None
            responses.append(PublicationResponse(
                id=str(pub.id),
                product_title=product.title if product else None,
                variation_title=variation.title if variation else None,
                status=pub.status.value,
                scheduled_for=pub.scheduled_for.isoformat() if pub.scheduled_for else None,
                posted_at=pub.posted_at.isoformat() if pub.posted_at else None,
                olx_ad_url=pub.olx_ad_url,
                error_message=pub.error_message,
            ).model_dump())
        return responses


@router.get("/schedule")
async def view_schedule(user: User = Depends(get_current_user)):
    """View the current Motor de Exposição schedule."""
    async with async_session() as db:
        result = await db.execute(
            select(ExposureSchedule)
            .where(
                and_(
                    ExposureSchedule.user_id == user.id,
                    ExposureSchedule.is_executed == False,
                    ExposureSchedule.is_skipped == False,
                )
            )
            .order_by(ExposureSchedule.scheduled_time)
        )
        entries = result.scalars().all()
        return [{
            "id": str(e.id),
            "scheduled_time": e.scheduled_time.isoformat(),
            "olx_account_id": str(e.olx_account_id) if e.olx_account_id else None,
            "product_id": str(e.product_id) if e.product_id else None,
            "variation_id": str(e.variation_id) if e.variation_id else None,
            "priority": e.priority,
        } for e in entries]


@router.post("/recalculate")
async def recalculate_schedule(user: User = Depends(get_current_user)):
    """Manually trigger the Motor de Exposição to recalculate the publishing calendar."""
    from app.tasks import safe_delay, exposure_engine_run
    safe_delay(exposure_engine_run, str(user.id))
    return {"status": "recalculation_started"}


@router.get("/stats")
async def publication_stats(user: User = Depends(get_current_user)):
    """Get publication statistics for the dashboard."""
    async with async_session() as db:
        result = await db.execute(
            select(Publication.status, func.count())
            .join(OlxAccount, Publication.olx_account_id == OlxAccount.id)
            .where(OlxAccount.user_id == user.id)
            .group_by(Publication.status)
        )
        status_counts = {row[0].value: row[1] for row in result.all()}

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(func.count())
            .select_from(Publication)
            .join(OlxAccount, Publication.olx_account_id == OlxAccount.id)
            .where(
                and_(
                    OlxAccount.user_id == user.id,
                    Publication.created_date >= now.replace(day=1, hour=0, minute=0, second=0),
                )
            )
        )
        total_this_month = result.scalar()

        return {
            "status_counts": status_counts,
            "total_this_month": total_this_month,
        }
