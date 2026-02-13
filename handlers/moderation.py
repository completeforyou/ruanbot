# handlers/moderation.py
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from services import antispam, content_filter
import config

async def check_spam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks for spam. If detected, punishes user.
    Returns True if spam was detected (stop processing).
    """
    if not update.message or not update.message.from_user:
        return False

    user = update.effective_user
    chat = update.effective_chat

    # --- PHASE 1: CONTENT FILTER ---
    # Check for content violations
    violation = content_filter.check_violation(update.message)
    
    if violation:
        # 1. Check Admin (Admins bypass filters)
        try:
            member = await context.bot.get_chat_member(chat.id, user.id)
            is_admin = member.status in ['administrator', 'creator']
        except:
            is_admin = False

        if not is_admin:
            try:
                # DELETE the bad message
                await update.message.delete()
                
                # Send a temporary warning
                warn_msg = await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"⚠️ {user.mention_html()} 信息已删除: <b>{violation}</b>",
                    parse_mode='HTML'
                )
                
                # (Optional) Delete warning after 5 seconds to keep chat clean
                context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(chat.id, warn_msg.message_id), 5)
                
            except Exception as e:
                print(f"Failed to delete message: {e}")
            
            return True # Stop processing (No points for you!)
    
    # --- PHASE 2: ANTI-SPAM ---
    # Only run if content was safe
    is_spam = antispam.check_is_spamming(
        user.id, 
        limit=config.SPAM_MESSAGE_LIMIT, 
        timeframe=config.SPAM_THRESHOLD_SECONDS
    )
    
    if is_spam:
        # 2. Check Admin Status
        try:
            member = await context.bot.get_chat_member(chat.id, user.id)
            is_admin = member.status in ['administrator', 'creator']
        except:
            is_admin = False

        # 3. Apply Punishment
        if is_admin:
            # Shadow Mute (No points for 3 mins)
            antispam.add_shadow_mute(user.id, duration_minutes=3)
            await update.message.reply_text(
                f"⚠️ {user.mention_html()} is spamming! \n🛡 管理刷屏惩罚,三分钟无法获得积分！",
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