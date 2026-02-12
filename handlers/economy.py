# handlers/economy.py
import random
from telegram import Update
from telegram.ext import ContextTypes
from services import economy, antispam

async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Updates user stats and awards random points.
    """
    if not update.message or not update.message.from_user:
        return

    user = update.effective_user
    
    # 1. Ensure user exists in DB
    economy.get_or_create_user(user.id, user.username, user.first_name)
    
    # 2. Update Message Count
    economy.increment_stats(user.id)
    
    # 3. Check Shadow Mute (Admin Penalty)
    if antispam.is_shadow_muted(user.id):
        return # No points for bad admins!

    # 4. Award Points (10% Chance)
    CHANCE = 0.15
    roll = random.random()
    if roll < CHANCE:
        economy.add_points(user.id, 1.0)