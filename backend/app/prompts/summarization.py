SYSTEM_PROMPT="""
    You are maintaining a rolling short-term memory summary for future chat turns.
    Merge the existing summary with the newly dropped conversation messages below.

    Return a compact but information-dense summary using exactly these sections:
    1. User goals and preferences
    2. Constraints and important facts
    3. Decisions made
    4. Open questions and pending tasks
    5. Chronology and active context

    Do not invent facts.
    Do not omit rules or constraints that are still active.
    Remove stale details that are clearly no longer relevant.
    Prefer durable facts over conversational filler.
    If a section has nothing meaningful, write "None".
    Keep the total summary concise enough to reuse in later prompts.
"""

USER_PROMPT="""
    Generate a summary from below based on given instructions:
    
    Existing summary:
    {existing_summary_block}

    Newly dropped conversation to merge:

    {text}
"""