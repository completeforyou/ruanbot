# config.py
import os

# --- Secrets ---
TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Fix for Railway PostgreSQL URL
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- Settings ---
MAX_DAILY_POINTS = 100
SPAM_THRESHOLD_SECONDS = 3.0
SPAM_MESSAGE_LIMIT = 4
ADMIN_IDS = [5569939377,729168419]  # REPLACE THIS with your actual Telegram User ID!