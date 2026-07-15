"""
AUTOMATIZA AI — CDP Live Monitoring Routes
Real-time monitoring of CDP automation sessions.
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from loguru import logger

from app.models import async_session, Publication, PublicationStatus, OlxAccount
from app.core.security import get_current_user, User

router = APIRouter()

# In-memory storage for CDP sessions and activity events
cdp_sessions: dict[str, dict] = {}
cdp_activities: list[dict] = []


class SimulateRequest(BaseModel):
    account_email: str
    action: str  # 'login' | 'post_ad' | 'sync_limits'


class TriggerRequest(BaseModel):
    """Trigger a REAL CDP action (not simulation)."""
    account_id: str
    action: str  # 'login' | 'sync_limits' | 'post_ad'
    password: str | None = None  # Required for login
    product_id: str | None = None  # Required for post_ad
    variation_id: str | None = None  # Required for post_ad


@router.get("/sessions")
async def get_sessions():
    """Returns a list of active/recent CDP sessions."""
    return list(cdp_sessions.values())


@router.get("/sessions/{id}")
async def get_session(id: str):
    """Returns details of a specific session."""
    if id not in cdp_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return cdp_sessions[id]


@router.get("/activity")
async def get_activity():
    """Returns recent CDP activity (last 50 events across all sessions)."""
    return cdp_activities[-50:][::-1]


@router.post("/simulate")
async def simulate_session(req: SimulateRequest):
    """Creates a simulated CDP session for demonstration."""
    if req.action not in ["login", "post_ad", "sync_limits"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    steps = [{
        "timestamp": now,
        "action": "initialize",
        "status": "success",
        "message": f"[SIMULAÇÃO] Iniciando CDP para ação: {req.action}"
    }]

    if req.action == "login":
        status = "success"
        current_action = "[SIMULAÇÃO] Login concluído com sucesso."
        steps.extend([
            {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "open_browser", "status": "success", "message": "[SIMULAÇÃO] Navegador Chromium iniciado em modo headless."},
            {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "navigate_login", "status": "success", "message": "[SIMULAÇÃO] Navegando para a página de login da OLX."},
            {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "fill_credentials", "status": "success", "message": f"[SIMULAÇÃO] Preenchendo e-mail: {req.account_email} e senha."},
            {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "bypass_captcha", "status": "success", "message": "[SIMULAÇÃO] Anti-captcha executado e resolvido com sucesso."},
            {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "detect_account_type", "status": "success", "message": "[SIMULAÇÃO] Conta identificada como 'professional'. Plano: Diversos 250"}
        ])
    elif req.action == "post_ad":
        status = "success"
        current_action = "[SIMULAÇÃO] Anúncio publicado com sucesso!"
        steps.extend([
            {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "navigate_post", "status": "success", "message": "[SIMULAÇÃO] Navegando para o formulário de anúncio da OLX."},
            {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "fill_form", "status": "success", "message": "[SIMULAÇÃO] Preenchendo título, descrição, categoria e preço."},
            {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "upload_images", "status": "success", "message": "[SIMULAÇÃO] Enviando imagens otimizadas para a OLX."},
            {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "submit_ad", "status": "success", "message": "[SIMULAÇÃO] Formulário enviado. Aguardando processamento da OLX."}
        ])
    else:
        status = "success"
        current_action = "[SIMULAÇÃO] Limites sincronizados com sucesso."
        steps.extend([
            {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "navigate_limits", "status": "success", "message": "[SIMULAÇÃO] Acessando a área de limites de publicação."},
            {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "parse_limits", "status": "success", "message": "[SIMULAÇÃO] Sincronizando dados: 120 anúncios restantes de 250."}
        ])

    session_data = {
        "id": session_id,
        "account_email": req.account_email,
        "status": status,
        "current_action": current_action,
        "started_at": now,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
        "olx_ad_url": "https://www.olx.com.br/detalhe-anuncio-simulado-123456" if req.action == "post_ad" else None
    }

    cdp_sessions[session_id] = session_data
    for step in steps:
        cdp_activities.append({
            "timestamp": step["timestamp"], "session_id": session_id,
            "account_email": req.account_email, "action": step["action"],
            "status": step["status"], "message": step["message"]
        })

    return session_data


@router.post("/trigger")
async def trigger_cdp_action(req: TriggerRequest, user: User = Depends(get_current_user)):
    """
    Trigger a REAL CDP action (not simulation).
    Launches actual Chromium, connects to OLX, performs the action.
    Returns the session ID immediately — monitor via /sessions/{id} or /activity.
    """
    import asyncio
    from app.automation.cdp_runner import run_cdp_login, run_cdp_sync_limits

    # Verify account belongs to user
    async with async_session() as db:
        account = await db.get(OlxAccount, uuid.UUID(req.account_id))
        if not account or account.user_id != user.id:
            raise HTTPException(404, "Account not found")
        email = account.email

    if req.action == "login":
        if not req.password:
            raise HTTPException(400, "Password required for login action")
        # Run in background — don't block the response
        asyncio.create_task(run_cdp_login(req.account_id, email, req.password))
        return {"status": "started", "message": f"CDP login iniciado para {email}", "monitor": f"/api/v1/cdp-live/sessions"}

    elif req.action == "sync_limits":
        asyncio.create_task(run_cdp_sync_limits(req.account_id, email))
        return {"status": "started", "message": f"CDP sync de limites iniciado para {email}", "monitor": f"/api/v1/cdp-live/sessions"}

    elif req.action == "post_ad":
        # TODO: Implement post_ad trigger with product/variation data
        raise HTTPException(501, "post_ad trigger ainda não implementado — use /simulate para demo")

    else:
        raise HTTPException(400, f"Unknown action: {req.action}")


@router.get("/schedule")
async def get_schedule():
    """Returns upcoming scheduled CDP actions (from publications table where status='scheduled')."""
    async with async_session() as db:
        query = (
            select(Publication)
            .where(Publication.status == PublicationStatus.scheduled)
            .order_by(Publication.scheduled_time.asc())
        )
        result = await db.execute(query)
        pubs = result.scalars().all()

        schedule_list = []
        for pub in pubs:
            account_email = "desconhecido@olx.com.br"
            account_res = await db.get(OlxAccount, pub.olx_account_id)
            if account_res:
                account_email = account_res.email

            product_title = "Produto"
            from app.models import Product
            prod_res = await db.get(Product, pub.product_id)
            if prod_res:
                product_title = prod_res.title

            variation_title = ""
            from app.models import AdVariation
            var_res = await db.get(AdVariation, pub.variation_id)
            if var_res:
                variation_title = var_res.title

            schedule_list.append({
                "id": str(pub.id),
                "scheduled_time": pub.scheduled_time.isoformat() if pub.scheduled_time else None,
                "account_email": account_email,
                "product_title": product_title,
                "action_type": "publish",
                "variation_title": variation_title
            })

        return schedule_list
