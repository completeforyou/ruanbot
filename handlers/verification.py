# handlers/verification.py
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, ChatMember
from telegram.ext import ContextTypes
from services import verification, cleaner
from database import Session, User, WelcomeConfig

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggered when a user status changes to MEMBER.
    Sends the strict math captcha.
    """
    # 1. Parse Update from ChatMemberHandler
    result = _extract_status_change(update.chat_member)
    if result is None:
        return

    was_member, is_member = result
    new_member = update.chat_member.new_chat_member
    user = new_member.user
    chat = update.effective_chat

    # 2. Filter: Only run if they weren't a member before, and are one now.
    #    Also ignore Bots.
    if user.is_bot:
        return
        
    if not was_member and is_member:
        # 3. Restrict (Mute)
        try:
            await chat.restrict_member(
                user.id, 
                permissions=ChatPermissions(can_send_messages=False)
            )
        except Exception as e:
            print(f"⚠️ Verification Error: Could not mute {user.full_name}. Is Bot Admin? {e}")
            return

        # 4. Generate Math Challenge
        question_text, answers = verification.generate_math_question(user.id)

        # 5. Build Math Buttons
        keyboard = []
        math_row = []
        for ans in answers:
            math_row.append(InlineKeyboardButton(str(ans), callback_data=f"verify_{user.id}_{ans}"))
            if len(math_row) == 2: 
                keyboard.append(math_row)
                math_row = []
        if math_row: keyboard.append(math_row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 6. Send Simple Captcha Message
        captcha_msg = await context.bot.send_message(
            chat_id=chat.id,
            text=f"🛑 欢迎加入, {user.mention_html()}!\n\n"
                 f"🛡 请完成验证\n"
                 f"请在三分钟内解答这道数学题,以验证你是人类:\n\n"
                 f"{question_text}",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

        # 7. Start 3-Minute Timeout
        async def timeout_kick(chat_id, user_id, message_id):
            await asyncio.sleep(180) 
            if verification.get_verification(user_id):
                verification.clear_verification(user_id)
                try:
                    await context.bot.ban_chat_member(chat_id, user_id)
                    await context.bot.unban_chat_member(chat_id, user_id)
                    await context.bot.delete_message(chat_id, message_id)
                except:
                    pass
                    
        context.application.create_task(timeout_kick(chat.id, user.id, captcha_msg.message_id))


def _extract_status_change(chat_member_update):
    """
    Helper to determine if the user joined.
    Returns (was_member, is_member) or None.
    """
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

    if status_change is None:
        return None

    old_status, new_status = status_change
    
    # Define what counts as "Being in the group"
    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)

    is_member = new_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)

    return was_member, is_member


async def verify_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when someone clicks the math answers."""
    query = update.callback_query
    clicker = query.from_user
    chat = update.effective_chat
    
    parts = query.data.split('_')
    target_user_id = int(parts[1])
    clicked_answer = int(parts[2])

    if clicker.id != target_user_id:
        await query.answer("❌ 你无需进行此验证!", show_alert=True)
        return

    v_data = verification.get_verification(target_user_id)
    if not v_data:
        await query.answer("❌ 验证已过期或未找到.", show_alert=True)
        return

    time_taken = time.time() - v_data['time']
    correct_answer = v_data['correct']
    
    # Clear memory
    verification.clear_verification(target_user_id)
    
    # --- RULE 1: Anti-Bot Check (< 1 second) ---
    if time_taken < 1.0:
        await query.answer("🤖 系统判定为机器人操作！点击速度异常", show_alert=True)
        try:
            await chat.ban_member(target_user_id)
            await chat.unban_member(target_user_id)
            await query.message.delete()
        except Exception as e:
            print(f"Kick failed: {e}")
        return

    # --- RULE 2: Correct Answer Check ---
    if clicked_answer == correct_answer:
        try:
            # 1. Unmute user
            await chat.restrict_member(
                target_user_id,
                permissions=ChatPermissions(
                    can_send_messages=True, can_send_audios=True, can_send_documents=True,
                    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            
            # 2. Mark as verified in DB AND Fetch Welcome Config
            session = Session()
            db_user = session.query(User).filter_by(id=target_user_id).first()
            if not db_user:
                db_user = User(id=clicker.id, username=clicker.username, full_name=clicker.first_name, is_verified=True)
                session.add(db_user)
            else:
                db_user.is_verified = True
            
            # Copy data safely
            config_obj = session.query(WelcomeConfig).filter_by(id=1).first()
            welcome_data = None
            if config_obj:
                welcome_data = {
                    'text': config_obj.text,
                    'media_id': config_obj.media_file_id,
                    'media_type': config_obj.media_type,
                    'buttons': config_obj.buttons
                }
            
            session.commit()
            session.close()

            # 4. Clean up the Captcha Message
            await query.answer("✅ 验证成功! 你现在可以聊天了.", show_alert=True)
            await query.message.delete()
            
            # 5. Send the Grand Personalized Welcome Message
            base_text = welcome_data['text'] if welcome_data and welcome_data['text'] else "🎉 Welcome to the group, {user}!"
            final_text = base_text.replace("{user}", clicker.mention_html())

            keyboard = []
            if welcome_data and welcome_data['buttons']:
                for btn in welcome_data['buttons']:
                    keyboard.append([InlineKeyboardButton(btn[0], url=btn[1])])
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            welcome_msg = None

            # Send Media/Text
            if welcome_data and welcome_data['media_id']:
                m_id = welcome_data['media_id']
                m_type = welcome_data['media_type']
                
                if m_type == 'photo':
                    welcome_msg = await context.bot.send_photo(chat_id=chat.id, photo=m_id, caption=final_text, reply_markup=reply_markup, parse_mode='HTML')
                elif m_type == 'video':
                    welcome_msg = await context.bot.send_video(chat_id=chat.id, video=m_id, caption=final_text, reply_markup=reply_markup, parse_mode='HTML')
                elif m_type == 'animation':
                    welcome_msg = await context.bot.send_animation(chat_id=chat.id, animation=m_id, caption=final_text, reply_markup=reply_markup, parse_mode='HTML')
            else:
                welcome_msg = await context.bot.send_message(chat_id=chat.id, text=final_text, reply_markup=reply_markup, parse_mode='HTML')
            
            # 6. Schedule Auto-Delete for Welcome Message (e.g. 60 seconds)
            if welcome_msg:
                context.job_queue.run_once(
                    cleaner.delete_message_job,
                    50, # Change this number to adjust how long it stays
                    data={'chat_id': welcome_msg.chat_id, 'message_id': welcome_msg.message_id},
                    name=f"del_welcome_{welcome_msg.chat_id}_{welcome_msg.message_id}"
                )

        except Exception as e:
            print(f"Unrestrict/Welcome failed: {e}")
    else:
        await query.answer("❌ 答案错误", show_alert=True)
        try:
            await chat.ban_member(target_user_id)
            await chat.unban_member(target_user_id)
            await query.message.delete()
        except Exception as e:
            print(f"Kick failed: {e}")