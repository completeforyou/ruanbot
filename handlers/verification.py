# handlers/verification.py
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import ContextTypes
from services import verification
from database import Session, User, WelcomeConfig

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when a new user joins. Sends the strict math captcha."""
    chat = update.effective_chat
    
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        
        # 1. Restrict
        try:
            await chat.restrict_member(member.id, permissions=ChatPermissions(can_send_messages=False))
        except:
            continue

        # 2. Generate Math Challenge
        question_text, answers = verification.generate_math_question(member.id)

        # 3. Build Math Buttons
        keyboard = []
        math_row = []
        for ans in answers:
            math_row.append(InlineKeyboardButton(str(ans), callback_data=f"verify_{member.id}_{ans}"))
            if len(math_row) == 2: 
                keyboard.append(math_row)
                math_row = []
        if math_row: keyboard.append(math_row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 4. Send Simple Captcha Message
        captcha_msg = await context.bot.send_message(
            chat_id=chat.id,
            text=f"🛑 **Stop right there, {member.mention_html()}!**\n\n"
                 f"🛡 **Verification Required**\n"
                 f"You have 3 minutes to solve this math problem to prove you are human:\n\n"
                 f"**{question_text}**",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

        # 5. Start 3-Minute Timeout
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
                    
        asyncio.create_task(timeout_kick(chat.id, member.id, captcha_msg.message_id))


async def verify_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when someone clicks the math answers."""
    query = update.callback_query
    clicker = query.from_user
    chat = update.effective_chat
    
    parts = query.data.split('_')
    target_user_id = int(parts[1])
    clicked_answer = int(parts[2])

    if clicker.id != target_user_id:
        await query.answer("❌ This verification is not for you!", show_alert=True)
        return

    v_data = verification.get_verification(target_user_id)
    if not v_data:
        await query.answer("❌ Verification expired or not found.", show_alert=True)
        return

    time_taken = time.time() - v_data['time']
    correct_answer = v_data['correct']
    
    verification.clear_verification(target_user_id)
    
    # --- RULE 1: Anti-Bot Check (< 1 second) ---
    if time_taken < 1.0:
        await query.answer("🤖 Bot detected! You clicked too fast.", show_alert=True)
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
            
            # 2. Mark as verified in DB
            session = Session()
            db_user = session.query(User).filter_by(id=target_user_id).first()
            if not db_user:
                db_user = User(id=clicker.id, username=clicker.username, full_name=clicker.first_name, is_verified=True)
                session.add(db_user)
            else:
                db_user.is_verified = True
            
            # Fetch Custom Welcome Config
            config = session.query(WelcomeConfig).filter_by(id=1).first()
            session.commit()
            session.close()

            # 3. Clean up the Captcha Message
            await query.answer("✅ Verification successful! You can now chat.", show_alert=True)
            await query.message.delete()
            
            # --- NEW: 4. Send the Grand Personalized Welcome Message ---
            base_text = config.text if config and config.text else "🎉 Welcome to the group, {user}!"
            final_text = base_text.replace("{user}", clicker.mention_html())

            keyboard = []
            if config and config.buttons:
                for btn in config.buttons:
                    keyboard.append([InlineKeyboardButton(btn[0], url=btn[1])])
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            # Send Media/Text
            if config and config.media_file_id:
                if config.media_type == 'photo':
                    await context.bot.send_photo(chat_id=chat.id, photo=config.media_file_id, caption=final_text, reply_markup=reply_markup, parse_mode='HTML')
                elif config.media_type == 'video':
                    await context.bot.send_video(chat_id=chat.id, video=config.media_file_id, caption=final_text, reply_markup=reply_markup, parse_mode='HTML')
                elif config.media_type == 'animation':
                    await context.bot.send_animation(chat_id=chat.id, animation=config.media_file_id, caption=final_text, reply_markup=reply_markup, parse_mode='HTML')
            else:
                await context.bot.send_message(chat_id=chat.id, text=final_text, reply_markup=reply_markup, parse_mode='HTML')

        except Exception as e:
            print(f"Unrestrict/Welcome failed: {e}")
    else:
        await query.answer("❌ Wrong answer!", show_alert=True)
        try:
            await chat.ban_member(target_user_id)
            await chat.unban_member(target_user_id)
            await query.message.delete()
        except Exception as e:
            print(f"Kick failed: {e}")