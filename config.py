# config.py
import os

# --- Secrets ---
TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Fix for Railway PostgreSQL URL
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- Admin Configuration ---
# Railway Variable Format: 123456789,987654321
# If variable is missing, it defaults to an empty list []
admin_env = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x) for x in admin_env.split(",")] if admin_env else []

# --- Tuning / Gameplay Settings ---
# We use defaults (second argument) so the bot still works if you forget to set them in Railway
MAX_DAILY_POINTS = int(os.getenv("MAX_DAILY_POINTS", "100"))
SHOP_BANNER_URL = os.getenv("SHOP_BANNER_URL")

# Anti-Spam
SPAM_THRESHOLD_SECONDS = float(os.getenv("SPAM_THRESHOLD_SECONDS", "3.0"))
SPAM_MESSAGE_LIMIT = int(os.getenv("SPAM_MESSAGE_LIMIT", "4"))