# database.py
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean, Float, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os
import config

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
    id = Column(BigInteger, primary_key=True)
    username = Column(String)
    full_name = Column(String)
    
    # Economy 1: Points (Activity)
    points = Column(Float, default=0.0)
    
    # Economy 2: Vouchers (Premium/Lottery)
    vouchers = Column(Integer, default=0) 
    
    # Stats & Status
    warnings = Column(Integer, default=0)
    msg_count_total = Column(Integer, default=0)
    msg_count_daily = Column(Integer, default=0)
    last_msg_date = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(Boolean, default=False)
    is_muted = Column(Boolean, default=False)

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    
    # Type: 'lottery' (Chance based, costs Vouchers) or 'shop' (Guaranteed, costs Points)
    type = Column(String, default='lottery') 
    
    cost = Column(Float, nullable=False)   # Points (if shop) or Vouchers (if lottery)
    chance = Column(Float, default=1.0)    # Only used for lottery (0.0 - 1.0)
    
    stock = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)

class WelcomeConfig(Base):
    __tablename__ = 'welcome_config'
    id = Column(Integer, primary_key=True)
    text = Column(Text, default="🎉 Welcome to the group, {user}!")
    media_file_id = Column(String, nullable=True)
    media_type = Column(String, nullable=True)
    buttons = Column(JSON, nullable=True)

def init_db():
    Base.metadata.create_all(engine)
    
    # --- Auto-Migration: Add columns if they don't exist ---
    inspector = inspect(engine)
    with engine.connect() as conn:
        # 1. Check User table for 'vouchers'
        columns = [c['name'] for c in inspector.get_columns('users')]
        if 'vouchers' not in columns:
            print("⚙️ Migrating DB: Adding 'vouchers' to users...")
            conn.execute(text("ALTER TABLE users ADD COLUMN vouchers INTEGER DEFAULT 0"))
            
        # 2. Check Product table for 'type'
        p_columns = [c['name'] for c in inspector.get_columns('products')]
        if 'type' not in p_columns:
            print("⚙️ Migrating DB: Updating products table...")
            conn.execute(text("ALTER TABLE products ADD COLUMN type VARCHAR DEFAULT 'lottery'"))