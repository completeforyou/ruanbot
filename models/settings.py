# models/settings.py
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, JSON
from .base import Base

class WelcomeConfig(Base):
    __tablename__ = 'welcome_config'
    id = Column(Integer, primary_key=True)
    text = Column(Text, default="🎉 Welcome to the group, {user}!")
    media_file_id = Column(String, nullable=True)
    media_type = Column(String, nullable=True)
    buttons = Column(JSON, nullable=True)

class SystemConfig(Base):
    __tablename__ = 'system_config'
    id = Column(Integer, primary_key=True)
    check_in_points = Column(Float, default=10.0)
    check_in_limit = Column(Integer, default=1)
    voucher_buy_enabled = Column(Boolean, default=True)
    voucher_cost = Column(Integer, default=500)
    invite_reward_points = Column(Float, default=20.0)
    max_daily_points = Column(Integer, default=100)
    spam_threshold = Column(Float, default=3.0)
    spam_limit = Column(Integer, default=4)
