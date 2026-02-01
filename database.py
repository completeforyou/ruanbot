# database.py
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

# Get DATABASE_URL from Railway environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Fix for Railway's postgres:// vs postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

Base = declarative_base()
engine = create_engine(DATABASE_URL if DATABASE_URL else "sqlite:///local_test.db")
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True) # Telegram User ID
    username = Column(String)
    full_name = Column(String)
    points = Column(Float, default=0.0)       # Feature 4, 17
    warnings = Column(Integer, default=0)     # Feature 1
    
    # Activity Stats (Feature 9, 11)
    msg_count_total = Column(Integer, default=0)
    msg_count_daily = Column(Integer, default=0)
    last_msg_date = Column(DateTime, default=datetime.utcnow)
    
    # Feature 6: Check-in
    last_checkin = Column(DateTime, nullable=True)
    checkin_count_today = Column(Integer, default=0)
    
    # Feature 7: Verified User
    is_verified = Column(Boolean, default=False)
    
    # Feature 5: Scratch-off Pity System
    scratch_pity_rate = Column(Float, default=0.0) # Increases on fail

    # Feature 2: Join verification status
    is_muted = Column(Boolean, default=False)

def init_db():
    Base.metadata.create_all(engine)