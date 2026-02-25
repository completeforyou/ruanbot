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
import asyncio

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

async def main():
    """The new async boot sequence for Webhooks."""
    print("Initializing Database...")
    await init_db()
    print("Database Initialized!")

    if not config.TOKEN:
        print("Error: TOKEN not found in config.py")
        exit(1)

    req = HTTPXRequest(connection_pool_size=32, read_timeout=60, connect_timeout=60)
    application = ApplicationBuilder().token(config.TOKEN).request(req).build()

    # Setup Scheduled Jobs
    application.job_queue.run_repeating(cleanup_cache, interval=120, first=120)
    application.job_queue.run_daily(economy_service.reset_daily_msg_counts, time=time(hour=16, minute=0))

    # Register Handlers
    application.add_handler(MessageHandler(filters.ALL, priority_spam_check), group=-1)
    register_handlers(application)
    application.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), global_message_handler))

    # --- THE WEBHOOK ARCHITECTURE ---
    # This block safely initializes, starts, and eventually stops the bot
    async with application:
        await application.start()
        
        # 1. Tell Telegram where to push new messages
        # IMPORTANT: Replace the URL below with your ACTUAL Railway URL
        BASE_URL = "https://ruanbot-production.up.railway.app"
        webhook_url = f"{BASE_URL}/webhook_{config.TOKEN}"
        
        await application.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
        print(f"🔗 Webhook securely set to: {BASE_URL}/webhook_***")

        # 2. Start our aiohttp web server to listen for those messages
        await start_web_server(application)
        
        print("🟢 Bot is running in Webhook mode! CPU usage will now rest at 0%.")
        
        # 3. Keep the program running forever
        stop_signal = asyncio.Event()
        await stop_signal.wait()

if __name__ == '__main__':
    # Run the async main loop
    asyncio.run(main())