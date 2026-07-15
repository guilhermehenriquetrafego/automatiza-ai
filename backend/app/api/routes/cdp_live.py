import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import async_session, Publication, PublicationStatus, OlxAccount
from app.core.security import get_current_user, User

router = APIRouter()

# In-memory storage for simulated/active CDP sessions and recent activity events
# sessions key: uuid as string -> dict containing session details
# activities is a list of events (dicts)
cdp_sessions = {}
cdp_activities = []


class SimulateRequest(BaseModel):
    account_email: str
    action: str  # 'login' | 'post_ad' | 'sync_limits'


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
    """Creates a simulated CDP session for demonstration, simulating the process step by step."""
    if req.action not in ["login", "post_ad", "sync_limits"]:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'login', 'post_ad', or 'sync_limits'")

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    steps = [
        {
            "timestamp": now,
            "action": "initialize",
            "status": "success",
            "message": f"Iniciando CDP para ação: {req.action}"
        }
    ]

    # Add simulated steps depending on the action
    if req.action == "login":
        status = "success"
        current_action = "Login concluído com sucesso."
        steps.extend([
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "open_browser",
                "status": "success",
                "message": "Navegador Chromium iniciado em modo headless."
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "navigate_login",
                "status": "success",
                "message": "Navegando para a página de login da OLX."
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "fill_credentials",
                "status": "success",
                "message": f"Preenchendo e-mail: {req.account_email} e senha."
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "bypass_captcha",
                "status": "success",
                "message": "Anti-captcha executado e resolvido com sucesso."
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "detect_account_type",
                "status": "success",
                "message": "Conta identificada como 'professional'. Plano: Diversos 250"
            }
        ])
    elif req.action == "post_ad":
        status = "success"
        current_action = "Anúncio publicado com sucesso!"
        steps.extend([
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "navigate_post",
                "status": "success",
                "message": "Navegando para o formulário de anúncio da OLX."
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "fill_form",
                "status": "success",
                "message": "Preenchendo título, descrição, categoria e preço do produto."
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "upload_images",
                "status": "success",
                "message": "Enviando imagens otimizadas para a OLX."
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "submit_ad",
                "status": "success",
                "message": "Formulário enviado. Aguardando processamento da OLX."
            }
        ])
    else:  # sync_limits
        status = "success"
        current_action = "Limites sincronizados com sucesso."
        steps.extend([
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "navigate_limits",
                "status": "success",
                "message": "Acessando a área de limites de publicação da conta."
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "parse_limits",
                "status": "success",
                "message": "Sincronizando dados: 120 anúncios restantes de 250 contratados."
            }
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

    # Store in memory
    cdp_sessions[session_id] = session_data

    # Append to activity events
    for step in steps:
        cdp_activities.append({
            "timestamp": step["timestamp"],
            "session_id": session_id,
            "account_email": req.account_email,
            "action": step["action"],
            "status": step["status"],
            "message": step["message"]
        })

    return session_data


@router.get("/schedule")
async def get_schedule():
    """Returns upcoming scheduled CDP actions (from publications table where status='scheduled')."""
    async with async_session() as db:
        # We query publications where status is scheduled
        query = (
            select(Publication)
            .where(Publication.status == PublicationStatus.scheduled)
            .order_by(Publication.scheduled_time.asc())
        )
        result = await db.execute(query)
        pubs = result.scalars().all()

        schedule_list = []
        for pub in pubs:
            # Load variation and account info manually or if already joined
            # We fetch account email from db to be safe if not loaded
            account_email = "desconhecido@olx.com.br"
            account_res = await db.get(OlxAccount, pub.olx_account_id)
            if account_res:
                account_email = account_res.email

            product_title = "Produto Sem Nome"
            if pub.product:
                product_title = pub.product.title
            else:
                # Fallback check
                from app.models import Product
                prod_res = await db.get(Product, pub.product_id)
                if prod_res:
                    product_title = prod_res.title

            variation_title = ""
            if pub.variation:
                variation_title = pub.variation.title
            else:
                from app.models import AdVariation
                var_res = await db.get(AdVariation, pub.variation_id)
                if var_res:
                    variation_title = var_res.title

            schedule_list.append({
                "id": str(pub.id),
                "scheduled_time": pub.scheduled_time.isoformat() if pub.scheduled_time else None,
                "account_email": account_email,
                "product_title": product_title,
                "action_type": "publish",  # publication scheduled action is publishing
                "variation_title": variation_title
            })

        return schedule_list
