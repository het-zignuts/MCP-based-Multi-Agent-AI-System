import json
from app.schemas import MemoryComparisonResult

from app.services.llm import llm

from app.prompts import MEMORY_COMPARISON_SYSTEM_PROMPT, MEMORY_COMPARISON_USER_PROMPT



async def compare_memories(
    existing_content: str,
    new_content: str,
    memory_type: str,
) -> MemoryComparisonResult:

    try:
        user_prompt = MEMORY_COMPARISON_USER_PROMPT.format(
            existing_content=existing_content.strip(),
            new_content=new_content.strip(),
            memory_type=memory_type.strip(),
        )
        response = await llm.structured(
            [{"role": "system", "content": MEMORY_COMPARISON_SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
            purpose=f"memory_comparison:{memory_type}",
            response_model=MemoryComparisonResult
        )

        return response

    except Exception:
        return MemoryComparisonResult(
            relationship="compatible",
            confidence=0.5,
            reason="Could not parse comparator output.",
        )