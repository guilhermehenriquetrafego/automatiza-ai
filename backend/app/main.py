"""
AUTOMATIZA AI — FastAPI Application Entry Point
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import get_settings
from app.api.routes import (
    auth, products, accounts, dashboard, variations, publications, chat, cdp_live
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Sistema de Gestão de Exposição de Anúncios OLX",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
api_prefix = settings.API_PREFIX
app.include_router(auth.router, prefix=f"{api_prefix}/auth", tags=["Auth"])
app.include_router(accounts.router, prefix=f"{api_prefix}/accounts", tags=["OLX Accounts"])
app.include_router(products.router, prefix=f"{api_prefix}/products", tags=["Products"])
app.include_router(variations.router, prefix=f"{api_prefix}/variations", tags=["Variations"])
app.include_router(publications.router, prefix=f"{api_prefix}/publications", tags=["Publications"])
app.include_router(chat.router, prefix=f"{api_prefix}/chat", tags=["Chat"])
app.include_router(dashboard.router, prefix=f"{api_prefix}/dashboard", tags=["Dashboard"])
app.include_router(cdp_live.router, prefix=f"{api_prefix}/cdp-live", tags=["CDP Live"])


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/init-db")
async def init_db():
    """Initialize database tables. Call this once after deployment."""
    import traceback
    try:
        from app.models import Base, engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            await conn.run_sync(Base.metadata.create_all)
        return {"status": "success", "message": "Database initialized"}
    except Exception as e:
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}
