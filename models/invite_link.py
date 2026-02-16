from sqlalchemy import Column, String, BigInteger, DateTime
from datetime import datetime
from .base import Base

class InviteLink(Base):
    __tablename__ = 'invite_links'
    
    # The actual URL (e.g., https://t.me/...)
    link = Column(String, primary_key=True) 
    creator_id = Column(BigInteger, nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)