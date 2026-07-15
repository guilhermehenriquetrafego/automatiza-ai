"""
AUTOMATIZA AI — Motor de Exposição
O coração do sistema. Decide QUANDO, ONDE (qual conta) e O QUE publicar.

Objetivo: ESGOTAR o limite mensal de anúncios do usuário (ex: 250/250, nunca 240).
Estratégia: acumular anúncios durante o mês, distribuindo nos melhores horários.

Algoritmo:
  1. Soma o limite de anúncios de TODAS as contas OLX do usuário
  2. Divide pelo número de dias restantes no mês → meta diária
  3. Aplica pesos: fim de semana 1.3x, horários de pico têm prioridade
  4. Atribui variações (rodadas) por produto em round-robin
  5. Recalibra todo dia à meia-noite (ajusta baseado no que já foi publicado)
  6. Recalibra quando limites da OLX mudam (sync contínuo a cada 30 min)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict
from dataclasses import dataclass
import calendar
import math
import uuid

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    User, OlxAccount, Product, AdVariation, Publication,
    ExposureSchedule, PerformanceMetric, VariationStatus,
    PublicationStatus, OlxCategory
)
from loguru import logger

settings = get_settings()


@dataclass
class AccountCapacity:
    """How many ads an OLX account can still publish this month."""
    account_id: uuid.UUID
    remaining: int
    is_free: bool
    # For free accounts: { "celulares_e_telefonia": {"remaining": 3}, ... }
    category_remaining: dict | None = None


@dataclass
class DailyPlan:
    """The plan for a single day."""
    date: datetime
    target_publications: int
    slots: list[datetime]  # specific times to publish


class ExposureEngine:
    """
    Motor de Exposição — computes the optimal publishing calendar.

    Called by:
    - Celery Beat (daily at midnight) — full recalculation
    - Celery Beat (every 30 min) — adjusts for limit changes
    - On demand (when user adds/removes products or accounts)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_calendar(self, user_id: uuid.UUID) -> list[ExposureSchedule]:
        """
        Full computation: given the user's products, accounts, and remaining limits,
        compute the optimal schedule for the rest of the month.
        """
        # 1. Get all active OLX accounts and their remaining capacity
        accounts = await self._get_accounts_with_capacity(user_id)
        if not accounts:
            logger.warning(f"User {user_id} has no OLX accounts with capacity")
            return []

        total_remaining = sum(a.remaining for a in accounts)
        if total_remaining <= 0:
            logger.info(f"User {user_id} — all accounts exhausted this month")
            return []

        # 2. Get active products and their available variations
        products = await self._get_active_products(user_id)
        if not products:
            logger.warning(f"User {user_id} has no active products")
            return []

        # 3. Calculate days remaining in the month
        now = datetime.now(timezone.utc)
        last_day = calendar.monthrange(now.year, now.month)[1]
        end_of_month = datetime(now.year, now.month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        days_remaining = max(1, (end_of_month - now).days)

        # 4. Compute daily target
        daily_base = total_remaining / days_remaining

        # 5. Get learned peak hours from historical performance
        peak_hours = await self._get_learned_peak_hours(user_id)

        # 6. Build the calendar
        schedule_entries: list[ExposureSchedule] = []
        remaining_to_distribute = total_remaining

        for day_offset in range(days_remaining):
            day = now + timedelta(days=day_offset)
            is_weekend = day.weekday() >= 5  # Saturday=5, Sunday=6

            # Weekend weight
            day_weight = settings.EXPOSURE_WEEKEND_WEIGHT if is_weekend else 1.0

            # Daily target — proportional but capped to avoid burning everything early
            days_left = days_remaining - day_offset
            if days_left <= 1:
                # Last day — publish everything remaining
                daily_target = remaining_to_distribute
            else:
                # Weighted average: slightly front-load but not too much
                daily_target = math.ceil(daily_base * day_weight)
                # Cap at 150% of base to avoid burst
                daily_target = min(daily_target, int(daily_base * settings.EXPOSURE_MAX_DAILY_BURST))
                # Don't exceed what's left
                daily_target = min(daily_target, remaining_to_distribute)

            if daily_target <= 0:
                continue

            # 7. Assign time slots for this day
            slots = self._compute_slots(day, daily_target, peak_hours, is_weekend)

            # 8. Assign products/variations to each slot
            for slot_time, account in self._assign_to_slots(slots, accounts, products):
                if remaining_to_distribute <= 0:
                    break

                # Pick the next variation for a product
                variation, product = self._pick_next_variation(products)
                if not variation:
                    continue

                # Check account capacity (handle free accounts' category limits)
                if not self._can_publish_on_account(account, product):
                    continue

                entry = ExposureSchedule(
                    user_id=user_id,
                    olx_account_id=account.account_id,
                    scheduled_time=slot_time,
                    product_id=product.id,
                    variation_id=variation.id,
                    priority=self._compute_priority(product, variation, day, is_weekend),
                    is_executed=False,
                )
                schedule_entries.append(entry)
                remaining_to_distribute -= 1
                account.remaining -= 1
                if account.is_free and account.category_remaining:
                    cat_key = product.category.value
                    if cat_key in account.category_remaining:
                        account.category_remaining[cat_key]["remaining"] -= 1

        # 9. Clear old unexecuted schedule and save new
        await self._save_schedule(user_id, schedule_entries)

        logger.info(
            f"Motor de Exposição: {len(schedule_entries)} publications scheduled "
            f"for user {user_id} across {len(accounts)} accounts, "
            f"{days_remaining} days remaining"
        )
        return schedule_entries

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    async def _get_accounts_with_capacity(self, user_id: uuid.UUID) -> list[AccountCapacity]:
        """Get all OLX accounts with their remaining ad capacity."""
        result = await self.db.execute(
            select(OlxAccount).where(
                OlxAccount.user_id == user_id,
                OlxAccount.is_authenticated == True,
                OlxAccount.needs_reauth == False,
            )
        )
        accounts = result.scalars().all()

        capacities = []
        for acc in accounts:
            if acc.account_type.value == "professional":
                remaining = acc.remaining_this_month or 0
                capacities.append(AccountCapacity(
                    account_id=acc.id,
                    remaining=remaining,
                    is_free=False,
                ))
            else:
                # Free account — capacity is per category
                cat_remaining = {}
                if acc.category_limits:
                    for cat, limits in acc.category_limits.items():
                        remaining = limits.get("remaining", 0)
                        if remaining > 0:
                            cat_remaining[cat] = {"remaining": remaining}
                total = sum(c["remaining"] for c in cat_remaining.values())
                if total > 0:
                    capacities.append(AccountCapacity(
                        account_id=acc.id,
                        remaining=total,
                        is_free=True,
                        category_remaining=cat_remaining,
                    ))

        return capacities

    async def _get_active_products(self, user_id: uuid.UUID) -> list[tuple[Product, list[AdVariation]]]:
        """Get all active products with their ready-to-use variations."""
        result = await self.db.execute(
            select(Product).where(
                Product.user_id == user_id,
                Product.is_active == True,
            )
        )
        products = result.scalars().all()

        product_variations = []
        for product in products:
            # Get variations that are ready and not yet used
            var_result = await self.db.execute(
                select(AdVariation).where(
                    AdVariation.product_id == product.id,
                    AdVariation.status == VariationStatus.ready,
                ).order_by(AdVariation.variation_round)
            )
            variations = var_result.scalars().all()
            if variations:
                product_variations.append((product, variations))

        return product_variations

    async def _get_learned_peak_hours(self, user_id: uuid.UUID) -> list[int]:
        """
        Learn from historical performance which hours generate most engagement.
        Falls back to default peak hours if not enough data yet.
        """
        # Query: group by posted_hour, sum chats + views
        result = await self.db.execute(
            select(
                PerformanceMetric.posted_hour,
                func.sum(PerformanceMetric.chats + PerformanceMetric.views).label("engagement")
            )
            .join(Publication, PerformanceMetric.publication_id == Publication.id)
            .join(OlxAccount, Publication.olx_account_id == OlxAccount.id)
            .where(OlxAccount.user_id == user_id)
            .group_by(PerformanceMetric.posted_hour)
            .order_by(func.sum(PerformanceMetric.chats + PerformanceMetric.views).desc())
            .limit(6)
        )
        rows = result.all()

        if len(rows) < 3:
            # Not enough data — use defaults
            return settings.EXPOSURE_DEFAULT_PEAK_HOURS

        return [row[0] for row in rows if row[0] is not None]

    def _compute_slots(
        self, day: datetime, count: int, peak_hours: list[int], is_weekend: bool
    ) -> list[datetime]:
        """
        Distribute `count` publications across the day at strategic times.
        Uses peak hours as primary slots, fills with secondary hours.
        """
        slots = []
        base_date = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

        # Primary slots: peak hours
        primary_hours = peak_hours[:count] if len(peak_hours) >= count else peak_hours

        # Fill remaining with secondary hours (avoiding early morning)
        secondary_hours = [8, 10, 11, 14, 15, 16, 17, 19, 21, 22]
        all_hours = list(peak_hours)
        for h in secondary_hours:
            if h not in all_hours:
                all_hours.append(h)

        # Assign hours with jitter (±15 min) to avoid robotic timing
        import random
        for i in range(count):
            hour = all_hours[i % len(all_hours)]
            minute = random.randint(0, 45)  # jitter
            slot = base_date + timedelta(hours=hour, minutes=minute)
            slots.append(slot)

        slots.sort()
        return slots

    def _assign_to_slots(
        self,
        slots: list[datetime],
        accounts: list[AccountCapacity],
        products: list[tuple[Product, list[AdVariation]]],
    ):
        """
        Assign each time slot to an OLX account (load-balanced).
        Yields (slot_time, account) pairs.
        """
        # Sort accounts by remaining capacity (descending) for load balancing
        available_accounts = [a for a in accounts if a.remaining > 0]
        if not available_accounts:
            return

        account_idx = 0
        for slot in slots:
            # Rotate to next available account
            while available_accounts and available_accounts[account_idx].remaining <= 0:
                available_accounts.pop(account_idx)
                if account_idx >= len(available_accounts):
                    account_idx = 0
            if not available_accounts:
                break

            account = available_accounts[account_idx]
            yield (slot, account)
            account_idx = (account_idx + 1) % len(available_accounts)

    def _pick_next_variation(
        self, products: list[tuple[Product, list[AdVariation]]]
    ) -> tuple[Optional[AdVariation], Optional[Product]]:
        """
        Pick the next variation using round-robin across products.
        Prioritizes products with the most unused variations (to avoid starving any product).
        """
        # Sort by number of available variations (descending) to ensure balanced distribution
        sorted_products = sorted(products, key=lambda p: len(p[1]), reverse=True)

        for product, variations in sorted_products:
            if variations:
                # Pop the first available variation
                variation = variations.pop(0)
                return variation, product

        return None, None

    def _can_publish_on_account(self, account: AccountCapacity, product: Product) -> bool:
        """Check if a product can be published on a given account (handles free account category limits)."""
        if not account.is_free:
            return account.remaining > 0

        # Free account — check category-specific capacity
        if not account.category_remaining:
            return False

        cat_key = product.category.value
        return account.category_remaining.get(cat_key, {}).get("remaining", 0) > 0

    def _compute_priority(self, product: Product, variation: AdVariation, day: datetime, is_weekend: bool) -> int:
        """Compute priority score for a schedule entry."""
        base = 50
        # First variations (round 1) get slightly higher priority
        if variation.variation_round == 1:
            base += 10
        # Weekend boost
        if is_weekend:
            base += 5
        return base

    async def _save_schedule(self, user_id: uuid.UUID, entries: list[ExposureSchedule]):
        """Clear old unexecuted entries and save new schedule."""
        # Delete old unexecuted entries
        await self.db.execute(
            update(ExposureSchedule)
            .where(
                ExposureSchedule.user_id == user_id,
                ExposureSchedule.is_executed == False,
            )
            .values(is_skipped=True, skip_reason="Replaced by new schedule")
        )

        # Add new entries
        for entry in entries:
            self.db.add(entry)

        await self.db.commit()
