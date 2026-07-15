"""Chat routes — view messages, override AI responses, mark as resolved."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import Optional

from app.models import async_session, User, ChatMessage, OlxAccount, ChatStatus, ChatDirection
from app.core.security import get_current_user

router = APIRouter()


class ChatMessageResponse(BaseModel):
    id: str
    direction: str
    message_text: str
    buyer_name: str | None
    ai_generated: bool
    status: str
    created_date: str


class ManualReplyRequest(BaseModel):
    conversation_id: str
    account_id: str
    message: str


@router.get("/messages")
async def list_messages(status: str | None = None, user: User = Depends(get_current_user)):
    async with async_session() as db:
        query = (
            select(ChatMessage, OlxAccount)
            .join(OlxAccount, ChatMessage.olx_account_id == OlxAccount.id)
            .where(OlxAccount.user_id == user.id)
        )
        if status:
            query = query.where(ChatMessage.status == ChatStatus(status))
        query = query.order_by(ChatMessage.created_date.desc()).limit(100)

        result = await db.execute(query)
        rows = result.all()
        return [ChatMessageResponse(
            id=str(msg.id),
            direction=msg.direction.value,
            message_text=msg.message_text,
            buyer_name=msg.buyer_name,
            ai_generated=msg.ai_generated,
            status=msg.status.value,
            created_date=msg.created_date.isoformat(),
        ).model_dump() for msg, _ in rows]


@router.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str, user: User = Depends(get_current_user)):
    """Get all messages in a conversation."""
    async with async_session() as db:
        result = await db.execute(
            select(ChatMessage, OlxAccount)
            .join(OlxAccount, ChatMessage.olx_account_id == OlxAccount.id)
            .where(
                and_(
                    OlxAccount.user_id == user.id,
                    ChatMessage.olx_conversation_id == conversation_id,
                )
            )
            .order_by(ChatMessage.created_date)
        )
        rows = result.all()
        return [ChatMessageResponse(
            id=str(msg.id),
            direction=msg.direction.value,
            message_text=msg.message_text,
            buyer_name=msg.buyer_name,
            ai_generated=msg.ai_generated,
            status=msg.status.value,
            created_date=msg.created_date.isoformat(),
        ).model_dump() for msg, _ in rows]


@router.post("/reply")
async def manual_reply(req: ManualReplyRequest, user: User = Depends(get_current_user)):
    """Send a manual reply (overrides AI). Sends via CDP to OLX chat."""
    async with async_session() as db:
        account = await db.get(OlxAccount, uuid.UUID(req.account_id))
        if not account or account.user_id != user.id:
            raise HTTPException(404, "Account not found")

        # Save the message
        msg = ChatMessage(
            olx_account_id=uuid.UUID(req.account_id),
            olx_conversation_id=req.conversation_id,
            direction=ChatDirection.outgoing,
            message_text=req.message,
            ai_generated=False,
            status=ChatStatus.resolved,
        )
        db.add(msg)
        await db.commit()

    # Send via CDP in background
    async def _send():
        from app.automation.cdp.olx_automation import OlxAutomation
        async with async_session() as db:
            account = await db.get(OlxAccount, uuid.UUID(req.account_id))
            async with OlxAutomation(account, db) as olx:
                await olx.send_chat_reply(req.conversation_id, req.message)

    import asyncio
    asyncio.create_task(_send())
    return {"status": "sent"}


@router.put("/{message_id}/resolve")
async def resolve_message(message_id: str, user: User = Depends(get_current_user)):
    async with async_session() as db:
        msg = await db.get(ChatMessage, uuid.UUID(message_id))
        if not msg:
            raise HTTPException(404, "Message not found")
        msg.status = ChatStatus.resolved
        await db.commit()
    return {"status": "resolved"}
