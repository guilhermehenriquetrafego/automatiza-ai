"""
AUTOMATIZA AI — Similarity Checker
Ensures no two variations of the same product are too similar.
Uses PostgreSQL pg_trgm (trigram similarity) for text comparison.
Threshold: 60% — anything above is rejected.
"""

from __future__ import annotations

import uuid
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings

settings = get_settings()


class SimilarityChecker:
    """
    Checks similarity between a new variation's title/description and all existing ones.
    Uses PostgreSQL's pg_trgm extension for fast trigram comparison.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_variation(self, product_id: uuid.UUID, title: str, description: str) -> float:
        """
        Returns the maximum similarity score (0.0 to 1.0) of the new title+description
        against all existing variations of the same product.
        """
        # Use raw SQL for pg_trgm similarity function
        query = text("""
            SELECT MAX(
                GREATEST(
                    similarity(:new_title, title),
                    similarity(:new_desc, description)
                )
            ) as max_sim
            FROM ad_variations
            WHERE product_id = :product_id
        """)

        result = await self.db.execute(query, {
            "new_title": title,
            "new_desc": description,
            "product_id": str(product_id),
        })
        row = result.fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

    async def install_pg_trgm(self):
        """Install the pg_trgm extension if not already installed."""
        await self.db.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await self.db.commit()

    async def check_title_uniqueness(self, product_id: uuid.UUID, title: str) -> float:
        """Check just the title similarity."""
        query = text("""
            SELECT MAX(similarity(:new_title, title)) as max_sim
            FROM ad_variations
            WHERE product_id = :product_id
        """)
        result = await self.db.execute(query, {
            "new_title": title,
            "product_id": str(product_id),
        })
        row = result.fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

    async def check_image_duplicate(self, perceptual_hash: str, user_id: uuid.UUID) -> bool:
        """
        Check if an image with the same perceptual hash already exists
        for any product of this user.
        """
        query = text("""
            SELECT EXISTS(
                SELECT 1 FROM product_images pi
                JOIN products p ON pi.product_id = p.id
                WHERE p.user_id = :user_id
                AND pi.perceptual_hash = :hash
            ) as exists
        """)
        result = await self.db.execute(query, {
            "user_id": str(user_id),
            "hash": perceptual_hash,
        })
        row = result.fetchone()
        return bool(row[0]) if row else False
