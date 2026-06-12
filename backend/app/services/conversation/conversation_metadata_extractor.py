import json
from typing import Any

from fastapi_pagination import response

from app.services.llm import llm

from app.schemas import ConversationMetadata

from app.prompts import CONVERSATION_METADATA_SYSTEM_PROMPT, CONVERSATION_METADATA_USER_PROMPT



async def extract_conversation_metadata(conversation_text: str) -> ConversationMetadata:
    if not conversation_text.strip():
        return {
            "topics": [],
            "entities": [],
            "active_goals": [],
            "sentiment": "neutral",
            "summary_hint": "",
        }

    try:
        user_prompt=CONVERSATION_METADATA_USER_PROMPT.format(conversation_text=conversation_text.strip())
        metadata = await llm.structured(
            messages=[{"role": "system", "content": CONVERSATION_METADATA_SYSTEM_PROMPT},{"role": "user", "content": user_prompt}],
            purpose="conversation_metadata_extraction",
            response_model=ConversationMetadata,
        )
        return metadata
    except Exception:
        return ConversationMetadata()

    
