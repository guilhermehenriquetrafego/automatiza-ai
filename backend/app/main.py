"""
AUTOMATIZA AI — FastAPI Application Entry Point
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI, CORS
from loguru import logger

from app.core.config import get_settings
from app.api.routes import (
    auth, products, accounts, dashboard, variations, publications, chat
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    # Initialize database (create tables, install extensions)
    from app.models import Base, engine
    async with engine.begin() as conn:
        # Install pg_trgm for similarity checking
        from sqlalchemy import text
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")

    yield

    logger.info("Shutting down...")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Sistema de Gestão de Exposição de Anúncios OLX",
    lifespan=lifespan,
)

# CORS
from fastapi.middleware.cors import CORSMiddleware
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
