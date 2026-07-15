"""Dashboard routes — overview stats and performance metrics."""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timezone
from typing import Optional

from app.models import (
    async_session, User, OlxAccount, Product, Publication,
    PublicationStatus, PerformanceMetric, ChatMessage, ChatStatus
)
from app.core.security import get_current_user

router = APIRouter()


@router.get("/overview")
async def overview(user: User = Depends(get_current_user)):
    """Main dashboard overview — key metrics at a glance."""
    async with async_session() as db:
        # Active products
        active_products = await db.execute(
            select(func.count()).where(
                Product.user_id == user.id,
                Product.is_active == True,
            )
        )
        # OLX accounts
        accounts = await db.execute(
            select(OlxAccount).where(OlxAccount.user_id == user.id)
        )
        accounts_list = accounts.scalars().all()

        # Publications this month
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, tzinfo=timezone.utc)
        pubs = await db.execute(
            select(Publication.status, func.count())
            .join(OlxAccount, Publication.olx_account_id == OlxAccount.id)
            .where(
                and_(
                    OlxAccount.user_id == user.id,
                    Publication.created_date >= month_start,
                )
            )
            .group_by(Publication.status)
        )
        pub_stats = {row[0].value: row[1] for row in pubs.all()}

        # Total remaining ad capacity
        total_remaining = sum(a.remaining_this_month or 0 for a in accounts_list)

        # Pending chats
        pending_chats = await db.execute(
            select(func.count())
            .select_from(ChatMessage)
            .join(OlxAccount, ChatMessage.olx_account_id == OlxAccount.id)
            .where(
                and_(
                    OlxAccount.user_id == user.id,
                    ChatMessage.status == ChatStatus.human_needed,
                )
            )
        )

        return {
            "active_products": active_products.scalar(),
            "max_products": user.max_products,
            "olx_accounts": len(accounts_list),
            "max_accounts": user.max_olx_accounts,
            "total_remaining_ads": total_remaining,
            "publications": {
                "online": pub_stats.get("online", 0),
                "scheduled": pub_stats.get("scheduled", 0),
                "posting": pub_stats.get("posting", 0),
                "failed": pub_stats.get("failed", 0),
            },
            "pending_chats": pending_chats.scalar(),
            "plan": user.plan_tier.value,
        }


@router.get("/performance")
async def performance(user: User = Depends(get_current_user)):
    """Performance metrics — views, chats, CTR over time."""
    async with async_session() as db:
        result = await db.execute(
            select(
                PerformanceMetric.posted_hour,
                func.sum(PerformanceMetric.views).label("views"),
                func.sum(PerformanceMetric.chats).label("chats"),
                func.sum(PerformanceMetric.clicks).label("clicks"),
                func.sum(PerformanceMetric.favorites).label("favorites"),
            )
            .join(Publication, PerformanceMetric.publication_id == Publication.id)
            .join(OlxAccount, Publication.olx_account_id == OlxAccount.id)
            .where(OlxAccount.user_id == user.id)
            .group_by(PerformanceMetric.posted_hour)
            .order_by(PerformanceMetric.posted_hour)
        )
        by_hour = result.all()

        # Best performing hours
        result = await db.execute(
            select(
                PerformanceMetric.posted_weekday,
                func.sum(PerformanceMetric.views).label("views"),
                func.sum(PerformanceMetric.chats).label("chats"),
            )
            .join(Publication, PerformanceMetric.publication_id == Publication.id)
            .join(OlxAccount, Publication.olx_account_id == OlxAccount.id)
            .where(OlxAccount.user_id == user.id)
            .group_by(PerformanceMetric.posted_weekday)
            .order_by(PerformanceMetric.posted_weekday)
        )
        by_weekday = result.all()

        return {
            "by_hour": [{
                "hour": row[0],
                "views": row[1] or 0,
                "chats": row[2] or 0,
                "clicks": row[3] or 0,
                "favorites": row[4] or 0,
            } for row in by_hour],
            "by_weekday": [{
                "weekday": row[0],
                "views": row[1] or 0,
                "chats": row[2] or 0,
            } for row in by_weekday],
        }


@router.get("/exposure-calendar")
async def exposure_calendar(user: User = Depends(get_current_user)):
    """Visual representation of the Motor de Exposição's plan for the month."""
    from app.models import ExposureSchedule, Product, AdVariation

    async with async_session() as db:
        result = await db.execute(
            select(ExposureSchedule, Product, AdVariation)
            .outerjoin(Product, ExposureSchedule.product_id == Product.id)
            .outerjoin(AdVariation, ExposureSchedule.variation_id == AdVariation.id)
            .where(
                and_(
                    ExposureSchedule.user_id == user.id,
                    ExposureSchedule.is_skipped == False,
                )
            )
            .order_by(ExposureSchedule.scheduled_time)
        )
        rows = result.all()

        return [{
            "scheduled_time": entry.scheduled_time.isoformat(),
            "product_title": product.title if product else None,
            "variation_title": variation.title if variation else None,
            "is_executed": entry.is_executed,
            "priority": entry.priority,
        } for entry, product, variation in rows]
