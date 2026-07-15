"""
AUTOMATIZA AI — Celery Tasks
Scheduled and on-demand tasks that run the system autonomously.

When Redis is not available, tasks run synchronously (fallback mode).
This allows the system to work without Redis during development/initial setup.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Celery app — use memory broker if Redis not configured
_broker = settings.CELERY_BROKER_URL or "memory://"
_backend = settings.CELERY_RESULT_BACKEND or "cache+memory://"

try:
    from celery import Celery
    celery_app = Celery(
        "automatiza_ai",
        broker=_broker,
        backend=_backend,
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
    CELERY_AVAILABLE = bool(settings.CELERY_BROKER_URL)
except ImportError:
    celery_app = None
    CELERY_AVAILABLE = False

# Database session for tasks
engine = create_async_engine(settings.DATABASE_URL, pool_size=3, max_overflow=2)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def run_async(coro):
    """Helper to run async functions in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def safe_delay(task, *args, **kwargs):
    """
    Try to send task to Celery (Redis broker).
    If Redis is not available, run the task synchronously as fallback.
    """
    if not CELERY_AVAILABLE:
        logger.info(f"Running {task.name} synchronously (no Redis)")
        try:
            task.apply(args=args, kwargs=kwargs)
        except Exception as e:
            logger.error(f"Task {task.name} failed synchronously: {e}")
        return

    try:
        task.delay(*args, **kwargs)
        logger.info(f"Task {task.name} queued via Celery")
    except Exception as e:
        logger.warning(f"Celery unavailable ({e}), running {task.name} synchronously")
        try:
            task.apply(args=args, kwargs=kwargs)
        except Exception as sync_err:
            logger.error(f"Task {task.name} failed synchronously: {sync_err}")


# ============================================================
# TASK 1: MOTOR DE EXPOSIÇÃO — Daily Recalculation
# ============================================================

@celery_app.task(name="exposure_engine_run")
def exposure_engine_run(user_id: str):
    """Run the Motor de Exposição — full recalculation of publishing calendar."""
    from app.services.exposure_engine import ExposureEngine

    async def _run():
        async with async_session() as db:
            engine = ExposureEngine(db)
            await engine.compute_calendar(uuid.UUID(user_id))

    run_async(_run())
    logger.info(f"Motor de Exposição executed for user {user_id}")


# ============================================================
# TASK 2: SYNC OLX LIMITS
# ============================================================

@celery_app.task(name="sync_olx_limits")
def sync_olx_limits(account_id: str):
    """Sync ad limits from OLX account via CDP."""
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
# TASK 3: EXECUTE SCHEDULED PUBLICATIONS
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
                variation = await db.get(AdVariation, entry.variation_id)
                product = await db.get(Product, entry.product_id)
                account = await db.get(OlxAccount, entry.olx_account_id)

                if not all([variation, product, account]):
                    entry.is_skipped = True
                    entry.skip_reason = "Missing variation, product, or account"
                    continue

                pub = Publication(
                    product_id=product.id,
                    variation_id=variation.id,
                    olx_account_id=account.id,
                    scheduled_for=entry.scheduled_time,
                    status=PublicationStatus.posting,
                )
                db.add(pub)
                await db.commit()

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
# TASK 5: READ AND RESPOND CHATS
# ============================================================

@celery_app.task(name="read_and_respond_chats")
def read_and_respond_chats(account_id: str):
    """Scrape OLX chat messages and respond with AI."""
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

            for pub, account in rows:
                try:
                    async with OlxAutomation(account, db) as olx:
                        metrics = await olx.scrape_ad_metrics(pub.olx_ad_id)

                        metric = PerformanceMetric(
                            publication_id=pub.id,
                            views=metrics.get("views", 0),
                            chats=metrics.get("chats", 0),
                            clicks=metrics.get("clicks", 0),
                            favorites=metrics.get("favorites", 0),
                        )
                        db.add(metric)
                except Exception as e:
                    logger.error(f"Failed to scrape metrics for pub {pub.id}: {e}")

            await db.commit()

    run_async(_run())
