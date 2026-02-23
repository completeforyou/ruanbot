# main.py
import logging
import config
from database import init_db
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ApplicationHandlerStop
from telegram.request import HTTPXRequest
from handlers import register_handlers
from handlers import moderation, economy as economy_handler
from services.antispam import cleanup_cache
from services import cleaner, economy as economy_service
from datetime import time
from webapp_server import start_web_server
import aiohttp
import os

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

async def global_message_handler(update, context):
    
    await economy_handler.track_activity(update, context)
    
    await cleaner.schedule_media_deletion(update, context)

async def priority_spam_check(update: Update, context):
    is_spam = await moderation.check_spam(update, context)
    if is_spam:
        raise ApplicationHandlerStop # Stop processing this update immediately

async def keep_webapp_warm(context):
    """Pings the web app's API every 10 minutes to keep the DB connection and Railway router awake."""
    port = os.getenv("PORT", 8080)
    url = f"http://127.0.0.1:{port}/api/wheel_data"
    
    try:
        # We use aiohttp to make a quick invisible request to our own server
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                pass # We don't care about the result, we just wanted to wake it up!
    except Exception as e:
        pass # Ignore errors, this is just a background heartbeat

async def post_init(application):
    """Runs asynchronously before the bot starts polling."""
    print("Initializing Database...")
    await init_db()
    print("Database Initialized!")
    print("Starting Web Server...")
    await start_web_server(application.bot)

if __name__ == '__main__':
    # Initialize Database    
    if not config.TOKEN:
        print("Error: TOKEN not found in config.py")
        exit(1)
    req = HTTPXRequest(connection_pool_size=8, read_timeout=60, connect_timeout=60)
    application = ApplicationBuilder().token(config.TOKEN).request(req).post_init(post_init).build()

    application.job_queue.run_repeating(cleanup_cache, interval=3600, first=3600)

    application.job_queue.run_daily(economy_service.reset_daily_msg_counts, time=time(hour=16, minute=0))

    application.job_queue.run_repeating(keep_webapp_warm, interval=600, first=10)

    application.add_handler(MessageHandler(filters.ALL, priority_spam_check), group=-1)
    
    # --- Register Handlers ---
    register_handlers(application)
    
    # Global Message Handler
    application.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), global_message_handler))
    
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)