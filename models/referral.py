from sqlalchemy import Column, BigInteger, Integer, DateTime
from datetime import datetime
from .base import Base

class Referral(Base):
    __tablename__ = 'referrals'
    id = Column(Integer, primary_key=True)
    inviter_id = Column(BigInteger, nullable=False)
    invited_user_id = Column(BigInteger, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)