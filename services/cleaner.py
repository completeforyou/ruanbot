# ruanbot/services/cleaner.py
from telegram import Update
from telegram.ext import ContextTypes
from services import economy

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    """The job that runs after X seconds to delete the message."""
    job = context.job
    chat_id = job.data['chat_id']
    message_id = job.data['message_id']
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        # Message might already be deleted or bot lacks permissions
        pass

async def schedule_media_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks config and schedules deletion if enabled."""
    if not update.message:
        return

    # 1. Check if the message has media
    msg = update.message
    has_media = (
        msg.photo or 
        msg.video or 
        msg.animation or 
        msg.document or   
        msg.video_note
    )

    if not has_media:
        return

    # 2. Get Config
    config = economy.get_system_config()
    delay = config.get('media_delete_time', 0)

    # 3. Schedule Job (Only if delay > 0)
    if delay > 0:
        context.job_queue.run_once(
            delete_message_job,
            when=delay,
            data={'chat_id': msg.chat_id, 'message_id': msg.message_id},
            name=f"del_{msg.chat_id}_{msg.message_id}"
        )