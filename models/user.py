from sqlalchemy import Column, BigInteger, String, Float, Integer, DateTime, Boolean
from datetime import datetime
from .base import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True)
    username = Column(String)
    full_name = Column(String)
    
    # Economy
    points = Column(Float, default=0.0)
    vouchers = Column(Integer, default=0) 
    
    # Check-In Stats
    last_check_in_date = Column(DateTime, nullable=True)
    daily_check_in_count = Column(Integer, default=0)
    
    # General Stats
    warnings = Column(Integer, default=0)
    msg_count_total = Column(Integer, default=0)
    msg_count_daily = Column(Integer, default=0)
    last_msg_date = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(Boolean, default=False)
    is_muted = Column(Boolean, default=False)