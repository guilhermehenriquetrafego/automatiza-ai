"""
AUTOMATIZA AI — Celery Tasks
Scheduled and on-demand tasks that run the system autonomously.

Key tasks:
  1. exposure_engine_run — daily midnight: full recalculation of the publishing calendar
  2. sync_olx_limits — every 30 min: scrape OLX accounts for current limits
  3. execute_scheduled_publications — every 5 min: post ads that are scheduled
  4. generate_variations — on demand: generate new variations when running low
  5. read_and_respond_chats — every 2 min: scrape OLX chats and respond with AI
  6. scrape_performance — daily: collect views/clicks for all active ads
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from loguru import logger
from celery import Celery
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Celery app
celery_app = Celery(
    "automatiza_ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
)

# Database session for tasks
engine = create_async_engine(settings.DATABASE_URL, pool_size=3, max_overflow=2)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def run_async(coro):
    """Helper to run async functions in Celery's sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================
# TASK 1: MOTOR DE EXPOSIÇÃO — Daily Recalculation
# ============================================================

@celery_app.task(name="exposure_engine_run")
def exposure_engine_run(user_id: str):
    """Run the Motor de Exposição — full recalculation of publishing calendar. Daily at midnight."""
    from app.services.exposure_engine import ExposureEngine

    async def _run():
        async with async_session() as db:
            engine = ExposureEngine(db)
            await engine.compute_calendar(uuid.UUID(user_id))

    run_async(_run())
    logger.info(f"Motor de Exposição executed for user {user_id}")


# ============================================================
# TASK 2: SYNC OLX LIMITS — Every 30 minutes
# ============================================================

@celery_app.task(name="sync_olx_limits")
def sync_olx_limits(account_id: str):
    """Sync ad limits from OLX account via CDP. Runs every 30 minutes per account."""
    from app.automation.cdp.olx_automation import OlxAutomation
    from app.models import OlxAccount

    async def _run():
        async with async_session() as db:
            account = await db.get(OlxAccount, uuid.UUID(account_id))
            if not account or not account.is_authenticated:
                return

            async with OlxAutomation(account, db) as olx:
                await olx.sync_limits()
                logger.info(f"Synced limits for account {account_id}")

    run_async(_run())


# ============================================================
# TASK 3: EXECUTE SCHEDULED PUBLICATIONS — Every 5 minutes
# ============================================================

@celery_app.task(name="execute_scheduled_publications")
def execute_scheduled_publications(user_id: str):
    """Check for scheduled publications whose time has come and post them via CDP."""
    from sqlalchemy import select, and_
    from app.models import (
        ExposureSchedule, Publication, AdVariation, Product,
        OlxAccount, PublicationStatus, VariationStatus
    )
    from app.automation.cdp.olx_automation import OlxAutomation

    async def _run():
        async with async_session() as db:
            # Get all schedule entries that are due
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(ExposureSchedule).where(
                    and_(
                        ExposureSchedule.user_id == uuid.UUID(user_id),
                        ExposureSchedule.is_executed == False,
                        ExposureSchedule.is_skipped == False,
                        ExposureSchedule.scheduled_time <= now,
                    )
                ).order_by(ExposureSchedule.scheduled_time)
            )
            entries = result.scalars().all()

            if not entries:
                return

            logger.info(f"Found {len(entries)} scheduled publications to execute")

            for entry in entries:
                # Get the variation and product
                variation = await db.get(AdVariation, entry.variation_id)
                product = await db.get(Product, entry.product_id)
                account = await db.get(OlxAccount, entry.olx_account_id)

                if not all([variation, product, account]):
                    entry.is_skipped = True
                    entry.skip_reason = "Missing variation, product, or account"
                    continue

                # Create a publication record
                pub = Publication(
                    product_id=product.id,
                    variation_id=variation.id,
                    olx_account_id=account.id,
                    scheduled_for=entry.scheduled_time,
                    status=PublicationStatus.posting,
                )
                db.add(pub)
                await db.commit()

                # Post via CDP
                try:
                    async with OlxAutomation(account, db) as olx:
                        result = await olx.post_ad(variation, product)

                        if result.get("status") == PublicationStatus.online:
                            pub.olx_ad_id = result.get("olx_ad_id")
                            pub.olx_ad_url = result.get("olx_ad_url")
                            pub.status = PublicationStatus.online
                            pub.posted_at = datetime.now(timezone.utc)
                            variation.status = VariationStatus.used
                            entry.is_executed = True
                            logger.info(f"Published: {variation.title}")
                        else:
                            pub.status = PublicationStatus.failed
                            pub.error_message = result.get("error", "Unknown error")
                            entry.is_skipped = True
                            entry.skip_reason = pub.error_message
                            logger.error(f"Failed to publish: {pub.error_message}")

                except Exception as e:
                    pub.status = PublicationStatus.failed
                    pub.error_message = str(e)
                    entry.is_skipped = True
                    entry.skip_reason = str(e)
                    logger.error(f"Exception posting ad: {e}")

                await db.commit()

    run_async(_run())


# ============================================================
# TASK 4: GENERATE VARIATIONS — On demand / when running low
# ============================================================

@celery_app.task(name="generate_variations")
def generate_variations(product_id: str, count: int = 8, round_num: int = 2):
    """Generate new AI variations for a product."""
    from app.services.variation_engine import VariationEngine

    async def _run():
        async with async_session() as db:
            engine = VariationEngine(db)
            await engine.generate_variations_for_product(
                uuid.UUID(product_id), count, round_num
            )

    run_async(_run())


# ============================================================
# TASK 5: READ AND RESPOND CHATS — Every 2 minutes
# ============================================================

@celery_app.task(name="read_and_respond_chats")
def read_and_respond_chats(account_id: str):
    """Scrape OLX chat messages and respond with AI. Runs every 2 minutes per account."""
    from app.automation.cdp.olx_automation import OlxAutomation
    from app.ai.chat_ai import ChatAI
    from app.models import OlxAccount

    async def _run():
        async with async_session() as db:
            account = await db.get(OlxAccount, uuid.UUID(account_id))
            if not account or not account.is_authenticated:
                return

            async with OlxAutomation(account, db) as olx:
                messages = await olx.read_chat_messages()

                if not messages:
                    return

                chat_ai = ChatAI(db)
                for msg in messages:
                    result = await chat_ai.process_incoming_message(uuid.UUID(account_id), msg)

                    # Send the AI response back via CDP
                    if result.get("response") and not result.get("needs_human"):
                        await olx.send_chat_reply(result["conversation_id"], result["response"])

    run_async(_run())


# ============================================================
# TASK 6: SCRAPE PERFORMANCE — Daily
# ============================================================

@celery_app.task(name="scrape_performance")
def scrape_performance(user_id: str):
    """Scrape performance metrics (views, chats) for all active ads. Daily."""
    from sqlalchemy import select, and_
    from app.models import (
        Publication, PerformanceMetric, OlxAccount,
        PublicationStatus
    )
    from app.automation.cdp.olx_automation import OlxAutomation

    async def _run():
        async with async_session() as db:
            # Get all online publications for this user
            result = await db.execute(
                select(Publication, OlxAccount)
                .join(OlxAccount, Publication.olx_account_id == OlxAccount.id)
                .where(
                    and_(
                        OlxAccount.user_id == uuid.UUID(user_id),
                        Publication.status == PublicationStatus.online,
                    )
                )
            )
            rows = result.all()

            # Group by account
            accounts_pubs: dict[uuid.UUID, list[Publication]] = {}
            for pub, account in rows:
                accounts_pubs.setdefault(account.id, []).append(pub)

            for account_id, pubs in accounts_pubs.items():
                account = await db.get(OlxAccount, account_id)
                if not account:
                    continue

                async with OlxAutomation(account, db) as olx:
                    for pub in pubs:
                        try:
                            metrics = await olx.scrape_performance(pub)
                            if metrics:
                                # Find the hour and weekday when this was posted
                                posted_hour = pub.posted_at.hour if pub.posted_at else None
                                posted_weekday = pub.posted_at.weekday() if pub.posted_at else None

                                metric = PerformanceMetric(
                                    publication_id=pub.id,
                                    views=metrics.get("views", 0),
                                    clicks=metrics.get("clicks", 0),
                                    chats=metrics.get("chats", 0),
                                    favorites=metrics.get("favorites", 0),
                                    posted_hour=posted_hour,
                                    posted_weekday=posted_weekday,
                                )
                                db.add(metric)
                        except Exception as e:
                            logger.error(f"Error scraping performance for pub {pub.id}: {e}")

            await db.commit()

    run_async(_run())


# ============================================================
# CELERY BEAT SCHEDULE
# ============================================================

celery_app.conf.beat_schedule = {
    # Motor de Exposição — daily at midnight (Sao Paulo time)
    "exposure-engine-daily": {
        "task": "exposure_engine_run",
        "schedule": crontab(hour=0, minute=0),
        "args": [],  # will be dispatched per user
    },
    # Sync OLX limits — every 30 minutes
    "sync-olx-limits-30min": {
        "task": "sync_olx_limits",
        "schedule": crontab(minute="*/30"),
        "args": [],  # will be dispatched per account
    },
    # Execute scheduled publications — every 5 minutes
    "execute-publications-5min": {
        "task": "execute_scheduled_publications",
        "schedule": crontab(minute="*/5"),
        "args": [],  # will be dispatched per user
    },
    # Read and respond chats — every 2 minutes
    "read-chats-2min": {
        "task": "read_and_respond_chats",
        "schedule": crontab(minute="*/2"),
        "args": [],  # will be dispatched per account
    },
    # Scrape performance — daily at 23:00
    "scrape-performance-daily": {
        "task": "scrape_performance",
        "schedule": crontab(hour=23, minute=0),
        "args": [],  # will be dispatched per user
    },
}

# Import crontab here to avoid circular imports
from celery.schedules import crontab
