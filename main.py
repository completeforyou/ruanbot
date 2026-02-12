# main.py
import logging
import config
from database import init_db
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from handlers import moderation, economy, admin

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def global_message_handler(update, context):
    """
    The Pipeline:
    1. Check Spam -> If spam, stop.
    2. Track Activity -> If safe, award points.
    """
    # Step 1: Moderation
    is_spam = await moderation.check_spam(update, context)
    if is_spam:
        return 
        
    # Step 2: Economy
    await economy.track_activity(update, context)

if __name__ == '__main__':
    # Initialize Database
    init_db()
    
    if not config.TOKEN:
        print("Error: TOKEN not found in config.py")
        exit(1)

    # Build App
    application = ApplicationBuilder().token(config.TOKEN).build()
    
    # --- Register Handlers ---
    
    # Admin Commands
    application.add_handler(CommandHandler("admin", admin.admin_panel))
    application.add_handler(CallbackQueryHandler(admin.admin_callback, pattern="^admin_"))

    # Economy Commands
    application.add_handler(MessageHandler(filters.Regex(r'^积分$'), economy.check_balance))
    
    # Global Message Handler (Must be last)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), global_message_handler))
    
    print("Bot is running...")
    application.run_polling()