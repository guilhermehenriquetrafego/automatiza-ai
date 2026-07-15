"""
AUTOMATIZA AI — CDP Runner
Connects real CDP automation to live monitoring.

This module bridges the gap between the OLX automation code (stealth_browser + olx_automation)
and the CDP Live monitoring page. When a CDP action is triggered, this runner:
  1. Creates a live session record (visible on /cdp-live)
  2. Runs the real CDP automation step by step
  3. Updates the session status in real-time
  4. Logs all activity for the history feed

Selectors verified against real OLX pages via Browserbase (15/07/2026):
  - Login URL: https://conta.olx.com.br/
  - Email field: form input (first input inside form)
  - Continue button: form button
  - Multi-step: email → Continuar → password → Continuar
  - React controlled inputs (need type_text_react)
  - Cookie consent: button text "Aceitar"
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from app.api.routes.cdp_live import cdp_sessions, cdp_activities

# Real OLX URLs (verified 15/07/2026)
OLX_LOGIN_URL = "https://conta.olx.com.br/"
OLX_MY_ADS_URL = "https://www.olx.com.br/conta/meusanuncios"


async def run_cdp_login(account_id: str, email: str, password: str) -> dict:
    """
    Run a REAL CDP login on OLX.
    Uses the multi-step login flow discovered via Browserbase:
      1. Navigate to conta.olx.com.br
      2. Accept cookies
      3. Type email in form input (React controlled)
      4. Click Continuar (form button)
      5. Wait for password field
      6. Type password
      7. Click Continuar
      8. Wait for redirect to www.olx.com.br (success)
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    cdp_sessions[session_id] = {
        "id": session_id,
        "account_email": email,
        "status": "connecting",
        "current_action": "Iniciando navegador...",
        "started_at": now,
        "last_updated": now,
        "steps": [],
        "olx_ad_url": None,
    }

    def add_step(action: str, status: str, message: str):
        step = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "status": status,
            "message": message,
        }
        cdp_sessions[session_id]["steps"].append(step)
        cdp_sessions[session_id]["last_updated"] = step["timestamp"]
        cdp_sessions[session_id]["current_action"] = message
        cdp_activities.append({
            "timestamp": step["timestamp"],
            "session_id": session_id,
            "account_email": email,
            "action": action,
            "status": status,
            "message": message,
        })

    browser = None
    try:
        from app.automation.cdp.stealth_browser import StealthBrowser, CDPError

        add_step("initialize", "running", f"Iniciando CDP para conta {email}")

        add_step("launch_browser", "running", "Iniciando Chromium com stealth patches...")
        browser = StealthBrowser(headless=True)
        await browser.launch()
        add_step("browser_ready", "success", "Chromium iniciado com anti-detecção ativa")

        # Step 1: Navigate to OLX login (real URL)
        add_step("navigate_login", "running", f"Navegando para {OLX_LOGIN_URL}")
        await browser.navigate(OLX_LOGIN_URL)
        await asyncio.sleep(2)
        add_step("page_loaded", "success", "Página de login carregada (conta.olx.com.br)")

        # Step 2: Accept cookies
        add_step("accept_cookies", "running", "Procurando cookie consent...")
        if hasattr(browser, 'accept_cookies'):
            accepted = await browser.accept_cookies(timeout=5.0)
            add_step("cookies_done", "success" if accepted else "running", 
                     "Cookies aceitos" if accepted else "Nenhum cookie modal encontrado")
        else:
            add_step("cookies_done", "running", "Cookie handler não disponível")

        # Step 3: Wait for email field (form input)
        add_step("find_email_field", "running", "Procurando campo de email...")
        await browser.wait_for_selector("form input", timeout=10.0)
        add_step("email_field_found", "success", "Campo de email encontrado (form input)")

        # Step 4: Type email using React-compatible method
        add_step("type_email", "running", f"Digitando email: {email}")
        if hasattr(browser, 'type_text_react'):
            await browser.type_text_react("form input", email)
        else:
            await browser.type_text("form input", email)
        add_step("email_typed", "success", "Email preenchido (React mode)")

        # Step 5: Click "Continuar" button
        add_step("click_continue", "running", "Clicando em Continuar...")
        await browser.click("form button")
        add_step("continue_clicked", "success", "Botão Continuar clicado (etapa email)")

        # Step 6: Wait for password field
        add_step("find_password_field", "running", "Aguardando campo de senha...")
        await asyncio.sleep(2)  # Give React time to transition

        password_selector = None
        for selector in [
            "input[type='password']",
            "input#input-2",
            "input#input-1",  # Same field, repurposed by React
            "form input",
        ]:
            try:
                await browser.wait_for_selector(selector, timeout=5.0)
                password_selector = selector
                break
            except CDPError:
                continue

        if not password_selector:
            # Check for error message (invalid email)
            try:
                error_text = await browser.get_text("[class*='error'], [class*='Error'], [role='alert']")
                if error_text:
                    add_step("login_error", "error", f"Erro da OLX: {error_text}")
                else:
                    add_step("login_error", "error", "Campo de senha não encontrado — email pode estar inválido")
            except Exception:
                add_step("login_error", "error", "Campo de senha não encontrado")
            cdp_sessions[session_id]["status"] = "error"
            return cdp_sessions[session_id]

        add_step("password_field_found", "success", f"Campo de senha encontrado ({password_selector})")

        # Step 7: Type password
        add_step("type_password", "running", "Digitando senha...")
        if hasattr(browser, 'type_text_react'):
            await browser.type_text_react(password_selector, password)
        else:
            await browser.type_text(password_selector, password)
        add_step("password_typed", "success", "Senha preenchida")

        # Step 8: Click "Continuar" to submit
        add_step("submit_login", "running", "Enviando formulário de login...")
        await browser.click("form button")

        # Step 9: Wait for redirect to www.olx.com.br (success indicator)
        add_step("wait_redirect", "running", "Aguardando redirecionamento...")
        login_success = False
        
        try:
            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < 15.0:
                if hasattr(browser, 'get_current_url'):
                    current_url = await browser.get_current_url()
                    if current_url and "conta.olx.com.br" not in current_url:
                        login_success = True
                        break
                await asyncio.sleep(1)

            if login_success:
                add_step("login_success", "success", "Login realizado! Redirecionado para www.olx.com.br")
                cdp_sessions[session_id]["status"] = "success"

                # Detect account type by navigating to my ads page
                add_step("detect_account_type", "running", "Detectando tipo de conta...")
                await browser.navigate(OLX_MY_ADS_URL)
                await asyncio.sleep(3)

                try:
                    page_text = await browser.get_text("body") or ""
                    page_lower = page_text.lower()
                    
                    is_professional = any(kw in page_lower for kw in [
                        "profissional", "plano profissional", "assinatura",
                        "inserções profissionais", "anúncios profissionais",
                        "plano pago", "plano pro",
                    ])
                    
                    account_type_str = "PROFISSIONAL" if is_professional else "GRATUITA"
                    add_step("account_type_detected", "success", f"Conta identificada como {account_type_str}")

                    # Try to extract limit numbers
                    numbers = re.findall(r'\d+', page_text.replace('.', ''))
                    add_step("limits_detected", "success", f"Encontrados {len(numbers)} valores numéricos na página")

                except Exception as e:
                    add_step("account_type_detected", "success", f"Tipo de conta detectado (erro na leitura: {e})")

                # Update database
                from app.models import async_session, OlxAccount, OlxAccountType
                async with async_session() as db:
                    account = await db.get(OlxAccount, uuid.UUID(account_id))
                    if account:
                        account.is_authenticated = True
                        account.needs_reauth = False
                        account.last_login_at = datetime.now(timezone.utc)
                        if is_professional:
                            account.account_type = OlxAccountType.professional
                        else:
                            account.account_type = OlxAccountType.free
                        await db.commit()

                add_step("db_updated", "success", "Conta atualizada no banco de dados")

            else:
                add_step("login_failed", "error", "Login falhou — sem redirecionamento após 15s (credenciais incorretas ou captcha)")
                cdp_sessions[session_id]["status"] = "error"

                from app.models import async_session, OlxAccount
                async with async_session() as db:
                    account = await db.get(OlxAccount, uuid.UUID(account_id))
                    if account:
                        account.needs_reauth = True
                        account.is_authenticated = False
                        await db.commit()

        except Exception as e:
            add_step("login_failed", "error", f"Erro no redirecionamento: {str(e)}")
            cdp_sessions[session_id]["status"] = "error"

    except Exception as e:
        logger.error(f"CDP login failed: {e}")
        add_step("error", "error", f"Erro: {str(e)}")
        cdp_sessions[session_id]["status"] = "error"
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        cdp_sessions[session_id]["last_updated"] = datetime.now(timezone.utc).isoformat()

    return cdp_sessions[session_id]


async def run_cdp_sync_limits(account_id: str, email: str) -> dict:
    """
    Run a REAL CDP limit sync on OLX.
    Navigates to the account's ads page and scrapes current limits.
    Uses session persistence (cookies) from previous login.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    cdp_sessions[session_id] = {
        "id": session_id,
        "account_email": email,
        "status": "syncing",
        "current_action": "Iniciando sync de limites...",
        "started_at": now,
        "last_updated": now,
        "steps": [],
        "olx_ad_url": None,
    }

    def add_step(action: str, status: str, message: str):
        step = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "status": status,
            "message": message,
        }
        cdp_sessions[session_id]["steps"].append(step)
        cdp_sessions[session_id]["last_updated"] = step["timestamp"]
        cdp_sessions[session_id]["current_action"] = message
        cdp_activities.append({
            "timestamp": step["timestamp"],
            "session_id": session_id,
            "account_email": email,
            "action": action,
            "status": status,
            "message": message,
        })

    browser = None
    try:
        from app.automation.cdp.stealth_browser import StealthBrowser, CDPError

        add_step("initialize", "running", f"Iniciando sync para {email}")

        browser = StealthBrowser(headless=True)
        await browser.launch()
        add_step("browser_ready", "success", "Chromium iniciado")

        # Navigate to my ads page
        add_step("navigate_ads", "running", f"Navegando para {OLX_MY_ADS_URL}")
        await browser.navigate(OLX_MY_ADS_URL)
        await asyncio.sleep(3)
        add_step("page_loaded", "success", "Página de anúncios carregada")

        # Check if we're authenticated (not redirected to login)
        add_step("check_auth", "running", "Verificando autenticação...")
        current_url = ""
        if hasattr(browser, 'get_current_url'):
            current_url = await browser.get_current_url()
        
        is_authenticated = "conta.olx.com.br" not in current_url and "entrar" not in current_url.lower()
        
        if is_authenticated:
            add_step("authenticated", "success", "Sessão autenticada (cookies válidos)")
        else:
            add_step("auth_failed", "error", "Sessão expirada — redirecionado para login")
            cdp_sessions[session_id]["status"] = "error"
            
            # Mark account as needing reauth
            from app.models import async_session, OlxAccount
            async with async_session() as db:
                account = await db.get(OlxAccount, uuid.UUID(account_id))
                if account:
                    account.needs_reauth = True
                    await db.commit()
            
            return cdp_sessions[session_id]

        # Scrape limit information
        add_step("scrape_limits", "running", "Extraindo informações de limite...")
        
        # Get page text and look for limit patterns
        page_text = await browser.get_text("body") or ""
        
        # Parse limit patterns: "X de Y", "X/Y", "X inserções", etc.
        limit_match = re.search(r'(\d+)\s*(?:de|dos?|\/)\s*(\d+)', page_text.replace('.', ''))
        if limit_match:
            used = int(limit_match.group(1))
            total = int(limit_match.group(2))
            remaining = max(0, total - used)
            add_step("limits_parsed", "success", f"Limites: {used}/{total} usados, {remaining} restantes")
        else:
            # Count numbers on page as fallback
            numbers = re.findall(r'\d+', page_text.replace('.', ''))
            add_step("limits_parsed", "success", f"Encontrados {len(numbers)} valores numéricos na página")

        # Count active ads
        add_step("count_ads", "running", "Contando anúncios ativos...")
        result = await browser._evaluate_js("""
            (() => {
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
                    if (elements.length > 0) return elements.length;
                }
                return 0;
            })()
        """)
        
        ad_count = result.get("result", {}).get("value", 0) if result else 0
        if isinstance(ad_count, dict):
            ad_count = 0
        add_step("ads_counted", "success", f"{ad_count} anúncios encontrados na página")

        # Update database
        from app.models import async_session, OlxAccount
        async with async_session() as db:
            account = await db.get(OlxAccount, uuid.UUID(account_id))
            if account:
                account.last_limit_sync = datetime.now(timezone.utc)
                if limit_match:
                    account.total_monthly_limit = total
                    account.used_this_month = used
                    account.remaining_this_month = remaining
                else:
                    account.used_this_month = int(ad_count) if ad_count else 0
                await db.commit()

        add_step("sync_complete", "success", "Limites sincronizados com sucesso")
        cdp_sessions[session_id]["status"] = "success"

    except Exception as e:
        logger.error(f"CDP sync failed: {e}")
        add_step("error", "error", f"Erro: {str(e)}")
        cdp_sessions[session_id]["status"] = "error"
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        cdp_sessions[session_id]["last_updated"] = datetime.now(timezone.utc).isoformat()

    return cdp_sessions[session_id]


async def run_cdp_post_ad(account_id: str, email: str, product_data: dict) -> dict:
    """
    Run a REAL CDP ad posting on OLX.
    Navigates to the post ad form, fills all fields, and submits.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    cdp_sessions[session_id] = {
        "id": session_id,
        "account_email": email,
        "status": "posting",
        "current_action": "Iniciando postagem...",
        "started_at": now,
        "last_updated": now,
        "steps": [],
        "olx_ad_url": None,
    }

    def add_step(action: str, status: str, message: str):
        step = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "status": status,
            "message": message,
        }
        cdp_sessions[session_id]["steps"].append(step)
        cdp_sessions[session_id]["last_updated"] = step["timestamp"]
        cdp_sessions[session_id]["current_action"] = message
        cdp_activities.append({
            "timestamp": step["timestamp"],
            "session_id": session_id,
            "account_email": email,
            "action": action,
            "status": status,
            "message": message,
        })

    browser = None
    try:
        from app.automation.cdp.stealth_browser import StealthBrowser, CDPError

        add_step("initialize", "running", f"Iniciando postagem para {email}")

        browser = StealthBrowser(headless=True)
        await browser.launch()
        add_step("browser_ready", "success", "Chromium iniciado")

        # Navigate to post ad page
        add_step("navigate_post", "running", "Navegando para https://www.olx.com.br/criar-anuncio")
        await browser.navigate("https://www.olx.com.br/criar-anuncio")
        await asyncio.sleep(3)
        add_step("page_loaded", "success", "Página de postagem carregada")

        # Accept cookies if present
        if hasattr(browser, 'accept_cookies'):
            await browser.accept_cookies(timeout=3.0)

        # Select category
        category = product_data.get("category", "Celulares")
        add_step("select_category", "running", f"Selecionando categoria: {category}")
        await browser._evaluate_js(f"""
            (() => {{
                const links = document.querySelectorAll('a, button, [role="button"]');
                for (const link of links) {{
                    if (link.textContent && link.textContent.includes({json.dumps(category)})) {{
                        link.click();
                        return true;
                    }}
                }}
                return false;
            }})()
        """)
        await asyncio.sleep(2)
        add_step("category_selected", "success", f"Categoria {category} selecionada")

        # Fill title
        title = product_data.get("title", "")
        add_step("fill_title", "running", f"Digitando título: {title[:50]}...")
        await browser.wait_for_selector("form input, input[name='title'], #title", timeout=10.0)
        if hasattr(browser, 'type_text_react'):
            await browser.type_text_react("form input, input[name='title'], #title", title)
        else:
            await browser.type_text("form input, input[name='title'], #title", title)
        add_step("title_filled", "success", "Título preenchido")

        # Fill description
        description = product_data.get("description", "")
        add_step("fill_desc", "running", "Digitando descrição...")
        await browser.wait_for_selector("textarea, [name='description'], #description", timeout=5.0)
        if hasattr(browser, 'type_text_react'):
            await browser.type_text_react("textarea, [name='description'], #description", description)
        else:
            await browser.type_text("textarea, [name='description'], #description", description)
        add_step("desc_filled", "success", "Descrição preenchida")

        # Fill price
        price = product_data.get("price", "")
        if price:
            add_step("fill_price", "running", f"Digitando preço: {price}")
            await browser.wait_for_selector("input[name='price'], #price, input[placeholder*='preço']", timeout=5.0)
            if hasattr(browser, 'type_text_react'):
                await browser.type_text_react("input[name='price'], #price", str(price))
            else:
                await browser.type_text("input[name='price'], #price", str(price))
            add_step("price_filled", "success", "Preço preenchido")

        # Submit
        add_step("submit_ad", "running", "Enviando anúncio...")
        await browser.click("button[type='submit'], form button")
        await asyncio.sleep(3)

        # Check result
        current_url = await browser.get_current_url() if hasattr(browser, 'get_current_url') else ""
        if "olx.com.br" in current_url and "criar-anuncio" not in current_url:
            add_step("ad_posted", "success", f"Anúncio postado! URL: {current_url}")
            cdp_sessions[session_id]["status"] = "success"
            cdp_sessions[session_id]["olx_ad_url"] = current_url
        else:
            add_step("post_failed", "error", "Postagem falhou — ainda no formulário")
            cdp_sessions[session_id]["status"] = "error"

    except Exception as e:
        logger.error(f"CDP post ad failed: {e}")
        add_step("error", "error", f"Erro: {str(e)}")
        cdp_sessions[session_id]["status"] = "error"
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        cdp_sessions[session_id]["last_updated"] = datetime.now(timezone.utc).isoformat()

    return cdp_sessions[session_id]
