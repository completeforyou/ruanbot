# handlers/invitation.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.helpers import mention_html
from telegram.error import TelegramError

from database import AsyncSessionLocal
from sqlalchemy import select

from models.referral import Referral
from models.invite_link import InviteLink
from models.user import User
from services import economy

# Store pending invites in memory until the user passes verification
# Format: {invited_user_id: inviter_user_id}
_pending_invites = {}

def clear_pending_invite(user_id: int):
    """Removes a user from the pending invite list if they fail verification."""
    if user_id in _pending_invites:
        del _pending_invites[user_id]

async def request_invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Command: 专属链接 (Used in the group)
    Sends a button that redirects the user to the bot's DM with a deep link payload.
    """
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == 'private':
        await update.message.reply_text("⚠️ 请在群组中使用此命令获取该群组的邀请链接。")
        return

    bot_username = context.bot.username
    
    # Create the deep link payload including the group's chat ID
    payload = f"invite_{chat.id}_{user.id}"
    deep_link = f"https://t.me/{bot_username}?start={payload}"

    # --- NEW: Await the async config fetch ---
    config = await economy.get_system_config()
    reward_points = config['invite_reward_points']

    keyboard = [[InlineKeyboardButton("📩 点我私聊获取专属链接", url=deep_link)]]
    
    await update.message.reply_text(
        f"👋 {user.mention_html()}，✅ 您的专属链接生成成功:\n"
        f"🎉 邀请新用户加入，每位验证成功后即可获得 <b>{reward_points}</b> 积分奖励!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Command: /start (Used in Private DM)
    Reads the deep link payload and generates the link if applicable.
    """
    chat = update.effective_chat
    user = update.effective_user

    if chat.type != 'private':
        return # Ignore /start commands in groups to prevent spam

    args = context.args
    
    if not args:
        return

    payload = args[0]
    
    if payload.startswith("invite_"):
        parts = payload.split("_")
        
        try:
            target_chat_id = int(parts[1])
            if len(parts) >= 3:
                target_user_id = int(parts[2])
                
                if user.id != target_user_id:
                    await update.message.reply_text("❌ 这是别人的链接！请在群组内发送 '专属链接' 来获取你自己的邀请链接。")
                    return
        except ValueError:
            await update.message.reply_text("❌ 无效的链接参数。")
            return

        # --- FIX: Ensure the inviter exists in the database so they can receive points later! ---
        await economy.get_or_create_user(user.id, user.username, user.first_name)

        # --- QUERY 1: ASYNC CONVERSION ---
        async with AsyncSessionLocal() as session:
            try:
                # Check if user already has a link for this specific chat
                result = await session.execute(
                    select(InviteLink).filter_by(creator_id=user.id, chat_id=target_chat_id)
                )
                existing_link = result.scalars().first()

                invite_url = None

                if existing_link:
                    invite_url = existing_link.link
                else:
                    try:
                        invite = await context.bot.create_chat_invite_link(
                            chat_id=target_chat_id,
                            name=f"Invite: {user.first_name}", 
                            creates_join_request=False
                        )
                        invite_url = invite.invite_link
                        
                        new_link = InviteLink(
                            link=invite_url,
                            creator_id=user.id,
                            chat_id=target_chat_id
                        )
                        session.add(new_link)
                        await session.commit()
                    except TelegramError as e:
                        await update.message.reply_text(f"❌ 生成失败: 请确保机器人在目标群组中是管理员，并且拥有 '管理邀请链接' 的权限。\n错误代码: {e}")
                        return
                
                await update.message.reply_text(
                    f"<code>{invite_url}</code>\n\n",
                    parse_mode='HTML'
                )
                
            except Exception as e:
                print(f"Invite Generation Error: {e}")
                await session.rollback()

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

    # --- QUERY 2: ASYNC CONVERSION ---
    async with AsyncSessionLocal() as session:
        try:
            result_link = await session.execute(select(InviteLink).filter_by(link=link_url))
            link_record = result_link.scalars().first()
            
            if not link_record:
                return

            inviter_id = link_record.creator_id

            if inviter_id == user.id:
                return 

            result_ref = await session.execute(
                select(Referral).filter_by(inviter_id=inviter_id, invited_user_id=user.id)
            )
            exists = result_ref.scalars().first()

            if exists:
                return
            
            _pending_invites[user.id] = inviter_id

        except Exception as e:
            print(f"Referral Tracking Error: {e}")

async def register_verified_invite(invited_user, context: ContextTypes.DEFAULT_TYPE):
    """
    Called by the verification system AFTER the user passes the math captcha.
    Logs the referral to the database, waiting to be rewarded.
    """
    if invited_user.id not in _pending_invites:
        return
    
    inviter_id = _pending_invites.pop(invited_user.id)

    # --- QUERY 3: ASYNC CONVERSION ---
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Referral).filter_by(inviter_id=inviter_id, invited_user_id=invited_user.id)
            )
            exists = result.scalars().first()

            if exists:
                return
                
            new_ref = Referral(inviter_id=inviter_id, invited_user_id=invited_user.id)
            session.add(new_ref)
            await session.commit()
        except Exception as e:
            print(f"Referral Registration Error: {e}")
            await session.rollback()

async def check_and_reward_invite(invited_user, chat_id, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggered when an invited user hits 50 messages.
    """
    inviter_id = None
    inviter_name = None

    # --- QUERY 4: ASYNC CONVERSION ---
    async with AsyncSessionLocal() as session:
        try:
            result_ref = await session.execute(
                select(Referral).filter_by(invited_user_id=invited_user.id, is_rewarded=False)
            )
            referral = result_ref.scalars().first()

            if not referral:
                return 

            referral.is_rewarded = True
            inviter_id = referral.inviter_id
            
            result_user = await session.execute(select(User).filter_by(id=inviter_id))
            inviter_user = result_user.scalars().first()
            inviter_name = inviter_user.full_name if inviter_user else str(inviter_id)

            await session.commit()
        except Exception as e:
            print(f"Referral Awarding Error: {e}")
            await session.rollback()
            return  # Stop executing if there was a DB error
            
    # Award Points (Executed after the DB session closes to free up the connection faster)
    if inviter_id:
        config = await economy.get_system_config()
        reward_points = config['invite_reward_points']
        await economy.add_points(inviter_id, float(reward_points))

        # Notify Group
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📢 <b>邀请奖励发放!</b>\n"
                 f"🎉 {invited_user.mention_html()} 成功满足条件！\n"
                 f"💰 邀请人 {mention_html(inviter_id, inviter_name)} 获得 <b>{reward_points}</b> 积分",
            parse_mode='HTML'
        )