# handlers/invitation.py
from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from telegram.helpers import mention_html
from telegram.error import TelegramError
from database import Session
from models.referral import Referral
from models.invite_link import InviteLink
from models.user import User
from services import economy

config = economy.get_system_config()
reward_points = config['invite_reward_points']
# Config
async def generate_invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Command: 专属链接
    Checks for an existing link first. If none, generates a new one.
    """
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == 'private':
        await update.message.reply_text("⚠️ 请在群组中使用此命令。")
        return

    session = Session()
    try:
        # 1. Check if user already has a link for this chat
        existing_link = session.query(InviteLink).filter_by(
            creator_id=user.id, 
            chat_id=chat.id
        ).first()

        invite_url = None

        if existing_link:
            # Reuse existing link
            invite_url = existing_link.link
        else:
            # Generate NEW link
            try:
                invite = await context.bot.create_chat_invite_link(
                    chat_id=chat.id,
                    name=f"Invite: {user.first_name}", 
                    creates_join_request=False
                )
                invite_url = invite.invite_link
                
                # Save to DB
                new_link = InviteLink(
                    link=invite_url,
                    creator_id=user.id,
                    chat_id=chat.id
                )
                session.add(new_link)
                session.commit()
            except TelegramError:
                await update.message.reply_text("❌ 生成失败: 请确保机器人是群管理员，并且有 '管理邀请链接' 的权限。")
                return

        # 2. Send Response (Monospace for easy copying)
        # <code> tags make it copyable on click and not a hyperlink
        await update.message.reply_text(
            f"✅ {user.mention_html()} 的专属链接:\n\n"
            f"<code>{invite_url}</code>\n\n"
            f"🎉 邀请新用户加入，每位奖励 {reward_points} 积分!",
            parse_mode='HTML'
        )
        
    except Exception as e:
        print(f"Invite Generation Error: {e}")
        session.rollback()
    finally:
        session.close()

async def track_join_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggered when a user status changes. 
    Checks if an invite link was used and awards points.
    """
    if not update.chat_member:
        return

    # 1. Extract Info
    new_member = update.chat_member.new_chat_member
    user = new_member.user
    invite_used = update.chat_member.invite_link
    
    # 2. Quick Checks
    if not invite_used:
        return

    # Must be currently IN the group (not left/kicked)
    if new_member.status in ['left', 'kicked']:
        return

    link_url = invite_used.invite_link

    

    # 3. Database Processing
    session = Session()
    try:
        # A. Find who created this link
        link_record = session.query(InviteLink).filter_by(link=link_url).first()
        
        if not link_record:
            return

        inviter_id = link_record.creator_id

        # B. Prevent Self-Referral
        if inviter_id == user.id:
            return 

        # C. Check Duplicate Referral
        exists = session.query(Referral).filter_by(
            inviter_id=inviter_id, 
            invited_user_id=user.id
        ).first()

        if exists:
            return
        
        # D. Success: Save Referral
        new_ref = Referral(inviter_id=inviter_id, invited_user_id=user.id)
        session.add(new_ref)
        
        # Get Inviter Name for display
        inviter_user = session.query(User).filter_by(id=inviter_id).first()
        inviter_name = inviter_user.full_name if inviter_user else str(inviter_id)

        session.commit()
        session.close() # Close session before calling economy service
        
        # Award Points
        economy.add_points(inviter_id, float(reward_points))

        # Notify Group
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📢 <b>邀请成功!</b>\n"
                 f"🎉 {mention_html(inviter_name)} 邀请了 {user.mention_html()}!\n"
                 f"💰 邀请人获得奖励: <b>{reward_points}</b> 积分",
            parse_mode='HTML'
        )

    except Exception as e:
        print(f"Referral Error: {e}")
        session.rollback()
        session.close()