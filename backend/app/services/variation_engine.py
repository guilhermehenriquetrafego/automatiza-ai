"""
AUTOMATIZA AI — Motor de Variações (IA)
Generates unique ad variations: title, description, and AI image per product.

Rules enforced:
  - No title can be identical OR too similar to another variation of the same product
  - Same for descriptions
  - Images must be unique (AI-generated, never reuse original or other variation's image)
  - Image generation uses gpt-image-2 (ChatGPT Images 2.0) — OpenAI's latest model
  - SEO: each variation uses a different "angle" (brand+model, intent, comparison, etc.)
"""

from __future__ import annotations

import base64
import httpx
import uuid
from typing import Optional
from loguru import logger

from openai import AsyncOpenAI
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Product, ProductImage, AdVariation, VariationStatus,
    OlxCategory
)
from app.services.storage import R2Storage
from app.services.similarity import SimilarityChecker

settings = get_settings()
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# SEO angles — each variation uses a different approach to the title/description
SEO_ANGLES = [
    {
        "id": "marca_modelo",
        "instruction": "Comece com a marca e modelo do produto, seguido dos atributos principais",
        "example": "Apple iPhone 15 Pro Max 256GB Azul Titânio",
    },
    {
        "id": "intent_compra",
        "instruction": "Foque na intenção de compra — o que o comprador procura",
        "example": "iPhone 15 Pro Max Original 256GB Estado de Zero",
    },
    {
        "id": "atributo_destaque",
        "instruction": "Destaque o atributo mais valioso do produto primeiro",
        "example": "256GB iPhone 15 Pro Max Azul Titânio Apple Original",
    },
    {
        "id": "categoria_ampla",
        "instruction": "Use termos de busca mais amplos da categoria",
        "example": "Celular Apple iPhone 15 Pro Max 256GB Novo",
    },
    {
        "id": "premio_qualidade",
        "instruction": "Enfatize qualidade, originalidade e garantia",
        "example": "iPhone 15 Pro Max Apple Original Lacrado 256GB",
    },
    {
        "id": "comparativo",
        "instruction": "Posicione comparando com modelo anterior ou similar",
        "example": "iPhone 15 Pro Max 256GB Superior ao 14 Pro Melhor Câmera",
    },
    {
        "id": "regiao_entrega",
        "instruction": "Inclua termos de disponibilidade e entrega se aplicável",
        "example": "iPhone 15 Pro Max 256GB Azul Pronta Entrega",
    },
    {
        "id": "tecnico_detalhado",
        "instruction": "Foque em especificações técnicas detalhadas",
        "example": "Apple iPhone 15 Pro Max 256GB Chip A17 Pro Câmera 48MP",
    },
]


class VariationEngine:
    """
    Generates unique variations of a product's title, description, and image.
    Each variation is SEO-optimized using a different angle.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = R2Storage()
        self.similarity = SimilarityChecker(db)

    async def generate_variations_for_product(
        self,
        product_id: uuid.UUID,
        count: int = 8,
        round_num: int = 2,
    ) -> list[AdVariation]:
        """
        Generate `count` unique variations for a product.
        Round 1 = the original (user's input). Round 2+ = AI generated.
        """
        # Load product
        product = await self.db.get(Product, product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Load images
        images_result = await self.db.execute(
            select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.sort_order)
        )
        images = images_result.scalars().all()

        # Load existing variations (to avoid duplicates)
        existing_result = await self.db.execute(
            select(AdVariation).where(AdVariation.product_id == product_id)
        )
        existing = existing_result.scalars().all()
        existing_titles = [v.title for v in existing]
        existing_descriptions = [v.description for v in existing]

        # Select which angles to use (avoid repeating angles from previous rounds)
        used_angles = {v.seo_angle for v in existing if v.seo_angle}
        available_angles = [a for a in SEO_ANGLES if a["id"] not in used_angles]
        if not available_angles:
            available_angles = SEO_ANGLES  # reset if all used

        # Limit to available angles
        angles_to_use = available_angles[:count]

        variations: list[AdVariation] = []

        for angle in angles_to_use:
            try:
                # 1. Generate unique title
                title = await self._generate_title(product, angle, existing_titles)
                if not title:
                    logger.warning(f"Failed to generate title for product {product_id}, angle {angle['id']}")
                    continue

                # 2. Generate unique description
                description = await self._generate_description(product, angle, existing_descriptions)
                if not description:
                    logger.warning(f"Failed to generate description for product {product_id}")
                    continue

                # 3. Generate AI image (only 1 per variation to save tokens)
                image_url = None
                image_r2_key = None
                if images:
                    image_url, image_r2_key = await self._generate_image(product, images)

                # 4. Verify similarity is acceptable
                sim_score = await self.similarity.check_variation(product_id, title, description)
                if sim_score > settings.EXPOSURE_SIMILARITY_THRESHOLD:
                    logger.warning(f"Variation too similar (score={sim_score:.2f}), regenerating...")
                    # Try once more with more explicit instruction
                    title = await self._generate_title(product, angle, existing_titles + [title])
                    description = await self._generate_description(product, angle, existing_descriptions + [description])
                    sim_score = await self.similarity.check_variation(product_id, title, description)
                    if sim_score > settings.EXPOSURE_SIMILARITY_THRESHOLD:
                        logger.warning(f"Still too similar after retry, skipping this variation")
                        continue

                # 5. Create variation record
                variation = AdVariation(
                    product_id=product_id,
                    title=title,
                    description=description,
                    image_url=image_url,
                    image_r2_key=image_r2_key,
                    variation_round=round_num,
                    seo_angle=angle["id"],
                    similarity_score=sim_score,
                    status=VariationStatus.ready,
                )
                self.db.add(variation)
                variations.append(variation)

                # Track to avoid duplicates in next iterations
                existing_titles.append(title)
                existing_descriptions.append(description)

            except Exception as e:
                logger.error(f"Error generating variation for product {product_id}: {e}")
                continue

        await self.db.commit()
        logger.info(f"Generated {len(variations)} variations for product {product_id}")
        return variations

    # ============================================================
    # TITLE GENERATION
    # ============================================================

    async def _generate_title(self, product: Product, angle: dict, existing_titles: list[str]) -> Optional[str]:
        """Generate a unique, SEO-optimized title using GPT-4o."""
        category_map = {
            OlxCategory.celulares_telefonia: "celulares e telefonia",
            OlxCategory.informatica: "informática",
            OlxCategory.games: "games e videogames",
            OlxCategory.audio: "áudio e som",
            OlxCategory.tvs_e_video: "TVs e vídeo",
            OlxCategory.cameras_e_drones: "câmeras e drones",
        }

        prompt = f"""Você é um especialista em SEO para a OLX Brasil. Gere UM título de anúncio único para o produto abaixo.

PRODUTO:
- Nome: {product.title}
- Marca: {product.brand or 'N/A'}
- Modelo: {product.model or 'N/A'}
- Categoria: {category_map.get(product.category, 'diversos')}
- Preço: R$ {product.price:.2f}
- Condição: {product.condition}
- Specs: {product.specs or {}}

ESTRATÉGIA SEO: {angle['instruction']}
EXEMPLO deste estilo: {angle['example']}

REGRAS OBRIGATÓRIAS:
1. Máximo 80 caracteres
2. NÃO pode ser igual nem muito parecido com estes títulos já existentes: {existing_titles}
3. Inclua as palavras-chave mais buscadas na categoria
4. Seja natural — não soe como robô
5. Inclua marca, modelo e atributo principal
6. Não use caracteres especiais desnecessários
7. Em português do Brasil

Responda APENAS com o título, sem explicações."""

        response = await client.chat.completions.create(
            model=settings.OPENAI_TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.8,
        )
        title = response.choices[0].message.content.strip()
        # Clean up: remove quotes if present, trim
        title = title.strip('"').strip("'").strip()
        if len(title) > 80:
            title = title[:77] + "..."
        return title

    # ============================================================
    # DESCRIPTION GENERATION
    # ============================================================

    async def _generate_description(self, product: Product, angle: dict, existing_descs: list[str]) -> Optional[str]:
        """Generate a unique, compelling description using GPT-4o."""
        prompt = f"""Você é um especialista em copywriting para anúncios da OLX Brasil. Gere UMA descrição única para o produto abaixo.

PRODUTO:
- Nome: {product.title}
- Marca: {product.brand or 'N/A'}
- Modelo: {product.model or 'N/A'}
- Preço: R$ {product.price:.2f}
- Condição: {product.condition}
- Specs: {product.specs or {}}

Descrição original do vendedor (use como base, mas reescreva completamente):
{product.description}

ESTRATÉGIA: {angle['instruction']}

REGRAS OBRIGATÓRIAS:
1. NÃO pode ser igual nem muito parecida com estas descrições já existentes: {[d[:100] for d in existing_descs]}
2. Mude a estrutura: ordem dos parágrafos, bullet points, CTA
3. Inclua palavras-chave de busca naturalmente
4. Máximo 1500 caracteres
5. Em português do Brasil
6. Inclua um call-to-action no final (ex: "Chame no chat para mais informações" ou similar)
7. NÃO invente especificações que não estão nos dados do produto
8. Varie o tom: uma mais formal, outra mais casual, etc.

Responda APENAS com a descrição, sem explicações."""

        response = await client.chat.completions.create(
            model=settings.OPENAI_TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.85,
        )
        desc = response.choices[0].message.content.strip()
        return desc

    # ============================================================
    # IMAGE GENERATION (gpt-image-2)
    # ============================================================

    async def _generate_image(self, product: Product, images: list[ProductImage]) -> tuple[Optional[str], Optional[str]]:
        """
        Generate ONE unique product image using gpt-image-2 (ChatGPT Images 2.0).
        Takes the original images as reference, identifies the product, and generates a new image.
        Only generates 1 image per variation to conserve tokens.
        """
        # Download the primary image to use as reference
        primary_image = next((img for img in images if img.is_primary), images[0]) if images else None
        if not primary_image:
            return None, None

        try:
            # Download original image
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.get(primary_image.url, timeout=30.0)
                resp.raise_for_status()
                image_bytes = resp.content

            # Build prompt for image generation
            category_map = {
                OlxCategory.celulares_telefonia: "smartphone/celular",
                OlxCategory.informatica: "notebook/computador",
                OlxCategory.games: "videogame/console",
                OlxCategory.audio: "caixa de som/fone",
                OlxCategory.tvs_e_video: "TV/monitor",
                OlxCategory.cameras_e_drones: "câmera/drone",
            }
            product_type = category_map.get(product.category, "produto eletrônico")

            prompt = f"""Generate a clean, professional product photo of a {product_type}.
Product: {product.title}
Brand: {product.brand or ''}
Model: {product.model or ''}

Requirements:
- White or light neutral background (studio style)
- Product centered, well-lit, professional e-commerce style
- High detail, photorealistic
- Different angle or composition from typical product shots
- Do NOT add text, watermarks, or logos
- The product must look exactly as described — do not alter its color, shape, or features"""

            # Call gpt-image-2 with image reference
            import asyncio
            # Convert image bytes to base64 for the API
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')

            response = await client.images.edit(
                model=settings.OPENAI_IMAGE_MODEL,  # gpt-image-2
                image=image_b64,
                prompt=prompt,
                size="1024x1024",
                n=1,
            )

            # gpt-image-2 returns base64-encoded images
            if response.data and response.data[0].b64_json:
                generated_bytes = base64.b64decode(response.data[0].b64_json)
            elif response.data and response.data[0].url:
                # If URL is returned instead, download it
                async with httpx.AsyncClient() as http_client:
                    img_resp = await http_client.get(response.data[0].url, timeout=30.0)
                    generated_bytes = img_resp.content
            else:
                logger.error("No image data returned from gpt-image-2")
                return None, None

            # Upload to R2
            r2_key = f"variations/{uuid.uuid4()}.png"
            url = await self.storage.upload(generated_bytes, r2_key, content_type="image/png")
            return url, r2_key

        except Exception as e:
            logger.error(f"Error generating image with gpt-image-2: {e}")
            return None, None
