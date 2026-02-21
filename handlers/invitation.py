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

# Store pending invites in memory until the user passes verification
# Format: {invited_user_id: inviter_user_id}
_pending_invites = {}

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
        existing_link = session.query(InviteLink).filter_by(
            creator_id=user.id, 
            chat_id=chat.id
        ).first()

        invite_url = None

        if existing_link:
            invite_url = existing_link.link
        else:
            try:
                invite = await context.bot.create_chat_invite_link(
                    chat_id=chat.id,
                    name=f"Invite: {user.first_name}", 
                    creates_join_request=False
                )
                invite_url = invite.invite_link
                
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

        config = economy.get_system_config()
        reward_points = config['invite_reward_points']

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
    Checks if an invite link was used and saves it as PENDING.
    """
    if not update.chat_member:
        return

    new_member = update.chat_member.new_chat_member
    user = new_member.user
    invite_used = update.chat_member.invite_link
    
    if not invite_used or new_member.status in ['left', 'kicked']:
        return

    link_url = invite_used.invite_link

    session = Session()
    try:
        link_record = session.query(InviteLink).filter_by(link=link_url).first()
        if not link_record:
            return

        inviter_id = link_record.creator_id

        # Prevent Self-Referral
        if inviter_id == user.id:
            return 

        # Check if already referred previously
        exists = session.query(Referral).filter_by(
            inviter_id=inviter_id, 
            invited_user_id=user.id
        ).first()

        if exists:
            return
        
        # Save as a pending invite! Will be rewarded after verification.
        _pending_invites[user.id] = inviter_id

    except Exception as e:
        print(f"Referral Tracking Error: {e}")
    finally:
        session.close()

async def award_invite_points(invited_user, chat_id, context: ContextTypes.DEFAULT_TYPE):
    """
    Called by the verification system AFTER the user passes the math captcha.
    Rewards the points and logs the referral to the database.
    """
    # Check if this user was invited by someone
    if invited_user.id not in _pending_invites:
        return
    
    # Pop it from memory so we don't reward twice
    inviter_id = _pending_invites.pop(invited_user.id)

    session = Session()
    try:
        # Final safety check to prevent duplicates
        exists = session.query(Referral).filter_by(
            inviter_id=inviter_id, 
            invited_user_id=invited_user.id
        ).first()

        if exists:
            return
            
        # 1. Save Referral to DB
        new_ref = Referral(inviter_id=inviter_id, invited_user_id=invited_user.id)
        session.add(new_ref)
        
        # 2. Get Inviter Name
        inviter_user = session.query(User).filter_by(id=inviter_id).first()
        inviter_name = inviter_user.full_name if inviter_user else str(inviter_id)

        session.commit()
        session.close() 
        
        # 3. Award Points (Fetch config dynamically!)
        config = economy.get_system_config()
        reward_points = config['invite_reward_points']
        economy.add_points(inviter_id, float(reward_points))

        # 4. Notify Group
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📢 <b>邀请成功!</b>\n"
                 f"🎉 {mention_html(inviter_id, inviter_name)} 邀请了 {invited_user.mention_html()}!\n"
                 f"💰 邀请人获得奖励: <b>{reward_points}</b> 积分",
            parse_mode='HTML'
        )

    except Exception as e:
        print(f"Referral Awarding Error: {e}")
        session.rollback()
        session.close()