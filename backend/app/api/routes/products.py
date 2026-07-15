"""Product routes — CRUD for catalog, image upload."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
import imagehash
import io
from PIL import Image

from app.models import async_session, User, Product, ProductImage, OlxCategory
from app.core.security import get_current_user
from app.services.storage import R2Storage
from app.services.similarity import SimilarityChecker

router = APIRouter()
storage = R2Storage()


class CreateProductRequest(BaseModel):
    title: str
    description: str
    price: float
    min_price: float | None = None
    category: str  # OlxCategory value
    subcategory: str | None = None
    brand: str | None = None
    model: str | None = None
    condition: str = "novo"
    specs: dict | None = None


class ProductResponse(BaseModel):
    id: str
    title: str
    description: str
    price: float
    min_price: float | None
    category: str
    subcategory: str | None
    brand: str | None
    model: str | None
    condition: str
    is_active: bool
    image_count: int = 0


@router.get("/")
async def list_products(user: User = Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(
            select(Product).where(
                Product.user_id == user.id,
                Product.is_active == True,
            ).order_by(Product.created_date.desc())
        )
        products = result.scalars().all()

        responses = []
        for p in products:
            img_result = await db.execute(
                select(func.count()).where(ProductImage.product_id == p.id)
            )
            img_count = img_result.scalar()
            responses.append(_to_response(p, img_count).model_dump())
        return responses


@router.post("/")
async def create_product(req: CreateProductRequest, user: User = Depends(get_current_user)):
    async with async_session() as db:
        count_result = await db.execute(
            select(func.count()).where(
                Product.user_id == user.id,
                Product.is_active == True,
            )
        )
        count = count_result.scalar()
        if count >= user.max_products:
            raise HTTPException(403, f"Product limit reached ({user.max_products})")

        product = Product(
            user_id=user.id,
            title=req.title,
            description=req.description,
            price=req.price,
            min_price=req.min_price,
            category=OlxCategory(req.category),
            subcategory=req.subcategory,
            brand=req.brand,
            model=req.model,
            condition=req.condition,
            specs=req.specs,
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)

        # Generate initial variations (safe — falls back to sync if no Redis)
        from app.tasks import safe_delay, generate_variations
        safe_delay(generate_variations, str(product.id), count=8, round_num=2)

        return _to_response(product, 0).model_dump()


@router.put("/{product_id}")
async def update_product(product_id: str, req: CreateProductRequest, user: User = Depends(get_current_user)):
    async with async_session() as db:
        product = await db.get(Product, uuid.UUID(product_id))
        if not product or product.user_id != user.id:
            raise HTTPException(404, "Product not found")

        product.title = req.title
        product.description = req.description
        product.price = req.price
        product.min_price = req.min_price
        product.category = OlxCategory(req.category)
        product.subcategory = req.subcategory
        product.brand = req.brand
        product.model = req.model
        product.condition = req.condition
        product.specs = req.specs
        await db.commit()
        await db.refresh(product)
        return _to_response(product, 0).model_dump()


@router.delete("/{product_id}")
async def delete_product(product_id: str, user: User = Depends(get_current_user)):
    async with async_session() as db:
        product = await db.get(Product, uuid.UUID(product_id))
        if not product or product.user_id != user.id:
            raise HTTPException(404, "Product not found")
        product.is_active = False
        await db.commit()
    return {"status": "deactivated"}


@router.post("/{product_id}/images")
async def upload_images(product_id: str, files: list[UploadFile] = File(...), user: User = Depends(get_current_user)):
    """Upload product images. Computes perceptual hash for duplicate detection."""
    async with async_session() as db:
        product = await db.get(Product, uuid.UUID(product_id))
        if not product or product.user_id != user.id:
            raise HTTPException(404, "Product not found")

        similarity = SimilarityChecker(db)
        uploaded = []

        for i, file in enumerate(files):
            content = await file.read()
            img = Image.open(io.BytesIO(content))

            phash = str(imagehash.phash(img))

            is_dup = await similarity.check_image_duplicate(phash, user.id)
            if is_dup:
                raise HTTPException(409, f"Image {file.filename} is a duplicate")

            r2_key = f"products/{product_id}/{uuid.uuid4()}.jpg"
            url = await storage.upload(content, r2_key, content_type="image/jpeg")
            if not url:
                raise HTTPException(500, f"Failed to upload {file.filename}")

            img_record = ProductImage(
                product_id=uuid.UUID(product_id),
                url=url,
                r2_key=r2_key,
                perceptual_hash=phash,
                is_primary=(i == 0),
                sort_order=i,
            )
            db.add(img_record)
            uploaded.append({"url": url, "hash": phash})

        await db.commit()
        return {"uploaded": uploaded}


def _to_response(p: Product, img_count: int = 0) -> ProductResponse:
    return ProductResponse(
        id=str(p.id),
        title=p.title,
        description=p.description,
        price=p.price,
        min_price=p.min_price,
        category=p.category.value,
        subcategory=p.subcategory,
        brand=p.brand,
        model=p.model,
        condition=p.condition,
        is_active=p.is_active,
        image_count=img_count,
    )
