"""
AUTOMATIZA AI — Database Models
PostgreSQL via SQLAlchemy async. Designed for Supabase free tier (500MB).

Core entities:
  - User (tenant) — our customer
  - Plan — subscription tiers
  - OlxAccount — OLX accounts owned by a user (can be free or professional)
  - Product — items in the catalog
  - ProductImage — images for each product
  - AdVariation — generated variations (title, description, image) per product
  - Publication — a published (or scheduled) ad on an OLX account
  - ChatMessage — messages from OLX chat (scraped via CDP)
  - ExposureSchedule — the calendar computed by the Motor de Exposição
  - PerformanceMetric — tracks views, chats, CTR per variation/publication
"""

from __future__ import annotations

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey,
    Enum as SAEnum, JSON, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import get_settings

Base = declarative_base()
settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=5,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ============================================================
# ENUMS
# ============================================================

class PlanTier(str, enum.Enum):
    starter = "starter"
    pro = "pro"
    business = "business"
    enterprise = "enterprise"

class OlxAccountType(str, enum.Enum):
    free = "free"           # Conta gratuita — limites por categoria
    professional = "professional"  # Conta profissional/paga — limite compartilhado (ex: 250 diversos)

class OlxCategory(str, enum.Enum):
    celulares_telefonia = "celulares_e_telefonia"
    informatica = "informatica"
    games = "games"
    audio = "audio"
    tvs_e_video = "tvs_e_video"
    cameras_e_drones = "cameras_e_drones"

class PublicationStatus(str, enum.Enum):
    scheduled = "scheduled"
    posting = "posting"
    online = "online"
    failed = "failed"
    expired = "expired"
    deleted = "deleted"

class VariationStatus(str, enum.Enum):
    draft = "draft"
    ready = "ready"
    used = "used"  # already published

class ChatDirection(str, enum.Enum):
    incoming = "incoming"
    outgoing = "outgoing"

class ChatStatus(str, enum.Enum):
    pending = "pending"
    ai_responded = "ai_responded"
    human_needed = "human_needed"
    resolved = "resolved"


# ============================================================
# MODELS
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)

    # Subscription
    plan_tier = Column(SAEnum(PlanTier), default=PlanTier.starter, nullable=False)
    plan_expires_at = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)

    # Limits based on plan
    max_products = Column(Integer, default=10)
    max_olx_accounts = Column(Integer, default=1)

    is_active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    olx_accounts = relationship("OlxAccount", back_populates="user", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="user", cascade="all, delete-orphan")


class OlxAccount(Base):
    """An OLX account — can be free (per-category limits) or professional (shared limit)."""
    __tablename__ = "olx_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # OLX credentials (stored encrypted)
    email = Column(String(255), nullable=False)
    # Encrypted session data (cookies, localStorage, tokens) — for CDP session persistence
    session_data_encrypted = Column(Text, nullable=True)
    session_expires_at = Column(DateTime, nullable=True)

    # Account type
    account_type = Column(SAEnum(OlxAccountType), default=OlxAccountType.free, nullable=False)
    plan_name = Column(String(100), nullable=True)  # ex: "Diversos 250"

    # Dynamic limits — puxados da OLX via CDP e atualizados continuamente
    total_monthly_limit = Column(Integer, default=0)  # ex: 250 for professional, 0 for free (uses per-category)
    used_this_month = Column(Integer, default=0)
    remaining_this_month = Column(Integer, default=0)

    # For free accounts — per-category limits (JSON: {"celulares_e_telefonia": {"limit": 5, "used": 2}, ...})
    category_limits = Column(JSONB, nullable=True)

    # Status
    is_authenticated = Column(Boolean, default=False)
    needs_reauth = Column(Boolean, default=False)
    last_limit_sync = Column(DateTime, nullable=True)  # last time we synced limits from OLX

    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="olx_accounts")
    publications = relationship("Publication", back_populates="olx_account")
    chat_messages = relationship("ChatMessage", back_populates="olx_account")
    schedule_entries = relationship("ExposureSchedule", back_populates="olx_account")


class Product(Base):
    """A product in the user's catalog."""
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    min_price = Column(Float, nullable=True)  # minimum acceptable price for AI chat negotiation

    # Category
    category = Column(SAEnum(OlxCategory), nullable=False)
    subcategory = Column(String(100), nullable=True)  # OLX subcategory slug

    # Product details (for AI to use in variations)
    brand = Column(String(100), nullable=True)
    model = Column(String(200), nullable=True)
    condition = Column(String(50), default="novo")  # novo | seminovo | usado
    specs = Column(JSONB, nullable=True)  # { "storage": "256GB", "color": "azul", ... }

    # Status
    is_active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    variations = relationship("AdVariation", back_populates="product", cascade="all, delete-orphan")
    publications = relationship("Publication", back_populates="product")


class ProductImage(Base):
    """Original images uploaded by the user for a product."""
    __tablename__ = "product_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    url = Column(String(500), nullable=False)  # R2 public URL
    r2_key = Column(String(255), nullable=False)  # R2 storage key
    perceptual_hash = Column(String(64), nullable=True)  # for duplicate detection
    is_primary = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="images")


class AdVariation(Base):
    """A generated variation of a product — unique title, description, and image.
    Never reused. The Motor de Exposição picks from these to publish."""
    __tablename__ = "ad_variations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    # The variation
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)  # AI-generated image (R2 URL)
    image_r2_key = Column(String(255), nullable=True)

    # Generation metadata
    variation_round = Column(Integer, default=1)  # round 1 = original, 2+ = AI generated
    seo_angle = Column(String(100), nullable=True)  # ex: "marca_modelo", "intent_compra", "comparativo"
    similarity_score = Column(Float, nullable=True)  # computed against all other variations of same product

    # Status
    status = Column(SAEnum(VariationStatus), default=VariationStatus.draft, nullable=False)

    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="variations")
    publications = relationship("Publication", back_populates="variation")

    __table_args__ = (
        Index("idx_variations_product_status", "product_id", "status"),
    )


class Publication(Base):
    """A publication (posted or scheduled ad) on an OLX account."""
    __tablename__ = "publications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variation_id = Column(UUID(as_uuid=True), ForeignKey("ad_variations.id", ondelete="SET NULL"), nullable=True, index=True)
    olx_account_id = Column(UUID(as_uuid=True), ForeignKey("olx_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # OLX-side data (after posting)
    olx_ad_id = Column(String(100), nullable=True)  # OLX's internal ad ID
    olx_ad_url = Column(String(500), nullable=True)

    # Scheduling
    scheduled_for = Column(DateTime, nullable=True)  # when the Motor scheduled this
    posted_at = Column(DateTime, nullable=True)  # when it actually went live

    # Status
    status = Column(SAEnum(PublicationStatus), default=PublicationStatus.scheduled, nullable=False)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="publications")
    variation = relationship("AdVariation", back_populates="publications")
    olx_account = relationship("OlxAccount", back_populates="publications")
    metrics = relationship("PerformanceMetric", back_populates="publication", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_publications_status_scheduled", "status", "scheduled_for"),
        Index("idx_publications_account_month", "olx_account_id", "status"),
    )


class ChatMessage(Base):
    """Messages from OLX chat — scraped via CDP and responded by AI."""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    olx_account_id = Column(UUID(as_uuid=True), ForeignKey("olx_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # OLX chat context
    olx_conversation_id = Column(String(200), nullable=True)
    olx_ad_id = Column(String(100), nullable=True)
    buyer_name = Column(String(200), nullable=True)

    # Message
    direction = Column(SAEnum(ChatDirection), nullable=False)
    message_text = Column(Text, nullable=False)
    ai_generated = Column(Boolean, default=False)

    # Status
    status = Column(SAEnum(ChatStatus), default=ChatStatus.pending, nullable=False)

    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    olx_account = relationship("OlxAccount", back_populates="chat_messages")

    __table_args__ = (
        Index("idx_chat_account_status", "olx_account_id", "status"),
        Index("idx_chat_conversation", "olx_conversation_id"),
    )


class ExposureSchedule(Base):
    """The calendar entry computed by the Motor de Exposição.
    Each entry = one planned publication at a specific time, on a specific account."""
    __tablename__ = "exposure_schedule"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    olx_account_id = Column(UUID(as_uuid=True), ForeignKey("olx_accounts.id", ondelete="SET NULL"), nullable=True, index=True)

    scheduled_time = Column(DateTime, nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    variation_id = Column(UUID(as_uuid=True), ForeignKey("ad_variations.id", ondelete="SET NULL"), nullable=True)

    # Priority (higher = more important to publish)
    priority = Column(Integer, default=50)
    is_executed = Column(Boolean, default=False)
    is_skipped = Column(Boolean, default=False)
    skip_reason = Column(String(300), nullable=True)

    created_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    olx_account = relationship("OlxAccount", back_populates="schedule_entries")

    __table_args__ = (
        Index("idx_schedule_user_time", "user_id", "scheduled_time"),
        Index("idx_schedule_executed", "is_executed", "scheduled_time"),
    )


class PerformanceMetric(Base):
    """Tracks performance per publication — views, chats, CTR.
    Scraped periodically via CDP."""
    __tablename__ = "performance_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publication_id = Column(UUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), nullable=False, index=True)

    views = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    chats = Column(Integer, default=0)
    favorites = Column(Integer, default=0)

    # Hour of the day when this was posted (for learning peak hours)
    posted_hour = Column(Integer, nullable=True)
    posted_weekday = Column(Integer, nullable=True)  # 0=Monday, 6=Sunday

    measured_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    publication = relationship("Publication", back_populates="metrics")
