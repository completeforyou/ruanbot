# handlers/verification.py
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import ContextTypes
from services import verification
from database import Session, User

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when a new user joins the group."""
    chat = update.effective_chat
    
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        
        # 1. Restrict the user immediately
        try:
            await chat.restrict_member(
                member.id,
                permissions=ChatPermissions(can_send_messages=False)
            )
        except Exception as e:
            print(f"Failed to restrict member: {e}")
            continue

        # 2. Generate the Math Challenge
        question_text, answers = verification.generate_math_question(member.id)

        # 3. Build the Inline Buttons
        keyboard = []
        row = []
        for ans in answers:
            row.append(InlineKeyboardButton(str(ans), callback_data=f"verify_{member.id}_{ans}"))
            if len(row) == 2: 
                keyboard.append(row)
                row = []
        if row: keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 4. Send the Verification Message AND save the message object
        captcha_msg = await context.bot.send_message(
            chat_id=chat.id,
            text=f"👋 Welcome {member.mention_html()}!\n\n"
                 f"🛡 **Verification Required**\n"
                 f"You have 3 minutes to solve this math problem to prove you are human:\n\n"
                 f"**{question_text}**",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

        # --- NEW: 5. Start the 3-Minute Timeout Timer ---
        async def timeout_kick(chat_id, user_id, message_id):
            await asyncio.sleep(180) # Wait for 3 minutes (180 seconds)
            
            # Wake up and check if the user is STILL in the pending list
            if verification.get_verification(user_id):
                print(f"User {user_id} timed out on captcha. Kicking...")
                # Remove them from the list
                verification.clear_verification(user_id)
                
                try:
                    # Kick the user (ban then unban)
                    await context.bot.ban_chat_member(chat_id, user_id)
                    await context.bot.unban_chat_member(chat_id, user_id)
                    # Delete the unanswered captcha message to keep chat clean
                    await context.bot.delete_message(chat_id, message_id)
                except Exception as e:
                    print(f"Timeout cleanup failed: {e}")

        # Run the timer in the background so the bot doesn't freeze
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
    
    # Remove from pending (this tells the 3-minute timer to safely do nothing when it wakes up!)
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
            # Unmute user
            await chat.restrict_member(
                target_user_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            
            # Mark as verified in DB
            session = Session()
            db_user = session.query(User).filter_by(id=target_user_id).first()
            if not db_user:
                db_user = User(id=clicker.id, username=clicker.username, full_name=clicker.first_name, is_verified=True)
                session.add(db_user)
            else:
                db_user.is_verified = True
            session.commit()
            session.close()

            await query.answer("✅ Verification successful! You can now chat.", show_alert=True)
            await query.message.delete()
            
        except Exception as e:
            print(f"Unrestrict failed: {e}")
    else:
        await query.answer("❌ Wrong answer!", show_alert=True)
        try:
            await chat.ban_member(target_user_id)
            await query.message.delete()
        except Exception as e:
            print(f"Kick failed: {e}")