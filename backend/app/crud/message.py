from app.models import Message
from sqlmodel import Session, select

def create_message(user_id: int, session: Session):
    conversation=Conversation(
        user_id=user_id,
        title=title
    )
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation

def get_conversation(conversation_id: int, role: str, content: str, token_count:int, session: Session):
    conversation=session.exec(selct(Conversation).where(Conversation.id==conversation_id)).first()
    return conversation