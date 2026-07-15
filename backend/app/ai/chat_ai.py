"""
AUTOMATIZA AI — Chat IA
Responds to OLX chat messages using GPT-4o with product context.

Flow:
  1. CDP scrapes incoming messages from OLX
  2. For each message, identifies the product being discussed
  3. Builds context (product details, price, recent messages)
  4. GPT-4o generates a natural, helpful response in Portuguese
  5. If price negotiation goes below minimum → flag for human
  6. Sends the reply back via CDP
"""

from __future__ import annotations

import uuid
from typing import Optional
from loguru import logger
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.models import (
    Product, AdVariation, Publication, ChatMessage,
    ChatDirection, ChatStatus, OlxAccount
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


SYSTEM_PROMPT = """Você é o assistente virtual de um vendedor de eletrônicos na OLX Brasil.
Seu nome é o assistente do AUTOMATIZA AI.

REGRAS:
1. Seja educado, rápido e direto. Responda como um vendedor real faria.
2. NUNCA invente especificações que não estão nos dados do produto.
3. Se o comprador pedir desconto abaixo do preço mínimo configurado, diga que não é possível e que o vendedor vai entrar em contato.
4. Se a pergunta for sobre algo que você não sabe, diga que vai verificar com o vendedor e responderá em breve.
5. Mantenha as respostas curtas (2-4 frases) — chat da OLX é rápido.
6. Em português do Brasil.
7. Seja amigável mas profissional.
8. Se o comprador quiser fechar negócio, diga para encontrar no chat ou pedir o telefone.
9. NUNCA dê seu telefone ou dados pessoais — apenas se o vendedor autorizou.
"""

NEGOTIATION_KEYWORDS = ["desconto", "preço", "mais barato", "negociar", "fechamos", "quanto fica", "parcela", "à vista"]


class ChatAI:
    """AI-powered chat handler for OLX messages."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_incoming_message(self, account_id: uuid.UUID, message_data: dict) -> dict:
        """
        Process an incoming OLX chat message and generate a response.

        Returns: {
            "response": str,  # the AI-generated reply
            "needs_human": bool,  # True if should escalate to human
            "conversation_id": str,
        }
        """
        conversation_id = message_data.get("olx_conversation_id")
        buyer_name = message_data.get("buyer_name", "interessado")
        incoming_text = message_data.get("message_text", "")
        olx_ad_id = message_data.get("olx_ad_id")

        # 1. Find the product being discussed
        product = await self._find_product_from_ad(account_id, olx_ad_id)
        if not product:
            # Can't identify the product — ask for clarification
            return {
                "response": f"Olá! Obrigado pelo contato. Qual produto você está interessado? Pode me dizer o título do anúncio?",
                "needs_human": False,
                "conversation_id": conversation_id,
            }

        # 2. Get recent conversation history
        history = await self._get_conversation_history(account_id, conversation_id)

        # 3. Generate AI response
        response = await self._generate_response(product, incoming_text, buyer_name, history)

        # 4. Check if needs human escalation
        needs_human = self._check_needs_human(incoming_text, product)

        # 5. Save the incoming message and AI response
        incoming_msg = ChatMessage(
            olx_account_id=account_id,
            olx_conversation_id=conversation_id,
            olx_ad_id=olx_ad_id,
            buyer_name=buyer_name,
            direction=ChatDirection.incoming,
            message_text=incoming_text,
            ai_generated=False,
            status=ChatStatus.ai_responded if not needs_human else ChatStatus.human_needed,
        )
        self.db.add(incoming_msg)

        outgoing_msg = ChatMessage(
            olx_account_id=account_id,
            olx_conversation_id=conversation_id,
            olx_ad_id=olx_ad_id,
            buyer_name=buyer_name,
            direction=ChatDirection.outgoing,
            message_text=response,
            ai_generated=True,
            status=ChatStatus.ai_responded if not needs_human else ChatStatus.human_needed,
        )
        self.db.add(outgoing_msg)
        await self.db.commit()

        logger.info(f"Chat AI: {buyer_name} → {incoming_text[:50]}... → {response[:50]}...")

        return {
            "response": response,
            "needs_human": needs_human,
            "conversation_id": conversation_id,
        }

    async def _find_product_from_ad(self, account_id: uuid.UUID, olx_ad_id: Optional[str]) -> Optional[Product]:
        """Find the product associated with this OLX ad."""
        if not olx_ad_id:
            return None

        result = await self.db.execute(
            select(Product)
            .join(Publication, Publication.product_id == Product.id)
            .where(
                Publication.olx_account_id == account_id,
                Publication.olx_ad_id == olx_ad_id,
            )
            .limit(1)
        )
        return result.scalars().first()

    async def _get_conversation_history(self, account_id: uuid.UUID, conversation_id: str) -> list[ChatMessage]:
        """Get the last 5 messages in this conversation."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.olx_account_id == account_id,
                ChatMessage.olx_conversation_id == conversation_id,
            )
            .order_by(ChatMessage.created_date.desc())
            .limit(5)
        )
        messages = result.scalars().all()
        return list(reversed(messages))  # chronological order

    async def _generate_response(
        self,
        product: Product,
        incoming_text: str,
        buyer_name: str,
        history: list[ChatMessage],
    ) -> str:
        """Generate an AI response using GPT-4o with product context."""
        # Build conversation history for the prompt
        history_text = ""
        for msg in history:
            speaker = "Comprador" if msg.direction == ChatDirection.incoming else "Vendedor (você)"
            history_text += f"{speaker}: {msg.message_text}\n"

        prompt = f"""Você é o assistente virtual de um vendedor de eletrônicos na OLX.

PRODUTO EM QUESTÃO:
- Título: {product.title}
- Marca: {product.brand or 'N/A'}
- Modelo: {product.model or 'N/A'}
- Preço: R$ {product.price:.2f}
- Preço mínimo aceitável: R$ {product.min_price or product.price:.2f}
- Condição: {product.condition}
- Especificações: {product.specs or 'N/A'}

HISTÓRICO DA CONVERSA:
{history_text if history_text else '(primeira mensagem)'}

MENSAGEM DO COMPRADOR ({buyer_name}):
{incoming_text}

Gere uma resposta curta, natural e útil. Em português do Brasil. Máximo 2-3 frases."""

        response = await client.chat.completions.create(
            model=settings.OPENAI_TEXT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()

    def _check_needs_human(self, incoming_text: str, product: Product) -> bool:
        """Check if this message needs human escalation."""
        text_lower = incoming_text.lower()

        # Price negotiation below minimum
        if any(kw in text_lower for kw in NEGOTIATION_KEYWORDS):
            # Try to extract a number from the message
            import re
            numbers = re.findall(r'[\d,.]+', incoming_text.replace('.', '').replace(',', '.'))
            for num_str in numbers:
                try:
                    offered_price = float(num_str)
                    min_price = product.min_price or (product.price * 0.9)  # default 10% margin
                    if offered_price < min_price:
                        return True  # Offer below minimum — needs human
                except ValueError:
                    continue

        # Complex questions that AI shouldn't answer
        complex_keywords = ["garantia", "nota fiscal", "troca", "parcelamento", "reembolso", "defeito"]
        if any(kw in text_lower for kw in complex_keywords):
            return True

        return False
