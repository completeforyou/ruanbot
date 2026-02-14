# database.py
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean, Float, Text, JSON, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os
import config

# --- Secrets ---
TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Fix for Railway PostgreSQL URL
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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
    
    # Stats
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

def init_db():
    Base.metadata.create_all(engine)
    
    # --- Auto-Migration ---
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