"""Variation routes — generate and manage AI variations."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional

from app.models import async_session, User, Product, AdVariation, VariationStatus
from app.core.security import get_current_user

router = APIRouter()


class VariationResponse(BaseModel):
    id: str
    product_id: str
    title: str
    description: str
    image_url: str | None
    variation_round: int
    seo_angle: str | None
    similarity_score: float | None
    status: str


@router.get("/product/{product_id}")
async def list_variations(product_id: str, user: User = Depends(get_current_user)):
    async with async_session() as db:
        product = await db.get(Product, uuid.UUID(product_id))
        if not product or product.user_id != user.id:
            raise HTTPException(404, "Product not found")

        result = await db.execute(
            select(AdVariation)
            .where(AdVariation.product_id == uuid.UUID(product_id))
            .order_by(AdVariation.variation_round, AdVariation.created_date)
        )
        variations = result.scalars().all()
        return [_to_response(v).model_dump() for v in variations]


@router.post("/product/{product_id}/generate")
async def generate_new_variations(
    product_id: str,
    count: int = 8,
    user: User = Depends(get_current_user),
):
    """Trigger AI generation of new variations for a product."""
    async with async_session() as db:
        product = await db.get(Product, uuid.UUID(product_id))
        if not product or product.user_id != user.id:
            raise HTTPException(404, "Product not found")

    from app.tasks import safe_delay, generate_variations as gen_variations
    safe_delay(gen_variations, product_id, count=count, round_num=2)
    return {"status": "generation_started", "count": count}


@router.put("/{variation_id}/status")
async def update_variation_status(variation_id: str, status: str, user: User = Depends(get_current_user)):
    async with async_session() as db:
        variation = await db.get(AdVariation, uuid.UUID(variation_id))
        if not variation:
            raise HTTPException(404, "Variation not found")
        variation.status = VariationStatus(status)
        await db.commit()
    return {"status": "updated"}


def _to_response(v: AdVariation) -> VariationResponse:
    return VariationResponse(
        id=str(v.id),
        product_id=str(v.product_id),
        title=v.title,
        description=v.description,
        image_url=v.image_url,
        variation_round=v.variation_round,
        seo_angle=v.seo_angle,
        similarity_score=v.similarity_score,
        status=v.status.value,
    )
