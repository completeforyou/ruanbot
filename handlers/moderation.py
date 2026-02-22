# handlers/moderation.py
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from services import antispam, economy
from utils.admin_cache import is_user_admin

async def check_spam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks for spam. If detected, punishes user.
    Returns True if spam was detected (stop processing).
    """
    if not update.message or not update.message.from_user:
        return False

    user = update.effective_user
    chat = update.effective_chat
    
    # --- NEW: Extract media_group_id safely ---
    media_group_id = update.message.media_group_id

    # FETCH DYNAMIC SETTINGS
    sys_config = await economy.get_system_config()
    limit = sys_config['spam_limit']
    timeframe = sys_config['spam_threshold']
    
    # --- PHASE 2: ANTI-SPAM ---
    # Pass the media_group_id to the function
    is_spam = antispam.check_is_spamming(
        user.id, 
        limit=limit, 
        timeframe=timeframe,
        media_group_id=media_group_id
    )
    
    if is_spam:
        # 2. Check Admin Status
        is_admin = await is_user_admin(chat.id, user.id, context.bot)

        # 3. Apply Punishment
        if is_admin:
            # Shadow Mute (No points for 3 mins)
            antispam.add_shadow_mute(user.id, duration_minutes=3)
            await update.message.reply_text(
                f"⚠️ {user.mention_html()} 在刷屏! \n🛡 管理刷屏惩罚,三分钟无法获得积分！",
                parse_mode='HTML'
            )
        else:
            # Real Mute (Cannot speak for 3 mins)
            until = datetime.now() + timedelta(minutes=3)
            try:
                await chat.restrict_member(
                    user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until
                )
                await update.message.reply_text(f"🚫 {user.mention_html()} 禁言三分钟(刷屏)", parse_mode='HTML')
            except Exception as e:
                print(f"Failed to mute: {e}")
        
        return True # Stop other handlers
    
    return False # Safe to proceed