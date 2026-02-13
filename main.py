# main.py
import logging
import config
from database import init_db
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from handlers import moderation, economy, admin,admin_products, redemption, admin_filter

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
    
    # Admin Handerls
    application.add_handler(admin_products.conv_handler) # /add_product (Wizard)
    application.add_handler(CommandHandler("admin", admin.admin_panel))
    application.add_handler(CallbackQueryHandler(admin.admin_callback, pattern="^admin_"))

    # Filter Management (Private Chat)
    application.add_handler(CommandHandler("add_word", admin_filter.add_word_command))
    application.add_handler(CommandHandler("del_word", admin_filter.del_word_command))
    application.add_handler(CommandHandler("list_words", admin_filter.list_words_command))

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