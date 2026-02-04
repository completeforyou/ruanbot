# main.py
import logging
import re
import random
import time
import os
from difflib import SequenceMatcher
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from database import Session, User, init_db

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Configuration ---
TOKEN = os.getenv("TOKEN") # Put this in Railway Variables
MAX_DAILY_POINTS = 100
SPAM_THRESHOLD_SECONDS = 3
REPEAT_THRESHOLD = 0.8 # 80% similarity for ProMax

if not TOKEN:
    raise ValueError("No TOKEN found! Please add TOKEN to Railway Variables.")

# --- In-Memory Cache for Spam Detection ---
# Format: {user_id: {'last_time': timestamp, 'last_text': "string", 'repeat_count': int}}
user_cache = {}

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    user_id = update.message.from_user.id
    username = update.message.from_user.username or ""
    first_name = update.message.from_user.first_name or ""
    text = update.message.text or ""
    
    # Database Session
    session = Session()
    db_user = session.query(User).filter_by(id=user_id).first()
    
    # Create user if not exists
    if not db_user:
        db_user = User(id=user_id, username=username, full_name=first_name)
        session.add(db_user)
        session.commit()


    # --- Feature 1: Anti-Spam Logic (Pro & ProMax) ---
    current_time = time.time()
    user_data = user_cache.get(user_id, {'last_time': 0, 'last_text': "", 'repeat_count': 0})
    
    is_spam = False
    deduct_points = 0
    
    # 1. Frequency Check (Basic)
    if current_time - user_data['last_time'] < 1: # 1 second limit
        is_spam = True
        
    # 2. Semantic Repetition (ProMax)
    similarity = SequenceMatcher(None, text, user_data['last_text']).ratio()
    if similarity > REPEAT_THRESHOLD and (current_time - user_data['last_time'] < 5):
        user_data['repeat_count'] += 1
    else:
        user_data['repeat_count'] = 0 # Reset if text is different or time passed
        
    if user_data['repeat_count'] >= 3: # ProMax Trigger
        is_spam = True
        deduct_points = 50 # Example penalty
        await update.message.delete()
        await update.message.reply_text("🚫 Spam detected (ProMax). Points deducted.")
    
    # Update Cache
    user_data['last_time'] = current_time
    user_data['last_text'] = text
    user_cache[user_id] = user_data

    if is_spam:
        if deduct_points > 0:
            db_user.points = max(0, db_user.points - deduct_points)
            session.commit()
        session.close()
        return # Stop processing rewards if spam

    # --- Feature 4: Activity Rewards ---
    # Check if daily cap reached
    # (Simplified logic: In production, reset daily counts via cron/scheduler)
    if db_user.points < MAX_DAILY_POINTS:
        chance = random.random()
        reward = 0
        
        # 10% chance for reward
        if chance < 0.10: 
            reward = 5
            # 1% chance for Crit (Double)
            if chance < 0.01:
                reward = 10
                await update.message.reply_text("🔥 CRIT! Double Points!")
            
            db_user.points += reward
            db_user.msg_count_total += 1
            session.commit()
            
    session.close()

if __name__ == '__main__':
    # Initialize DB
    init_db()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Add Handler for text messages
    msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), process_message)
    application.add_handler(msg_handler)
    
    print("Bot is running...")
    application.run_polling()