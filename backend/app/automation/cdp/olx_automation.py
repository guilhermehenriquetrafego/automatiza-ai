"""
AUTOMATIZA AI — OLX Automation
All OLX interactions via CDP. No API. No exceptions.

Functions:
  1. login(email, password) — authenticate on OLX (multi-step: email → continue → password → submit)
  2. post_ad(variation, product, account) — publish an ad
  3. sync_limits(account) — scrape current ad limits from account dashboard
  4. check_ad_status(ad_id) — verify if ad is online
  5. read_chat_messages() — scrape incoming chat messages
  6. send_chat_reply(conversation_id, message) — respond to a chat

Selectors discovered via Browserbase against real OLX pages (15/07/2026):
  - Login URL: https://conta.olx.com.br/
  - Email field: form input (input#input-1)
  - Continue button: form button
  - Cookie consent: button containing "Aceitar"
  - Login is multi-step: email → click Continuar → password → click Continuar
  - React controlled inputs (need type_text_react with proper event dispatching)
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from loguru import logger

from app.automation.cdp.stealth_browser import StealthBrowser, CDPError
from app.models import (
    OlxAccount, Product, AdVariation, Publication,
    PublicationStatus, OlxAccountType, ChatMessage, ChatDirection, ChatStatus,
    PerformanceMetric, OlxCategory
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


# OLX URLs (verified against real OLX 15/07/2026)
OLX_LOGIN_URL = "https://conta.olx.com.br/"
OLX_DASHBOARD_URL = "https://www.olx.com.br/conta/meuposicionamento"
OLX_POST_AD_URL = "https://www.olx.com.br/criar-anuncio"
OLX_AD_LIMITS_URL = "https://www.olx.com.br/conta/meusanuncios"
OLX_CHAT_URL = "https://www.olx.com.br/conta/mensagens"
OLX_HOME_URL = "https://www.olx.com.br"

# Real selectors discovered via Browserbase
OLX_SELECTORS = {
    # Login page (conta.olx.com.br)
    "login_email_input": "form input",
    "login_continue_btn": "form button",
    "login_password_input": "form input[type='password'], input#input-2, form input",
    "login_error": "[class*='error'], [class*='Error'], [role='alert']",
    # Cookie consent
    "cookie_accept": "button",  # Text content matching "Aceitar"
    # My ads page
    "ads_list": "[data-testid='ad-list'], .ad-card, [data-testid*='ad-card'], section[class*='ad']",
    "ads_count": "[data-testid='active-count'], .listing-count, [class*='count']",
    "limit_text": "[data-testid='ad-limit-text'], .ad-limit-info, .plan-usage, [class*='limit']",
    # Post ad page
    "post_title_input": "input[name='title'], #title, input[placeholder*='título'], form input",
    "post_desc_input": "textarea[name='description'], #description, textarea",
    "post_price_input": "input[name='price'], #price, input[placeholder*='preço']",
    "post_submit_btn": "button[type='submit'], button[data-testid='submit'], form button",
    # Chat
    "chat_list": "[data-testid='chat-list'], .chat-list, [class*='conversation']",
    "chat_msg": "[data-testid='message'], .message, [class*='message']",
}


class OlxAutomation:
    """
    Full OLX automation via CDP.
    One instance per OLX account. Never run two instances on the same account simultaneously.
    """

    def __init__(self, account: OlxAccount, db: AsyncSession):
        self.account = account
        self.db = db
        self.browser = StealthBrowser(headless=True)

    async def __aenter__(self):
        await self.browser.launch()
        # Restore session if available
        if self.account.session_data_encrypted:
            from app.core.security import decrypt_session
            session_data = decrypt_session(self.account.session_data_encrypted)
            await self.browser.restore_session(session_data)
        return self

    async def __aexit__(self, *args):
        # Save session for next time
        session_data = await self.browser.save_session()
        from app.core.security import encrypt_session
        self.account.session_data_encrypted = encrypt_session(json.dumps(session_data))
        self.account.session_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        await self.db.commit()
        await self.browser.close()

    # ============================================================
    # AUTHENTICATION
    # ============================================================

    async def login(self, email: str, password: str) -> bool:
        """
        Login to OLX using the multi-step flow.
        
        Step 1: Navigate to conta.olx.com.br
        Step 2: Accept cookies if present
        Step 3: Type email in form input
        Step 4: Click "Continuar" (form button)
        Step 5: Wait for password field to appear
        Step 6: Type password
        Step 7: Click "Continuar" again
        Step 8: Wait for redirect to www.olx.com.br (success indicator)
        """
        logger.info(f"Logging into OLX as {email}")

        # Step 1: Navigate to login page
        await self.browser.navigate(OLX_LOGIN_URL)
        await asyncio.sleep(2)

        # Step 2: Accept cookies if present
        await self.browser.accept_cookies(timeout=5.0)

        # Step 3: Wait for and fill email field
        # The OLX login page uses React with controlled inputs
        # The email field is the first input inside the form
        await self.browser.wait_for_selector(OLX_SELECTORS["login_email_input"], timeout=10.0)
        
        # Use type_text_react for React controlled inputs
        if hasattr(self.browser, 'type_text_react'):
            await self.browser.type_text_react(OLX_SELECTORS["login_email_input"], email)
        else:
            await self.browser.type_text(OLX_SELECTORS["login_email_input"], email)
        
        logger.debug("Email typed")

        # Step 4: Click "Continuar" button
        await self.browser.click(OLX_SELECTORS["login_continue_btn"])
        logger.debug("Continuar clicked (email step)")

        # Step 5: Wait for password field to appear
        # After clicking Continuar with a valid email, the form transitions to password step
        await asyncio.sleep(2)  # Give React time to transition
        
        # The password field might be the same input element (repurposed) or a new one
        # Try multiple selectors
        password_selector = None
        for selector in [
            "input[type='password']",
            "input#input-2",
            "input#input-1",  # Same field, repurposed
            "form input",
        ]:
            try:
                await self.browser.wait_for_selector(selector, timeout=5.0)
                password_selector = selector
                break
            except CDPError:
                continue
        
        if not password_selector:
            # Check for error message (invalid email)
            error_text = await self.browser.get_text(OLX_SELECTORS["login_error"])
            if error_text:
                logger.error(f"Login error: {error_text}")
            logger.error("Password field not found — email might be invalid")
            self.account.needs_reauth = True
            return False

        # Step 6: Type password
        if hasattr(self.browser, 'type_text_react'):
            await self.browser.type_text_react(password_selector, password)
        else:
            await self.browser.type_text(password_selector, password)
        
        logger.debug("Password typed")

        # Step 7: Click "Continuar" again to submit
        await self.browser.click(OLX_SELECTORS["login_continue_btn"])
        logger.debug("Continuar clicked (password step)")

        # Step 8: Wait for redirect to www.olx.com.br (success indicator)
        # On successful login, OLX redirects from conta.olx.com.br to www.olx.com.br
        try:
            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < 15.0:
                current_url = await self.browser.get_current_url() if hasattr(self.browser, 'get_current_url') else ""
                if current_url and "conta.olx.com.br" not in current_url:
                    # Redirected away from login page = success
                    logger.info(f"Login successful — redirected to {current_url}")
                    self.account.is_authenticated = True
                    self.account.needs_reauth = False
                    self.account.last_login_at = datetime.now(timezone.utc)
                    return True
                await asyncio.sleep(1)
            
            # Timeout — check if we're still on the login page (error) or if there's an error message
            error_text = await self.browser.get_text(OLX_SELECTORS["login_error"])
            if error_text:
                logger.error(f"Login error: {error_text}")
            else:
                logger.error("Login timeout — no redirect after 15s")
            self.account.needs_reauth = True
            return False
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            self.account.needs_reauth = True
            return False

    async def check_authenticated(self) -> bool:
        """Check if the current session is still authenticated by navigating to my ads page."""
        await self.browser.navigate(OLX_AD_LIMITS_URL)
        await asyncio.sleep(3)
        
        # If we're redirected to the login page, we're not authenticated
        current_url = await self.browser.get_current_url() if hasattr(self.browser, 'get_current_url') else ""
        if "conta.olx.com.br" in current_url or "entrar" in current_url.lower():
            self.account.needs_reauth = True
            return False
        
        # Try to find ads list elements (only visible when authenticated)
        try:
            await self.browser.wait_for_selector(OLX_SELECTORS["ads_list"], timeout=10.0)
            self.account.is_authenticated = True
            self.account.needs_reauth = False
            return True
        except CDPError:
            # Might be authenticated but page structure differs
            # Check URL — if we're on www.olx.com.br/conta/*, we're likely authenticated
            if "olx.com.br/conta" in current_url:
                self.account.is_authenticated = True
                self.account.needs_reauth = False
                return True
            self.account.needs_reauth = True
            return False

    # ============================================================
    # LIMIT SYNCING — The continuous scan
    # ============================================================

    async def sync_limits(self) -> dict:
        """
        Scrape the current ad limits from the OLX account dashboard.
        This is the "varredura contínua" — runs every 30 minutes.

        For professional accounts: total monthly limit (ex: 250) and used count.
        For free accounts: per-category limits.

        Returns the updated limit data.
        """
        logger.info(f"Syncing limits for account {self.account.id}")

        await self.browser.navigate(OLX_AD_LIMITS_URL)
        await asyncio.sleep(3)  # Let the page fully render (React SPA)

        # Check authentication first
        current_url = await self.browser.get_current_url() if hasattr(self.browser, 'get_current_url') else ""
        if "conta.olx.com.br" in current_url:
            logger.warning("Not authenticated — redirected to login")
            self.account.needs_reauth = True
            return {"error": "not_authenticated"}

        if self.account.account_type == OlxAccountType.professional:
            return await self._sync_professional_limits()
        else:
            return await self._sync_free_limits()

    async def _sync_professional_limits(self) -> dict:
        """Sync limits for a professional (paid) OLX account."""
        # The dashboard shows limit info somewhere on the page
        # Try multiple selectors for the limit text
        page_text = await self.browser.get_text("body")
        if not page_text:
            logger.warning("Could not get page text")
            return {"error": "no_page_text"}

        # Parse limit info from page text
        # OLX shows something like "X de Y" or "Você usou X inserções"
        # Also try to find specific limit elements
        limit_text = await self.browser.get_text(OLX_SELECTORS["limit_text"])
        
        all_text = (limit_text or "") + " " + page_text

        # Parse numbers from text like "45 de 250 anúncios usados"
        # Pattern 1: "X de Y" (most common)
        match = re.search(r'(\d+)\s*(?:de|dos?|\/)\s*(\d+)', all_text.replace('.', ''))
        if match:
            used = int(match.group(1))
            total = int(match.group(2))
            remaining = max(0, total - used)

            self.account.total_monthly_limit = total
            self.account.used_this_month = used
            self.account.remaining_this_month = remaining
            self.account.last_limit_sync = datetime.now(timezone.utc)

            logger.info(f"Professional limits synced: {used}/{total} used, {remaining} remaining")
            return {"total": total, "used": used, "remaining": remaining}

        # Pattern 2: "inserções" or "anúncios" with numbers nearby
        match = re.search(r'(\d+)\s*(?:inserç|anúnc|insert)', all_text.replace('.', ''), re.IGNORECASE)
        if match:
            used = int(match.group(1))
            # Try to find total nearby
            total_match = re.search(r'(?:limite|total|máximo)\s*(?:de\s*)?(\d+)', all_text.replace('.', ''), re.IGNORECASE)
            total = int(total_match.group(1)) if total_match else self.account.total_monthly_limit or 250
            
            remaining = max(0, total - used)
            self.account.used_this_month = used
            self.account.remaining_this_month = remaining
            self.account.total_monthly_limit = total
            self.account.last_limit_sync = datetime.now(timezone.utc)

            logger.info(f"Professional limits synced (pattern 2): {used}/{total}")
            return {"total": total, "used": used, "remaining": remaining}

        # Fallback: count active ads
        logger.warning("Could not parse limit text, counting active ads instead")
        ad_count = await self._count_active_ads()
        if self.account.total_monthly_limit > 0:
            self.account.used_this_month = ad_count
            self.account.remaining_this_month = max(0, self.account.total_monthly_limit - ad_count)
            self.account.last_limit_sync = datetime.now(timezone.utc)

        return {
            "total": self.account.total_monthly_limit,
            "used": ad_count,
            "remaining": self.account.remaining_this_month,
        }

    async def _sync_free_limits(self) -> dict:
        """Sync limits for a free OLX account — limits are per-category."""
        # Free accounts see their limits on the my-ads page
        page_text = await self.browser.get_text("body")
        if not page_text:
            return {"error": "no_page_text"}

        # Try to find limit text on the my-ads page
        limit_text = await self.browser.get_text(OLX_SELECTORS["limit_text"])
        all_text = (limit_text or "") + " " + page_text

        # Parse per-category limits
        # OLX free accounts typically show "X inserções gratuitas restantes"
        match = re.search(r'(\d+)\s*(?:inserç|anúnc|restant|dispon)', all_text.replace('.', ''), re.IGNORECASE)
        
        if match:
            remaining = int(match.group(1))
            self.account.remaining_this_month = remaining
            self.account.last_limit_sync = datetime.now(timezone.utc)
            
            # Free accounts typically have a total limit per month
            # Try to find total
            total_match = re.search(r'(?:total|máximo|limite)\s*(?:de\s*)?(\d+)', all_text.replace('.', ''), re.IGNORECASE)
            total = int(total_match.group(1)) if total_match else 50  # Default free limit
            used = max(0, total - remaining)
            
            self.account.total_monthly_limit = total
            self.account.used_this_month = used
            
            logger.info(f"Free account limits: {used}/{total} used, {remaining} remaining")
            return {"total": total, "used": used, "remaining": remaining}

        # Fallback: count active ads
        ad_count = await self._count_active_ads()
        self.account.used_this_month = ad_count
        self.account.last_limit_sync = datetime.now(timezone.utc)

        return {
            "total": self.account.total_monthly_limit,
            "used": ad_count,
            "remaining": max(0, (self.account.total_monthly_limit or 50) - ad_count),
        }

    async def _count_active_ads(self) -> int:
        """Count the number of active ads on the account."""
        # Try to find the count via JS evaluation
        result = await self.browser._evaluate_js("""
            (() => {
                // Try multiple selectors for ad cards
                const selectors = [
                    '[data-testid="ad-card"]',
                    '[data-testid*="ad-card"]',
                    '.ad-card',
                    '[class*="ad-card"]',
                    '[class*="AdCard"]',
                    '[data-testid="ad-list"] > *',
                    'section[class*="ad"]',
                    'article',
                ];
                for (const sel of selectors) {
                    const elements = document.querySelectorAll(sel);
                    if (elements.length > 0) {
                        return elements.length;
                    }
                }
                // Fallback: count elements that look like ad listings
                const allElements = document.querySelectorAll('[data-testid], [class*="ad"], [class*="Ad"]');
                return allElements.length;
            })()
        """)
        
        count = result.get("result", {}).get("value", 0) if result else 0
        if isinstance(count, dict):
            count = 0
            
        logger.info(f"Found {count} ad elements on page")
        return int(count) if count else 0

    # ============================================================
    # AD POSTING
    # ============================================================

    async def post_ad(self, variation: AdVariation, product: Product) -> Optional[Publication]:
        """
        Post an ad on OLX using CDP.
        Returns a Publication record if successful, None if failed.
        """
        logger.info(f"Posting ad for product {product.id}, variation {variation.id}")

        await self.browser.navigate(OLX_POST_AD_URL)
        await asyncio.sleep(3)

        # Accept cookies if present
        await self.browser.accept_cookies(timeout=3.0)

        # Select category (OLX has a category picker)
        await self._select_category(product.category)

        # Fill title
        await self.browser.wait_for_selector(OLX_SELECTORS["post_title_input"], timeout=10.0)
        if hasattr(self.browser, 'type_text_react'):
            await self.browser.type_text_react(OLX_SELECTORS["post_title_input"], variation.title)
        else:
            await self.browser.type_text(OLX_SELECTORS["post_title_input"], variation.title)

        # Fill description
        await self.browser.wait_for_selector(OLX_SELECTORS["post_desc_input"], timeout=5.0)
        if hasattr(self.browser, 'type_text_react'):
            await self.browser.type_text_react(OLX_SELECTORS["post_desc_input"], variation.description)
        else:
            await self.browser.type_text(OLX_SELECTORS["post_desc_input"], variation.description)

        # Fill price
        if product.price:
            await self.browser.wait_for_selector(OLX_SELECTORS["post_price_input"], timeout=5.0)
            if hasattr(self.browser, 'type_text_react'):
                await self.browser.type_text_react(OLX_SELECTORS["post_price_input"], str(product.price))
            else:
                await self.browser.type_text(OLX_SELECTORS["post_price_input"], str(product.price))

        # Upload images if available
        if variation.generated_image_url:
            # Download image to temp file and upload
            # TODO: Implement image download + upload
            pass

        # Submit the ad
        await self.browser.click(OLX_SELECTORS["post_submit_btn"])
        await asyncio.sleep(3)

        # Get the resulting URL (ad confirmation page)
        current_url = await self.browser.get_current_url() if hasattr(self.browser, 'get_current_url') else ""
        
        if "olx.com.br" in current_url and "criar-anuncio" not in current_url:
            # Redirected away from the form = success
            logger.info(f"Ad posted successfully: {current_url}")
            
            publication = Publication(
                variation_id=variation.id,
                account_id=self.account.id,
                status=PublicationStatus.active,
                olx_ad_url=current_url,
                posted_at=datetime.now(timezone.utc),
            )
            return publication
        else:
            logger.error("Ad posting failed — still on form page")
            return None

    async def _select_category(self, category: OlxCategory):
        """Select the product category on the OLX post ad form."""
        # OLX category mapping
        category_map = {
            OlxCategory.celulares: "Celulares",
            OlxCategory.informatica: "Informática",
            OlxCategory.games: "Games",
            OlxCategory.audio: "Áudio",
            OlxCategory.tvs: "TVs",
            OlxCategory.cameras: "Câmeras e Drones",
        }
        
        category_name = category_map.get(category, "Celulares")
        
        # Try to find and click the category
        result = await self.browser._evaluate_js(f"""
            (() => {{
                const links = document.querySelectorAll('a, button, [role="button"]');
                for (const link of links) {{
                    if (link.textContent && link.textContent.includes({json.dumps(category_name)})) {{
                        link.click();
                        return true;
                    }}
                }}
                return false;
            }})()
        """)
        
        await asyncio.sleep(1)

    # ============================================================
    # CHAT AUTOMATION
    # ============================================================

    async def read_chat_messages(self) -> list[dict]:
        """Read incoming chat messages from OLX."""
        await self.browser.navigate(OLX_CHAT_URL)
        await asyncio.sleep(3)

        # Extract chat messages via JS
        result = await self.browser._evaluate_js("""
            (() => {
                const messages = [];
                const msgElements = document.querySelectorAll(
                    '[data-testid="message"], .message, [class*="message"]'
                );
                msgElements.forEach(el => {
                    messages.push({
                        text: el.textContent,
                        sender: el.getAttribute('data-sender') || 'unknown',
                    });
                });
                return messages;
            })()
        """)
        
        messages = result.get("result", {}).get("value", []) if result else []
        return messages if isinstance(messages, list) else []

    async def send_chat_reply(self, conversation_id: str, message: str) -> bool:
        """Send a chat reply on OLX."""
        # Navigate to the specific conversation
        await self.browser.navigate(f"{OLX_CHAT_URL}/{conversation_id}")
        await asyncio.sleep(2)

        # Find the message input and type
        await self.browser.wait_for_selector(
            "textarea, input[type='text'][class*='message'], [data-testid='message-input']",
            timeout=10.0
        )
        
        if hasattr(self.browser, 'type_text_react'):
            await self.browser.type_text_react(
                "textarea, input[type='text'][class*='message'], [data-testid='message-input']",
                message
            )
        else:
            await self.browser.type_text(
                "textarea, input[type='text'][class*='message'], [data-testid='message-input']",
                message
            )

        # Send the message
        await self.browser.click(
            "button[type='submit'], button[data-testid='send'], [data-testid='send-button']"
        )
        
        await asyncio.sleep(1)
        logger.info(f"Chat reply sent to conversation {conversation_id}")
        return True

    # ============================================================
    # AD STATUS CHECK
    # ============================================================

    async def check_ad_status(self, ad_url: str) -> str:
        """Check if an ad is still active by visiting its URL."""
        await self.browser.navigate(ad_url)
        await asyncio.sleep(2)

        # Check if the ad page shows the product (active) or a removed message
        page_text = await self.browser.get_text("body")
        if not page_text:
            return "unknown"

        page_lower = page_text.lower()
        if "anúncio removido" in page_lower or "não está mais disponível" in page_lower:
            return "removed"
        elif "anúncio pausado" in page_lower:
            return "paused"
        elif "comprar" in page_lower or "vender" in page_lower or "contato" in page_lower:
            return "active"
        return "unknown"


# OLX Category URL paths for the post ad page
OlxCategoryUrls = {
    OlxCategory.celulares: "celulares-e-smartphones",
    OlxCategory.informatica: "computadores-e-acessorios",
    OlxCategory.games: "games",
    OlxCategory.audio: "audio",
    OlxCategory.tvs: "tvs",
    OlxCategory.cameras: "cameras-e-drones",
}
