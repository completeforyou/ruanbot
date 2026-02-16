# handlers/invitation.py
from telegram import Update, ChatMember, ChatMemberUpdated
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from database import Session, User
from models.referral import Referral
from models.invite_link import InviteLink
from services import economy

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
        
        # 2. Save mapping to DB (Link URL -> User ID)
        session = Session()
        try:
            # Remove old links for this user/chat if you want to keep it clean (Optional)
            # session.query(InviteLink).filter_by(creator_id=user.id, chat_id=chat.id).delete()
            
            new_link = InviteLink(
                link=invite.invite_link,
                creator_id=user.id,
                chat_id=chat.id
            )
            session.add(new_link)
            session.commit()
            print(f"✅ Saved invite link: {invite.invite_link} -> User {user.id}")
            
        except Exception as e:
            print(f"❌ Database Error saving link: {e}")
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
        await update.message.reply_text("❌ 生成失败: 机器人不是管理员或没有 '管理邀请链接' 权限。")

async def track_join_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"🔎 Checking join event in chat {update.effective_chat.id}...")

    # 1. Check Status Change (Joined?)
    result = _extract_status_change(update.chat_member)
    if result is None: return

    was_member, is_member = result
    if was_member or not is_member: return

    # 2. Get the Link Info
    invite_used = update.chat_member.invite_link
    new_member = update.chat_member.new_chat_member
    
    if not invite_used:
        print("❌ User joined without a specific invite link (or via vanity URL).")
        return

    link_url = invite_used.invite_link
    print(f"🔗 Link used: {link_url}")

    # 3. LOOKUP IN DATABASE
    session = Session()
    try:
        link_record = session.query(InviteLink).filter_by(link=link_url).first()
        
        if not link_record:
            print(f"❌ Link not found in DB (Maybe created before update?): {link_url}")
            return

        inviter_id = link_record.creator_id
        joined_user = new_member.user

        if inviter_id == joined_user.id:
            return # Self-invite

        print(f"✅ Real Inviter Found: {inviter_id}")

        # 4. Check Duplicate Referral
        exists = session.query(Referral).filter_by(
            inviter_id=inviter_id, 
            invited_user_id=joined_user.id
        ).first()

        if exists:
            print("⚠️ Referral already exists.")
            return
        
        # 5. Save & Reward
        new_ref = Referral(inviter_id=inviter_id, invited_user_id=joined_user.id)
        session.add(new_ref)
        
        # Add points (Use economy service)
        economy.add_points(inviter_id, float(INVITE_REWARD_POINTS))
        
        session.commit()

        # 6. Notify
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📢 邀请成功!\n"
                 f"🎉 用户 `{inviter_id}` 邀请了 {joined_user.mention_html()}!\n"
                 f"💰 获得奖励: {INVITE_REWARD_POINTS} 积分",
            parse_mode='HTML'
        )

    except Exception as e:
        print(f"❌ Referral Error: {e}")
        session.rollback()
    finally:
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