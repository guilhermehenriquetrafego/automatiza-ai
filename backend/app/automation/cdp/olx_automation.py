"""
AUTOMATIZA AI — OLX Automation
All OLX interactions via CDP. No API. No exceptions.

Functions:
  1. login(email, password) — authenticate on OLX
  2. post_ad(variation, product, account) — publish an ad
  3. sync_limits(account) — scrape current ad limits from account dashboard
  4. check_ad_status(ad_id) — verify if ad is online
  5. read_chat_messages() — scrape incoming chat messages
  6. send_chat_reply(conversation_id, message) — respond to a chat
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
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


# OLX URLs
OLX_LOGIN_URL = "https://www.olx.com.br/entrar"
OLX_DASHBOARD_URL = "https://www.olx.com.br/conta/meuposicionamento"
OLX_POST_AD_URL = "https://www.olx.com.br/criar-anuncio"
OLX_AD_LIMITS_URL = "https://www.olx.com.br/conta/meusanuncios"
OLX_CHAT_URL = "https://www.olx.com.br/conta/mensagens"
OLX_FREE_LIMITS_HELP = "https://ajuda.olx.com.br/s/article/anuncio-pago-e-limites-de-insercao-gratuita"


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
        self.account.session_expires_at = datetime.now(timezone.utc) + asyncio.timedelta(days=30)
        await self.db.commit()
        await self.browser.close()

    # ============================================================
    # AUTHENTICATION
    # ============================================================

    async def login(self, email: str, password: str) -> bool:
        """Login to OLX. Returns True if successful."""
        logger.info(f"Logging into OLX as {email}")

        await self.browser.navigate(OLX_LOGIN_URL)

        # Wait for and fill email field
        await self.browser.wait_for_selector("input[name='email'], input[type='email'], #email")
        await self.browser.type_text("input[name='email'], input[type='email'], #email", email)

        # Click "Continue" or "Entrar"
        await self.browser.click("button[type='submit'], button[data-testid='login-button']")

        # Wait for password field
        await self.browser.wait_for_selector("input[name='password'], input[type='password'], #password")

        # Fill password
        await self.browser.type_text("input[name='password'], input[type='password'], #password", password)

        # Submit
        await self.browser.click("button[type='submit'], button[data-testid='login-button']")

        # Wait for redirect to dashboard (indicates success)
        try:
            await self.browser.wait_for_selector(
                "[data-testid='dashboard'], .user-info, #my-account",
                timeout=15.0
            )
            self.account.is_authenticated = True
            self.account.needs_reauth = False
            logger.info("OLX login successful")
            return True
        except Exception:
            logger.error("OLX login failed — probably wrong credentials or captcha")
            self.account.needs_reauth = True
            return False

    async def check_authenticated(self) -> bool:
        """Check if the current session is still authenticated."""
        await self.browser.navigate(OLX_DASHBOARD_URL)
        try:
            await self.browser.wait_for_selector(
                "[data-testid='dashboard'], .user-info, #my-account",
                timeout=10.0
            )
            self.account.is_authenticated = True
            self.account.needs_reauth = False
            return True
        except CDPError:
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
        await asyncio.sleep(2)  # Let the page fully render

        if self.account.account_type == OlxAccountType.professional:
            return await self._sync_professional_limits()
        else:
            return await self._sync_free_limits()

    async def _sync_professional_limits(self) -> dict:
        """Sync limits for a professional (paid) OLX account."""
        # The dashboard shows something like "Você usou X de Y anúncios"
        # We need to parse this text
        limit_text = await self.browser.get_text(
            "[data-testid='ad-limit-text'], .ad-limit-info, .plan-usage, "
            ".insertion-limit, .limit-info"
        )

        if limit_text:
            # Parse numbers from text like "45 de 250 anúncios usados"
            numbers = re.findall(r'\d+', limit_text.replace('.', ''))
            if len(numbers) >= 2:
                used = int(numbers[0])
                total = int(numbers[1])
                remaining = max(0, total - used)

                self.account.total_monthly_limit = total
                self.account.used_this_month = used
                self.account.remaining_this_month = remaining
                self.account.last_limit_sync = datetime.now(timezone.utc)

                logger.info(f"Professional limits synced: {used}/{total} used, {remaining} remaining")
                return {"total": total, "used": used, "remaining": remaining}

        # Fallback: try to count active ads
        logger.warning("Could not parse limit text, trying alternative method")
        ad_count = await self._count_active_ads()
        # If we know the plan limit, calculate remaining
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
        await self.browser.navigate(OLX_FREE_LIMITS_HELP)

        # On free accounts, we need to check each category's limit
        # The OLX post page shows remaining limits per category when you try to post
        category_limits = {}

        for category, url_path in OlxCategoryUrls.items():
            # Navigate to the "create ad" page for this category
            await self.browser.navigate(f"{OLX_POST_AD_URL}/{url_path}")
            await asyncio.sleep(1)

            # Try to find the limit indicator for this category
            limit_text = await self.browser.get_text(
                ".category-limit, .insertion-limit-text, "
                "[data-testid='category-limit']"
            )

            if limit_text:
                numbers = re.findall(r'\d+', limit_text.replace('.', ''))
                if len(numbers) >= 2:
                    limit = int(numbers[1])
                    used = int(numbers[0])
                    remaining = max(0, limit - used)
                    category_limits[category.value] = {
                        "limit": limit,
                        "used": used,
                        "remaining": remaining,
                    }

        self.account.category_limits = category_limits
        self.account.last_limit_sync = datetime.now(timezone.utc)

        total_remaining = sum(c["remaining"] for c in category_limits.values())
        self.account.remaining_this_month = total_remaining

        logger.info(f"Free account limits synced: {json.dumps(category_limits)}")
        return category_limits

    async def _count_active_ads(self) -> int:
        """Count the number of active ads on the account."""
        await self.browser.navigate(OLX_AD_LIMITS_URL)
        await asyncio.sleep(2)

        # Try to find the count of active listings
        count_text = await self.browser.get_text(
            ".active-ads-count, [data-testid='active-count'], "
            ".listing-count, .ads-count"
        )
        if count_text:
            numbers = re.findall(r'\d+', count_text.replace('.', ''))
            if numbers:
                return int(numbers[0])

        # Fallback: count ad cards on the page
        count = await self.browser._evaluate_js("""
            document.querySelectorAll('[data-testid="ad-card"], .ad-card, .listing-card').length
        """)
        return count.get("result", {}).get("value", 0)

    # ============================================================
    # AD POSTING
    # ============================================================

    async def post_ad(self, variation: AdVariation, product: Product) -> Optional[Publication]:
        """
        Post an ad on OLX using CDP. This is the core action.

        Steps:
        1. Navigate to "Create Ad" page
        2. Select category
        3. Fill title, description, price
        4. Upload image
        5. Submit
        6. Capture the ad URL/ID
        """
        logger.info(f"Posting ad: {variation.title}")

        # Navigate to create ad page
        await self.browser.navigate(OLX_POST_AD_URL)
        await self.browser.wait_for_selector("form, [data-testid='create-ad-form']")

        # 1. Select category
        await self._select_category(product.category, product.subcategory)

        # 2. Fill title
        await self.browser.wait_for_selector("input[name='title'], #title, [data-testid='title-input']")
        await self.browser.type_text("input[name='title'], #title, [data-testid='title-input']", variation.title)

        # 3. Fill description
        await self.browser.wait_for_selector("textarea[name='description'], #description, [data-testid='description-input']")
        await self.browser.type_text("textarea[name='description'], #description, [data-testid='description-input']", variation.description)

        # 4. Fill price
        price_input = "input[name='price'], #price, [data-testid='price-input']"
        await self.browser.wait_for_selector(price_input)
        price_str = str(int(product.price))  # OLX expects integer
        await self.browser.type_text(price_input, price_str)

        # 5. Upload image
        if variation.image_url:
            # Download the image to a temp file
            import httpx
            import tempfile
            import os

            async with httpx.AsyncClient() as client:
                resp = await client.get(variation.image_url, timeout=30.0)
                resp.raise_for_status()

            temp_dir = tempfile.mkdtemp()
            temp_file = os.path.join(temp_dir, f"ad_image_{uuid.uuid4().hex[:8]}.png")
            with open(temp_file, "wb") as f:
                f.write(resp.content)

            # Upload via file chooser interception
            upload_selector = "input[type='file'], [data-testid='image-upload'], .upload-area, .dropzone"
            await self.browser.upload_file(upload_selector, temp_file)

            # Wait for upload to complete
            await asyncio.sleep(3)
            await self.browser.wait_for_selector(
                ".uploaded-image, .image-preview, [data-testid='image-uploaded']",
                timeout=15.0
            )

            # Clean up temp file
            os.remove(temp_file)
            os.rmdir(temp_dir)

        # 6. Fill additional fields based on category
        await self._fill_category_specific_fields(product)

        # 7. Set condition
        condition_map = {
            "novo": "new",
            "seminovo": "used",
            "usado": "used",
        }
        condition_value = condition_map.get(product.condition, "used")
        await self._select_radio(f"[name='condition'], [data-testid='condition-{condition_value}']", condition_value)

        # 8. Submit the ad
        await self.browser.click("button[type='submit'], [data-testid='publish-button'], .submit-button")

        # 9. Wait for confirmation and capture ad URL
        try:
            await self.browser.wait_for_selector(
                ".success-message, [data-testid='ad-success'], .ad-published",
                timeout=20.0
            )
            # Capture the ad URL from the success page
            ad_url = await self.browser._evaluate_js("window.location.href")
            ad_url = ad_url.get("result", {}).get("value", "")
            olx_ad_id = self._extract_ad_id(ad_url)

            logger.info(f"Ad posted successfully: {ad_url}")
            return {
                "olx_ad_id": olx_ad_id,
                "olx_ad_url": ad_url,
                "status": PublicationStatus.online,
            }
        except CDPError:
            logger.error("Failed to confirm ad publication")
            return {
                "status": PublicationStatus.failed,
                "error": "Could not confirm publication",
            }

    async def _select_category(self, category: OlxCategory, subcategory: Optional[str]):
        """Select the OLX category and subcategory for the ad."""
        url_path = OlxCategoryUrls.get(category, "diversos")
        category_selector = f"[data-testid='category-{category.value}'], a[href*='{url_path}']"

        await self.browser.click(category_selector)
        await self.browser._human_delay()

        if subcategory:
            sub_selector = f"[data-testid='subcategory-{subcategory}'], a[href*='{subcategory}']"
            try:
                await self.browser.click(sub_selector)
            except CDPError:
                logger.warning(f"Subcategory {subcategory} not found, using main category")

    async def _fill_category_specific_fields(self, product: Product):
        """Fill category-specific fields based on the product."""
        # Different categories have different required fields
        # This is a simplified version — would need to be expanded per category

        if product.brand:
            brand_input = "input[name='brand'], #brand, [data-testid='brand-input']"
            try:
                await self.browser.wait_for_selector(brand_input, timeout=3.0)
                await self.browser.type_text(brand_input, product.brand)
            except CDPError:
                pass

        if product.model:
            model_input = "input[name='model'], #model, [data-testid='model-input']"
            try:
                await self.browser.wait_for_selector(model_input, timeout=3.0)
                await self.browser.type_text(model_input, product.model)
            except CDPError:
                pass

        # Fill specs if available
        if product.specs:
            for key, value in product.specs.items():
                field = f"input[name='{key}'], select[name='{key}'], [data-testid='{key}-input']"
                try:
                    await self.browser.wait_for_selector(field, timeout=2.0)
                    await self.browser.type_text(field, str(value))
                except CDPError:
                    pass

    async def _select_radio(self, selector: str, value: str):
        """Select a radio button or similar option."""
        try:
            await self.browser.click(selector)
        except CDPError:
            logger.warning(f"Could not select option: {selector}")

    def _extract_ad_id(self, url: str) -> Optional[str]:
        """Extract the OLX ad ID from the URL."""
        match = re.search(r'/(\d+)(?:\?|$|#)', url)
        return match.group(1) if match else None

    # ============================================================
    # PERFORMANCE SCRAPING
    # ============================================================

    async def scrape_performance(self, publication: Publication) -> dict:
        """
        Scrape performance metrics (views, chats) from a published ad.
        Navigates to the ad's dashboard page and extracts metrics.
        """
        if not publication.olx_ad_id:
            return {}

        await self.browser.navigate(f"{OLX_AD_LIMITS_URL}/{publication.olx_ad_id}")
        await asyncio.sleep(2)

        views = await self.browser.get_text(
            "[data-testid='view-count'], .views-count, .stat-views"
        )
        chats = await self.browser.get_text(
            "[data-testid='chat-count'], .chats-count, .stat-chats"
        )
        clicks = await self.browser.get_text(
            "[data-testid='click-count'], .clicks-count, .stat-clicks"
        )
        favorites = await self.browser.get_text(
            "[data-testid='favorite-count'], .favorites-count, .stat-favorites"
        )

        def parse_num(text):
            if not text:
                return 0
            nums = re.findall(r'\d+', text.replace('.', ''))
            return int(nums[0]) if nums else 0

        return {
            "views": parse_num(views),
            "chats": parse_num(chats),
            "clicks": parse_num(clicks),
            "favorites": parse_num(favorites),
        }

    # ============================================================
    # CHAT AUTOMATION
    # ============================================================

    async def read_chat_messages(self) -> list[dict]:
        """
        Scrape incoming chat messages from OLX.
        Navigates to the messages page and extracts unread conversations.
        """
        await self.browser.navigate(OLX_CHAT_URL)
        await asyncio.sleep(3)

        # Get list of unread conversations
        conversations = await self.browser._evaluate_js("""
            (() => {
                const convs = document.querySelectorAll(
                    '[data-testid="conversation-item"], .conversation-item, .message-preview'
                );
                return Array.from(convs).map(c => ({
                    id: c.dataset.id || c.getAttribute('data-conversation-id'),
                    text: c.querySelector('.message-text, .preview-text')?.textContent,
                    isUnread: c.querySelector('.unread-badge, .unread-indicator') !== null,
                    buyerName: c.querySelector('.buyer-name, .conversation-name')?.textContent,
                }));
            })()
        """)

        conversations_data = conversations.get("result", {}).get("value", [])
        messages = []

        for conv in conversations_data:
            if not conv.get("isUnread"):
                continue

            # Click to open the conversation
            conv_selector = f"[data-conversation-id='{conv['id']}'], [data-id='{conv['id']}']"
            try:
                await self.browser.click(conv_selector)
                await asyncio.sleep(2)

                # Get the last incoming message
                last_msg = await self.browser._evaluate_js("""
                    (() => {
                        const msgs = document.querySelectorAll(
                            '[data-testid="message-item"], .message-bubble, .chat-message'
                        );
                        const lastIncoming = Array.from(msgs)
                            .filter(m => m.classList.contains('incoming') || m.dataset.direction === 'incoming')
                            .pop();
                        return lastIncoming ? {
                            text: lastIncoming.textContent,
                            conversationId: lastIncoming.dataset.conversationId,
                        } : null;
                    })()
                """)

                msg_data = last_msg.get("result", {}).get("value")
                if msg_data:
                    messages.append({
                        "olx_conversation_id": conv["id"] or msg_data.get("conversationId"),
                        "buyer_name": conv.get("buyerName"),
                        "message_text": msg_data["text"],
                    })
            except Exception as e:
                logger.error(f"Error reading conversation {conv.get('id')}: {e}")
                continue

        logger.info(f"Read {len(messages)} new chat messages from OLX")
        return messages

    async def send_chat_reply(self, conversation_id: str, message: str) -> bool:
        """Send a reply in an OLX chat conversation."""
        await self.browser.navigate(OLX_CHAT_URL)
        await asyncio.sleep(2)

        # Open the conversation
        conv_selector = f"[data-conversation-id='{conversation_id}'], [data-id='{conversation_id}']"
        await self.browser.click(conv_selector)
        await asyncio.sleep(2)

        # Type the message
        input_selector = "textarea[data-testid='chat-input'], .chat-input, .message-input"
        await self.browser.wait_for_selector(input_selector)
        await self.browser.type_text(input_selector, message)

        # Send
        await self.browser.click("button[data-testid='send-button'], .send-button, button[type='submit']")

        logger.info(f"Sent chat reply in conversation {conversation_id}")
        return True


# ============================================================
# OLX CATEGORY URL PATHS
# ============================================================
OlxCategoryUrls = {
    OlxCategory.celulares_telefonia: "celulares-e-telefonia",
    OlxCategory.informatica: "informatica",
    OlxCategory.games: "games",
    OlxCategory.audio: "audio",
    OlxCategory.tvs_e_video: "tvs-e-video",
    OlxCategory.cameras_e_drones: "cameras-e-drones",
}
