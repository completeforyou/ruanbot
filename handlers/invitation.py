# handlers/invitation.py
import logging
from telegram import Update, ChatMember, ChatMemberUpdated
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from database import Session, User
from models.referral import Referral
from models.invite_link import InviteLink
from services import economy

# Setup Logging
logger = logging.getLogger(__name__)

# Config
INVITE_REWARD_POINTS = 20

async def generate_invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Command: 专属链接
    Generates a link and SAVES it to the DB mapped to the user.
    """
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == 'private':
        await update.message.reply_text("⚠️ 请在群组中使用此命令。")
        return

    try:
        # 1. Create the link
        # Note: We name it so we can track it easily in Telegram's native admin UI too
        invite = await context.bot.create_chat_invite_link(
            chat_id=chat.id,
            name=f"Invite: {user.first_name}", 
            creates_join_request=False
        )
        
        # 2. Save mapping to DB (Link URL -> User ID)
        session = Session()
        try:
            new_link = InviteLink(
                link=invite.invite_link,
                creator_id=user.id,
                chat_id=chat.id
            )
            session.add(new_link)
            session.commit()
            logger.info(f"✅ Saved invite link: {invite.invite_link} -> User {user.id}")
            
        except Exception as e:
            logger.error(f"❌ Database Error saving link: {e}")
            session.rollback()
        finally:
            session.close()

        # 3. Reply to user
        await update.message.reply_text(
            f"✅ {user.mention_html()} 的专属链接:\n\n"
            f"{invite.invite_link}\n\n"
            f"🎉 邀请新用户加入，每位奖励 {INVITE_REWARD_POINTS} 积分!",
            parse_mode='HTML'
        )
        
    except TelegramError as e:
        logger.error(f"Generate Link Error: {e}")
        await update.message.reply_text("❌ 生成失败: 请确保机器人是群管理员，并且有 '管理邀请链接' 的权限。")

async def track_join_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggered when a user status changes (e.g. Left -> Member).
    """
    # 1. Basic Filters
    if not update.chat_member:
        return

    # Extract status change
    result = _extract_status_change(update.chat_member)
    if result is None: 
        return

    was_member, is_member = result
    
    # We only care if they WEREN'T a member and NOW ARE a member (Join Event)
    if was_member or not is_member: 
        return

    # 2. Debug Info
    new_member = update.chat_member.new_chat_member.user
    logger.info(f"[INVITE_DEBUG] User {new_member.id} ({new_member.first_name}) joined chat {update.effective_chat.id}")

    # 3. Get Invite Link Info
    # IMPORTANT: This is NONE if bot is not admin or user used a public link
    invite_used = update.chat_member.invite_link
    
    if not invite_used:
        logger.warning(f"[INVITE_DEBUG] ❌ No invite link found in update. Bot might not be Admin, or user used public/vanity link.")
        return

    link_url = invite_used.invite_link
    logger.info(f"[INVITE_DEBUG] 🔗 Joined via link: {link_url}")

    # 4. Lookup in Database
    session = Session()
    try:
        link_record = session.query(InviteLink).filter_by(link=link_url).first()
        
        if not link_record:
            logger.warning(f"[INVITE_DEBUG] ❌ Link not found in DB: {link_url}")
            return

        inviter_id = link_record.creator_id

        # Prevent Self-Referral
        if inviter_id == new_member.id:
            logger.info(f"[INVITE_DEBUG] Self-invite ignored.")
            return 

        # 5. Check Duplicate Referral (Did this user already refer this person?)
        exists = session.query(Referral).filter_by(
            inviter_id=inviter_id, 
            invited_user_id=new_member.id
        ).first()

        if exists:
            logger.info(f"[INVITE_DEBUG] ⚠️ Referral already exists for this pair.")
            return
        
        # 6. Save & Reward
        logger.info(f"[INVITE_DEBUG] ✅ Processing Valid Referral: {inviter_id} -> {new_member.id}")
        
        # Create Referral Record
        new_ref = Referral(inviter_id=inviter_id, invited_user_id=new_member.id)
        session.add(new_ref)
        session.commit() # Commit referral first to ensure record exists
        
        # Add Points (Using economy service - it handles its own session/commit)
        # We close our session first to avoid transaction conflicts if using SQLite
        session.close() 
        
        economy.add_points(inviter_id, float(INVITE_REWARD_POINTS))

        # 7. Notify Group
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📢 <b>邀请成功!</b>\n"
                 f"🎉 用户 <a href='tg://user?id={inviter_id}'>{inviter_id}</a> 邀请了 {new_member.mention_html()}!\n"
                 f"💰 邀请人获得奖励: <b>{INVITE_REWARD_POINTS}</b> 积分",
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"[INVITE_DEBUG] ❌ Referral System Error: {e}")
        session.rollback()
        session.close()

def _extract_status_change(chat_member_update: ChatMemberUpdated):
    """
    Helper to determine if a user joined, left, or was kicked.
    """
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

    if status_change is None: return None

    old_status, new_status = status_change
    
    was_member = old_status in [
        ChatMember.MEMBER, ChatMember.OWNER, ChatMember.ADMINISTRATOR,
    ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)

    is_member = new_status in [
        ChatMember.MEMBER, ChatMember.OWNER, ChatMember.ADMINISTRATOR,
    ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)

    return was_member, is_member