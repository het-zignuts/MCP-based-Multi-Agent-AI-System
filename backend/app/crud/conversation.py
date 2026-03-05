from app.models import Conversation
from sqlmodel import Session, select

def create_conversation(user_id: int, title: str= "New Conversation", session: Session):
    conversation=Conversation(
        user_id=user_id,
        title=title
    )
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation

def get_conversation(conversation_id: int, session: Session):
    conversation=session.exec(selct(Conversation).where(Conversation.id==conversation_id)).first()
    return conversation