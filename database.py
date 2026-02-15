# database.py
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean, Float, Text, JSON, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import config

Base = declarative_base()
engine = create_engine(config.DATABASE_URL if config.DATABASE_URL else "sqlite:///local_test.db")
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True)
    username = Column(String)
    full_name = Column(String)
    
    # Economy
    points = Column(Float, default=0.0)
    vouchers = Column(Integer, default=0) 
    
    # Check-In Stats (NEW)
    last_check_in_date = Column(DateTime, nullable=True)
    daily_check_in_count = Column(Integer, default=0)
    
    # General Stats
    warnings = Column(Integer, default=0)
    msg_count_total = Column(Integer, default=0)
    msg_count_daily = Column(Integer, default=0)
    last_msg_date = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(Boolean, default=False)
    is_muted = Column(Boolean, default=False)

# ... (Product and WelcomeConfig remain the same) ...
class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, default='lottery') 
    cost = Column(Float, nullable=False)
    chance = Column(Float, default=1.0)
    stock = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)

class WelcomeConfig(Base):
    __tablename__ = 'welcome_config'
    id = Column(Integer, primary_key=True)
    text = Column(Text, default="🎉 Welcome to the group, {user}!")
    media_file_id = Column(String, nullable=True)
    media_type = Column(String, nullable=True)
    buttons = Column(JSON, nullable=True)

# --- NEW: System Config (For Check-in Settings) ---
class SystemConfig(Base):
    __tablename__ = 'system_config'
    id = Column(Integer, primary_key=True)
    check_in_points = Column(Float, default=10.0)
    check_in_limit = Column(Integer, default=1) # How many times per day?
    voucher_buy_enabled = Column(Boolean, default=True)

def init_db():
    Base.metadata.create_all(engine)