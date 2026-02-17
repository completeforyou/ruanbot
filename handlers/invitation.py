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
    if not update.chat_member:
        return

    # 1. Extract Basic Info
    new_member = update.chat_member.new_chat_member
    old_member = update.chat_member.old_chat_member
    user = new_member.user
    invite_used = update.chat_member.invite_link
    
    logger.info(f"🔍 [TRACE] Update for: {user.first_name} (ID: {user.id})")
    logger.info(f"   Status: {old_member.status} -> {new_member.status}")

    # 2. Check for Invite Link
    # This is the most critical check. 
    if not invite_used:
        # If no link is in the update, we cannot track who invited them.
        logger.info("   ℹ️ No invite link detected in this update. (Ignored)")
        return

    link_url = invite_used.invite_link
    logger.info(f"   🔗 Invite Link Found: {link_url}")

    # 3. Status Safety Check
    # We generally only want to reward if they are IN the group now.
    # 'left' or 'kicked' means they are gone.
    if new_member.status in ['left', 'kicked']:
        logger.info("   ❌ User left or was kicked. No reward.")
        return

    # If we are here, we have a LINK and the user is PRESENT.
    # We proceed regardless of whether it was 'restricted->restricted' or 'left->member'.
    await process_referral(update, context, user, link_url)

async def process_referral(update, context, user, link_url):
    session = Session()
    try:
        # A. Find the link owner
        link_record = session.query(InviteLink).filter_by(link=link_url).first()
        if not link_record:
            logger.warning(f"   ⚠️ Link not found in DB: {link_url}")
            return

        inviter_id = link_record.creator_id

        # B. Self-Referral Check
        if inviter_id == user.id:
            logger.info("   ⚠️ Self-referral ignored.")
            return 

        # C. Duplicate Check
        exists = session.query(Referral).filter_by(
            inviter_id=inviter_id, 
            invited_user_id=user.id
        ).first()

        if exists:
            logger.info(f"   ⚠️ Referral already exists for {inviter_id} -> {user.id}")
            return
        
        # D. Success: Save & Reward
        logger.info(f"   ✅ SUCCESS! Crediting {inviter_id} for inviting {user.id}")
        
        new_ref = Referral(inviter_id=inviter_id, invited_user_id=user.id)
        session.add(new_ref)
        session.commit()
        session.close() # Close safely before economy call
        
        # Award Points
        economy.add_points(inviter_id, float(INVITE_REWARD_POINTS))

        # Notify
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📢 <b>邀请成功!</b>\n"
                 f"🎉 用户 <a href='tg://user?id={inviter_id}'>{inviter_id}</a> 邀请了 {user.mention_html()}!\n"
                 f"💰 邀请人获得奖励: <b>{INVITE_REWARD_POINTS}</b> 积分",
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"   ❌ Referral Error: {e}")
        session.rollback()
        session.close()