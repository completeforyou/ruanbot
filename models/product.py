from sqlalchemy import Column, Integer, String, Float, Boolean
from .base import Base

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, default='lottery') 
    cost = Column(Float, nullable=False)
    chance = Column(Float, default=1.0)
    stock = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)