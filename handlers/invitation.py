# handlers/invitation.py
import logging
from telegram import Update, ChatMember, ChatMemberUpdated
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from database import Session
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
        invite = await context.bot.create_chat_invite_link(
            chat_id=chat.id,
            name=f"Invite: {user.first_name}", 
            creates_join_request=False
        )
        
        # 2. Save mapping to DB
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

        await update.message.reply_text(
            f"✅ {user.mention_html()} 的专属链接:\n\n"
            f"{invite.invite_link}\n\n"
            f"🎉 邀请新用户加入，每位奖励 {INVITE_REWARD_POINTS} 积分!",
            parse_mode='HTML'
        )
        
    except TelegramError as e:
        logger.error(f"Generate Link Error: {e}")
        await update.message.reply_text("❌ 生成失败: 请确保机器人是群管理员。")

async def track_join_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggered when a user status changes.
    """
    # --- DEBUG SECTION: LOG EVERYTHING ---
    if not update.chat_member:
        return

    old = update.chat_member.old_chat_member
    new = update.chat_member.new_chat_member
    user = new.user
    
    logger.info(f"🔍 [TRACE] Member Update Triggered for: {user.first_name} ({user.id})")
    logger.info(f"   Status Change: {old.status} -> {new.status}")
    
    # Check if invite link is present in the update object
    if update.chat_member.invite_link:
        logger.info(f"   🔗 Invite Link in Update: {update.chat_member.invite_link.invite_link}")
    else:
        logger.info(f"   🔗 Invite Link in Update: None (Public join or bot not admin)")
    # -------------------------------------

    # 1. Check if it's a valid "Join" event
    result = _extract_status_change(update.chat_member)
    if result is None: 
        logger.info("   ❌ Logic: No relevant status change detected (e.g. member->member re-check).")
        return

    was_member, is_member = result
    
    if was_member and is_member:
        logger.info("   ❌ Logic: User was already a member.")
        return
    if not is_member:
        logger.info("   ❌ Logic: User left or was kicked.")
        return

    # 2. Identify the Invite Link
    invite_used = update.chat_member.invite_link
    if not invite_used:
        logger.warning("   ⚠️ User joined, but no invite link detected. (Used public link?)")
        return

    link_url = invite_used.invite_link
    
    # 3. Lookup in Database
    session = Session()
    try:
        link_record = session.query(InviteLink).filter_by(link=link_url).first()
        
        if not link_record:
            logger.warning(f"   ⚠️ Link not found in DB: {link_url}")
            return

        inviter_id = link_record.creator_id

        # Prevent Self-Referral
        if inviter_id == user.id:
            logger.info("   ⚠️ Self-referral ignored.")
            return 

        # 4. Check Duplicate Referral
        exists = session.query(Referral).filter_by(
            inviter_id=inviter_id, 
            invited_user_id=user.id
        ).first()

        if exists:
            logger.info("   ⚠️ Referral already exists.")
            return
        
        # 5. Save & Reward
        logger.info(f"   ✅ SUCCESS! Crediting {inviter_id} for inviting {user.id}")
        
        new_ref = Referral(inviter_id=inviter_id, invited_user_id=user.id)
        session.add(new_ref)
        session.commit()
        session.close() # Close before calling economy service
        
        economy.add_points(inviter_id, float(INVITE_REWARD_POINTS))

        # 6. Notify
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📢 <b>邀请成功!</b>\n"
                 f"🎉 用户 <a href='tg://user?id={inviter_id}'>{inviter_id}</a> 邀请了 {user.mention_html()}!\n"
                 f"💰 邀请人获得奖励: <b>{INVITE_REWARD_POINTS}</b> 积分",
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        session.rollback()
        session.close()

def _extract_status_change(chat_member_update: ChatMemberUpdated):
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