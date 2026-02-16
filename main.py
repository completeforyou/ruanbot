# main.py
import logging
import config
from database import init_db
from telegram.ext import ApplicationBuilder, MessageHandler, filters
from telegram.request import HTTPXRequest
from handlers import register_handlers
from handlers import moderation, economy
from services.antispam import cleanup_cache

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

async def global_message_handler(update, context):
    is_spam = await moderation.check_spam(update, context)
    if is_spam:
        return 
    await economy.track_activity(update, context)

if __name__ == '__main__':
    # Initialize Database
    init_db()
    
    if not config.TOKEN:
        print("Error: TOKEN not found in config.py")
        exit(1)
    req = HTTPXRequest(connection_pool_size=8, read_timeout=60, connect_timeout=60)
    application = ApplicationBuilder().token(config.TOKEN).request(req).build()

    application.job_queue.run_repeating(cleanup_cache, interval=3600, first=3600)
    
    # --- Register Handlers ---
    register_handlers(application)
    
    # Global Message Handler
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), global_message_handler))
    application.add_handler(MessageHandler(filters.CAPTION, global_message_handler))
    
    print("Bot is running...")
    application.run_polling()