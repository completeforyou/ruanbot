# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import config
from models.base import Base
from models.user import User
from models.product import Product
from models.referral import Referral
from models.settings import WelcomeConfig, SystemConfig

engine = create_engine(config.DATABASE_URL if config.DATABASE_URL else "sqlite:///local_test.db")
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)