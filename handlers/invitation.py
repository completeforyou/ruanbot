# handlers/invitation.py
import logging
from telegram import Update, ChatMember, ChatMemberUpdated
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from database import Session
from models.referral import Referral
from models.invite_link import InviteLink
from services import economy

# Config
INVITE_REWARD_POINTS = 100

# Set up logging to print to console
logger = logging.getLogger(__name__)

async def generate_invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == 'private':
        await update.message.reply_text("⚠️ 请在群组中使用此命令。")
        return

    try:
        # Create link
        invite = await context.bot.create_chat_invite_link(
            chat_id=chat.id,
            name=f"Invite: {user.first_name}", 
            creates_join_request=False
        )
        
        # Save to DB
        session = Session()
        try:
            # We strip whitespace to ensure exact match later
            link_clean = invite.invite_link.strip()
            
            new_link = InviteLink(
                link=link_clean,
                creator_id=user.id,
                chat_id=chat.id
            )
            session.add(new_link)
            session.commit()
            logger.info(f"✅ LINK SAVED: {link_clean} -> User {user.id}")
            
        except Exception as e:
            logger.error(f"❌ DB ERROR: {e}")
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
        await update.message.reply_text("❌ 生成失败: 机器人需要管理员权限。")
        logger.error(f"Generate Error: {e}")

async def track_join_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    DEBUG VERSION: Prints exactly what is happening.
    """
    logger.info("⚡️ UPDATE RECEIVED: Checking Chat Member Status...")

    # 1. Check if it's a join event
    result = _extract_status_change(update.chat_member)
    if result is None:
        return

    was_member, is_member = result
    
    # Debug print
    logger.info(f"👤 Status Change: WasMember={was_member}, IsMember={is_member}")

    if was_member or not is_member:
        return # Not a new join

    # 2. Extract Data
    new_member = update.chat_member.new_chat_member
    invite_used = update.chat_member.invite_link

    logger.info(f"👤 User Joined: {new_member.user.id} ({new_member.user.first_name})")

    # --- CRITICAL CHECK ---
    if not invite_used:
        logger.warning("❌ NO INVITE LINK FOUND in update. (User might have joined via username/public button)")
        return

    link_url = invite_used.invite_link.strip()
    logger.info(f"🔗 Link Used: {link_url}")

    # 3. Lookup in DB
    session = Session()
    try:
        # Debug: Print all links to verify
        # all_links = session.query(InviteLink).all()
        # logger.info(f"🔍 Links in DB: {[l.link for l in all_links]}")

        link_record = session.query(InviteLink).filter_by(link=link_url).first()
        
        if not link_record:
            logger.warning(f"❌ LINK NOT FOUND IN DB: {link_url}")
            return

        inviter_id = link_record.creator_id
        joined_user = new_member.user

        logger.info(f"✅ Match Found! Inviter: {inviter_id}, Joiner: {joined_user.id}")

        # 4. Self-Invite Check
        if inviter_id == joined_user.id:
            logger.warning("⚠️ Self-invite detected. No points awarded.")
            return

        # 5. Duplicate Check
        exists = session.query(Referral).filter_by(
            inviter_id=inviter_id, 
            invited_user_id=joined_user.id
        ).first()

        if exists:
            logger.warning("⚠️ Referral already exists.")
            return
        
        # 6. Success: Save & Reward
        new_ref = Referral(inviter_id=inviter_id, invited_user_id=joined_user.id)
        session.add(new_ref)
        
        economy.add_points(inviter_id, float(INVITE_REWARD_POINTS))
        session.commit()
        
        logger.info(f"💰 POINTS AWARDED to {inviter_id}")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📢 邀请成功!\n"
                 f"🎉 用户 `{inviter_id}` 邀请了 {joined_user.mention_html()}!\n"
                 f"💰 获得奖励: {INVITE_REWARD_POINTS} 积分",
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"❌ PROCESS ERROR: {e}")
        session.rollback()
    finally:
        session.close()

def _extract_status_change(chat_member_update: ChatMemberUpdated):
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

    if status_change is None:
        return None

    old_status, new_status = status_change
    
    was_member = old_status in [
        ChatMember.MEMBER, ChatMember.OWNER, ChatMember.ADMINISTRATOR,
    ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)

    is_member = new_status in [
        ChatMember.MEMBER, ChatMember.OWNER, ChatMember.ADMINISTRATOR,
    ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)

    return was_member, is_member