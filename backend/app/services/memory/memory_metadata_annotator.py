import json
from typing import Any

from click import prompt

from  app.services.llm import llm
from app.schemas import MemoryProfileAnnotation
from app.prompts import METADATA_ANNOTATION_SYSTEM_PROMPT, METADATA_ANNOTATION_USER_PROMPT



async def annotate_memory_profile_metadata(
    *,
    content: str,
    memory_type: str,
) -> MemoryProfileAnnotation:

   

    try:
        user_prompt = METADATA_ANNOTATION_USER_PROMPT.format(
            content=content.strip(),
            memory_type=memory_type.strip(),
        )
        response = await llm.structured(
            [{"role":"system", "content": METADATA_ANNOTATION_SYSTEM_PROMPT},{"role": "user", "content": user_prompt}],
            purpose="memory_annotation",
            response_model=MemoryProfileAnnotation
        )

        return response

    except Exception:
        return MemoryProfileAnnotation()