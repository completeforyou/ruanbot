# main.py
import logging
import config
from database import init_db
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from handlers import moderation, economy, admin,admin_products, redemption, verification, admin_welcome
from services.antispam import cleanup_cache

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

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

    # --- BACKGROUND JOBS (Janitor) ---
    # Run every 60 minutes (3600 seconds)
    application.job_queue.run_repeating(cleanup_cache, interval=3600, first=3600)
    
    # --- Register Handlers ---
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, verification.welcome_new_member))
    application.add_handler(CallbackQueryHandler(verification.verify_button_click, pattern="^verify_"))
    # Admin Handerls
    application.add_handler(admin_welcome.welcome_conv_handler)
    application.add_handler(admin_products.conv_handler)
    application.add_handler(admin_products.conv_handler) # /add_product (Wizard)
    application.add_handler(CommandHandler("admin", admin.admin_panel))
    application.add_handler(CallbackQueryHandler(admin.admin_callback, pattern="^admin_"))

    # Redemption Commands
    application.add_handler(CommandHandler("lottery", redemption.list_products)) # Shows the list
    application.add_handler(CallbackQueryHandler(redemption.handle_draw, pattern="^draw_")) # Handles the button

    # Economy Commands
    application.add_handler(MessageHandler(filters.Regex(r'^积分$'), economy.check_balance))
    
    # Global Message Handler (Must be last)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), global_message_handler))
    # Also handle Captions (Photos with text) for filtering
    application.add_handler(MessageHandler(filters.CAPTION, global_message_handler))
    
    print("Bot is running...")
    application.run_polling()