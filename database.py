# database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import config
from models.base import Base

# Import all models so they are registered
from models.user import User
from models.product import Product
from models.referral import Referral
from models.invite_link import InviteLink
from models.settings import WelcomeConfig, SystemConfig

# Create the Async Engine
engine = create_async_engine(config.DATABASE_URL, echo=False)

# Create the Async Session Maker
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

async def init_db():
    """Asynchronously creates all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)