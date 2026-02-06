# main.py
import logging
from datetime import datetime, timedelta
import random
import time
import os
from difflib import SequenceMatcher
from telegram import Update, ChatPermissions
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
spam_cache = {}          # Tracks message timestamps: {user_id: [t1, t2...]}
shadow_mutes = {}        # Tracks admin penalty end times: {user_id: timestamp_end}

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    user = update.message.from_user
    chat_id = update.message.chat_id
    
    # Check Admin Status
    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        is_admin = member.status in ['administrator', 'creator']
    except:
        is_admin = False

    # Database Session
    session = Session()
    db_user = session.query(User).filter_by(id=user.id).first()
    
    if not db_user:
        db_user = User(id=user.id, username=user.username, full_name=user.first_name)
        session.add(db_user)
        session.commit()

    # ==================================================================
    # FEATURE 1: ANTI-SPAM (Sliding Window: >4 msgs in 3 sec)
    # ==================================================================
    current_time = datetime.now().timestamp()
    
    # Initialize cache for user
    if user.id not in spam_cache:
        spam_cache[user.id] = []
    
    # Add current message time
    spam_cache[user.id].append(current_time)
    
    # Filter: Keep only timestamps from the last 3 seconds
    spam_cache[user.id] = [t for t in spam_cache[user.id] if current_time - t <= 3.0]
    
    # CHECK: Did they breach the limit?
    if len(spam_cache[user.id]) > 4:
        # Clear cache so detection doesn't trigger on every single message after the 4th
        spam_cache[user.id] = []
        
        penalty_end_time = datetime.now() + timedelta(minutes=3)
        
        if is_admin:
            # --- PUNISHMENT: ADMIN (Shadow Mute) ---
            # Set a flag in memory that expires in 3 mins
            shadow_mutes[user.id] = penalty_end_time.timestamp()
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {user.mention_html()} 刷屏! \n🛡 **管理惩罚:** 3 分钟内发言无法获得积分",
                parse_mode='HTML'
            )
        else:
            # --- PUNISHMENT: USER (Real Mute) ---
            try:
                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=penalty_end_time
                )
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text=f"🚫 {user.mention_html()} 被禁言 3 分钟 (刷屏).",
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f"Failed to mute user: {e}")
        
        session.close()
        return # Stop processing (No rewards for this spam message)

    # ==================================================================
    # FEATURE 4: ACTIVITY REWARD (10% Chance -> 1 Point)
    # ==================================================================
    
    # Check if user is Shadow Muted (Admin Penalty)
    is_shadow_muted = False
    if user.id in shadow_mutes:
        if current_time < shadow_mutes[user.id]:
            is_shadow_muted = True
        else:
            # Penalty expired
            del shadow_mutes[user.id]

    if not is_shadow_muted:
        # 10% chance to earn 1 point
        if random.random() < 0.10:
            db_user.points += 1
            # Optional: Notify user occasionally? 
            # await update.message.reply_text("🍀 You found a point!")

    # Update total stats
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