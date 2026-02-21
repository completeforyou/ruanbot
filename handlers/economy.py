# handlers/economy.py
import random
from telegram import Update
from telegram.ext import ContextTypes
from services import economy, antispam, cleaner

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
    new_msg_count = economy.increment_stats(user.id)

    if new_msg_count == 50:
        from handlers import invitation
        await invitation.check_and_reward_invite(user, update.effective_chat.id, context)
    
    # 3. Check Shadow Mute (Admin Penalty)
    if antispam.is_shadow_muted(user.id):
        return # No points for bad admins!

    # 4. Award Points
    CHANCE = 0.20
    roll = random.random()
    if roll < CHANCE:
        economy.add_points(user.id, 1.0)

async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Responds to exact match '积分' with current balance.
    """
    if not update.message:
        return

    user = update.effective_user
    
    # Get clean data from DB
    balance = economy.get_user_balance(user.id)
    vouchers = economy.get_user_vouchers(user.id)
    
    # Reply to user
    await update.message.reply_text(
        f"💰 {user.first_name}, 当前积分: `{int(balance)}`\n🎟 兑奖券: `{int(vouchers)}`",
        parse_mode='Markdown'
    )

async def handle_check_in_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggered by '签到' or '/checkin'
    """
    user = update.effective_user
    
    success, msg, points = economy.process_check_in(user.id, user.username, user.first_name)
    
    reply_msg = None
    
    if success:
        reply_msg = await update.message.reply_text(
            f"{msg}\n💰 获得: {int(points)} 积分!",
            parse_mode='Markdown'
        )
    else:
        # Send failure message (Already checked in)
        reply_msg = await update.message.reply_text(msg)
        
    # MODIFIED: Schedule auto-delete after 20 seconds
    if reply_msg:
        context.job_queue.run_once(
            cleaner.delete_message_job,
            20,
            data={'chat_id': reply_msg.chat_id, 'message_id': reply_msg.message_id},
            name=f"del_checkin_{reply_msg.chat_id}_{reply_msg.message_id}"
        )