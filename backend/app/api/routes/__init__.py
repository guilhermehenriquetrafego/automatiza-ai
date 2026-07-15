"""
AUTOMATIZA AI — API Routes
All REST endpoints for the platform.
"""

# Auth routes — registration, login, token refresh
from app.api.routes import auth

# OLX Account routes — add/remove accounts, login to OLX, sync limits
from app.api.routes import accounts

# Product routes — CRUD for catalog, image upload
from app.api.routes import products

# Variation routes — generate and manage AI variations
from app.api.routes import variations

# Publication routes — view scheduled/active ads, manual publish
from app.api.routes import publications

# Chat routes — view chat messages, override AI responses
from app.api.routes import chat

# Dashboard routes — overview stats, performance metrics
from app.api.routes import dashboard

# CDP Live monitoring routes
from app.api.routes import cdp_live
