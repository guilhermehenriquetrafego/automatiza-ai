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


async def _check_olx_error(browser) -> Optional[str]:
    """Check if OLX is showing an error message after an action."""
    try:
        # Common OLX error selectors
        error_selectors = [
            "[class*='error']",
            "[class*='Error']",
            "[role='alert']",
            "[data-testid*='error']",
            "span[class*='invalid']",
            "p[class*='invalid']",
        ]
        for sel in error_selectors:
            try:
                text = await browser.get_text(sel)
                if text and len(text.strip()) > 3 and text.strip() not in ["", "none"]:
                    return text.strip()
            except Exception:
                continue
    except Exception:
        pass
    return None


async def _type_with_retry(browser, selector: str, text: str, retries: int = 3) -> bool:
    """Type text with retry logic — handles React re-render timing issues."""
    from app.automation.cdp.stealth_browser import CDPError
    
    for attempt in range(retries):
        try:
            # Wait a bit before each attempt (except first)
            if attempt > 0:
                await asyncio.sleep(1.5)
                # Re-wait for the selector
                try:
                    await browser.wait_for_selector(selector, timeout=5.0)
                except CDPError:
                    continue
            
            if hasattr(browser, 'type_text_react'):
                await browser.type_text_react(selector, text)
            else:
                await browser.type_text(selector, text)
            return True
        except CDPError as e:
            if attempt < retries - 1:
                logger.warning(f"Type attempt {attempt+1} failed: {e}, retrying...")
                # Check for error message
                error = await _check_olx_error(browser)
                if error:
                    raise CDPError(f"OLX error: {error}")
            else:
                raise
    return False


async def run_cdp_login(account_id: str, email: str, password: str) -> dict:
    """
    Run a REAL CDP login on OLX.
    Uses the multi-step login flow discovered via Browserbase:
      1. Navigate to conta.olx.com.br
      2. Accept cookies
      3. Type email in form input (React controlled)
      4. Click Continuar (form button)
      5. Wait for password field (or error message)
      6. Type password (with retry)
      7. Click Continuar
      8. Wait for redirect to www.olx.com.br (success)
      9. Detect account type (free/professional)
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
        await _type_with_retry(browser, "form input", email, retries=2)
        add_step("email_typed", "success", "Email preenchido (React mode)")

        # Step 5: Click "Continuar" button
        add_step("click_continue", "running", "Clicando em Continuar...")
        await browser.click("form button")
        add_step("continue_clicked", "success", "Botão Continuar clicado (etapa email)")

        # Step 6: Wait for password field OR error message
        add_step("find_password_field", "running", "Aguardando campo de senha...")
        await asyncio.sleep(3)  # Give React time to transition

        # First, check for error messages (invalid email, account not found, etc.)
        error_msg = await _check_olx_error(browser)
        if error_msg:
            add_step("login_error", "error", f"Erro da OLX: {error_msg}")
            cdp_sessions[session_id]["status"] = "error"
            cdp_sessions[session_id]["current_action"] = f"Erro: {error_msg}"
            await browser.close()
            return cdp_sessions[session_id]

        # Try to find the password field with multiple selectors
        password_selector = None
        for selector in [
            "input[type='password']",
            "input#input-2",
            "form input[type='password']",
            "input#input-1",  # Same field repurposed by React
        ]:
            try:
                await browser.wait_for_selector(selector, timeout=5.0)
                password_selector = selector
                break
            except CDPError:
                continue

        if not password_selector:
            # Double-check for error messages
            error_msg = await _check_olx_error(browser)
            if error_msg:
                add_step("login_error", "error", f"Erro da OLX: {error_msg}")
            else:
                # Try getting any visible text that might indicate what happened
                try:
                    body_text = await browser.get_text("body") or ""
                    # Look for common OLX messages
                    if "informe um e-mail" in body_text.lower():
                        add_step("login_error", "error", "Email rejeitado pela OLX — formato inválido")
                    elif "não encontrado" in body_text.lower() or "não existe" in body_text.lower():
                        add_step("login_error", "error", "Email não cadastrado na OLX")
                    else:
                        add_step("login_error", "error", 
                                "Campo de senha não encontrado — email pode estar incorreto ou não cadastrado")
                except Exception:
                    add_step("login_error", "error", "Campo de senha não encontrado")
            
            cdp_sessions[session_id]["status"] = "error"
            cdp_sessions[session_id]["current_action"] = "Erro: Campo de senha não encontrado"
            await browser.close()
            return cdp_sessions[session_id]

        add_step("password_field_found", "success", f"Campo de senha encontrado ({password_selector})")

        # Wait a moment for the field to become interactive
        await asyncio.sleep(1)

        # Step 7: Type password (with retry for React re-render timing)
        add_step("type_password", "running", "Digitando senha...")
        try:
            await _type_with_retry(browser, password_selector, password, retries=3)
            add_step("password_typed", "success", "Senha preenchida")
        except Exception as e:
            error_str = str(e)
            if "OLX error:" in error_str:
                add_step("login_error", "error", error_str)
            else:
                add_step("type_password_error", "error", f"Erro ao digitar senha: {error_str}")
            cdp_sessions[session_id]["status"] = "error"
            cdp_sessions[session_id]["current_action"] = f"Erro: {error_str}"
            await browser.close()
            return cdp_sessions[session_id]

        # Step 8: Click "Continuar" to submit
        add_step("submit_login", "running", "Enviando formulário de login...")
        await browser.click("form button")

        # Step 9: Wait for redirect to www.olx.com.br (success indicator)
        add_step("wait_redirect", "running", "Aguardando redirecionamento...")
        login_success = False
        is_professional = False

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
                try:
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
                except Exception as e:
                    add_step("db_update_warning", "running", f"Banco: {e}")

            else:
                # Check for error after login attempt
                error_msg = await _check_olx_error(browser)
                if error_msg:
                    add_step("login_failed", "error", f"Login falhou: {error_msg}")
                else:
                    add_step("login_failed", "error", "Login falhou — sem redirecionamento após 15s (credenciais incorretas ou captcha)")
                cdp_sessions[session_id]["status"] = "error"
                cdp_sessions[session_id]["current_action"] = "Erro: Login falhou"

        except Exception as e:
            add_step("login_error", "error", f"Erro durante verificação: {e}")
            cdp_sessions[session_id]["status"] = "error"

    except Exception as e:
        add_step("error", "error", f"Erro: {e}")
        cdp_sessions[session_id]["status"] = "error"
        cdp_sessions[session_id]["current_action"] = f"Erro: {e}"
        logger.exception(f"CDP login error for {email}")

    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    return cdp_sessions[session_id]


async def run_cdp_sync_limits(account_id: str, email: str) -> dict:
    """
    Sync OLX ad limits by navigating to the my ads page and extracting limit info.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    cdp_sessions[session_id] = {
        "id": session_id,
        "account_email": email,
        "status": "connecting",
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

        add_step("launch_browser", "running", "Iniciando Chromium...")
        browser = StealthBrowser(headless=True)
        await browser.launch()
        add_step("browser_ready", "success", "Navegador pronto")

        # Navigate to my ads page
        add_step("navigate", "running", f"Navegando para {OLX_MY_ADS_URL}")
        await browser.navigate(OLX_MY_ADS_URL)
        await asyncio.sleep(3)

        # Check if we're redirected to login (not authenticated)
        if hasattr(browser, 'get_current_url'):
            current_url = await browser.get_current_url()
            if "conta.olx.com.br" in current_url:
                add_step("auth_required", "error", "Não autenticado — redirecionado para login")
                cdp_sessions[session_id]["status"] = "error"
                cdp_sessions[session_id]["current_action"] = "Erro: Não autenticado"
                await browser.close()
                return cdp_sessions[session_id]

        add_step("page_loaded", "success", "Página de anúncios carregada")

        # Extract limits from the page
        add_step("extract_limits", "running", "Extraindo limites da página...")
        try:
            page_text = await browser.get_text("body") or ""
            page_lower = page_text.lower()

            # Look for limit patterns
            # Free accounts: "X de Y inserções gratuitas restantes"
            # Professional: "X de Y inserções profissionais restantes"
            
            limits = {}
            
            # Try to find "X de Y" patterns
            pattern = r'(\d+)\s*(?:de|/)\s*(\d+)'
            matches = re.findall(pattern, page_text)
            
            if matches:
                for used, total in matches[:3]:
                    key = f"limite_{len(limits)+1}"
                    limits[key] = {"used": int(used), "total": int(total)}
                
                add_step("limits_extracted", "success", 
                         f"Limites encontrados: {limits}")
            else:
                add_step("limits_extracted", "running", "Nenhum padrão de limite encontrado na página")

            # Detect account type
            is_professional = any(kw in page_lower for kw in [
                "profissional", "plano profissional", "assinatura"
            ])
            account_type = "PROFISSIONAL" if is_professional else "GRATUITA"
            add_step("account_type", "success", f"Tipo: {account_type}")

        except Exception as e:
            add_step("extract_error", "error", f"Erro ao extrair: {e}")

        cdp_sessions[session_id]["status"] = "success"

    except Exception as e:
        add_step("error", "error", f"Erro: {e}")
        cdp_sessions[session_id]["status"] = "error"

    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    return cdp_sessions[session_id]
