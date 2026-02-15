# main.py
import logging
import config
from database import init_db
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from handlers import moderation, economy, admin, admin_products, redemption, verification, admin_welcome, shop, games
from services.antispam import cleanup_cache
from telegram.request import HTTPXRequest

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
    req = HTTPXRequest(connection_pool_size=8, read_timeout=60, connect_timeout=60)
    # Build App
    application = ApplicationBuilder().token(config.TOKEN).request(req).build()

    # --- BACKGROUND JOBS ---
    # Run every 60 minutes
    application.job_queue.run_repeating(cleanup_cache, interval=3600, first=3600)
    # Run verification cleanup every 60 seconds (Fixes the zombie user issue)
    application.job_queue.run_repeating(verification.cleanup_pending_users, interval=60, first=10)
    
    # --- Register Handlers ---
    
    # 1. Verification & Welcome
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, verification.welcome_new_member))
    application.add_handler(CallbackQueryHandler(verification.verify_button_click, pattern="^verify_"))
    
    # 2. Admin Wizards (Must be before generic admin callback)
    # Triggers: /set_welcome OR Button "admin_welcome_set"
    application.add_handler(admin_welcome.welcome_conv_handler)
    # Triggers: /add OR Button "admin_prod_add"
    application.add_handler(admin_products.conv_handler) 
    
    # 3. Admin Panel & Commands
    application.add_handler(CommandHandler("admin", admin.admin_panel))
    application.add_handler(CommandHandler("give", admin.give_voucher_command))
    application.add_handler(CommandHandler("set_checkin", admin.set_checkin_command))
    # Note: toggle_voucher is REMOVED because it's in the panel now.
    
    # Generic Admin Callback (Handles navigation buttons)
    application.add_handler(CallbackQueryHandler(admin.admin_callback, pattern="^admin_"))

    # 4. Economy & Games
    application.add_handler(MessageHandler(filters.Regex(r'^积分$'), economy.check_balance))
    application.add_handler(MessageHandler(filters.Regex(r'(?i)^(签到|checkin)$'), economy.handle_check_in_request))
    application.add_handler(CommandHandler("lottery", redemption.open_lottery_menu))
    application.add_handler(CommandHandler("shop", shop.open_shop_menu))
    application.add_handler(CommandHandler("bet", games.dice_gamble)) # New Dice Game

    application.add_handler(CallbackQueryHandler(redemption.handle_lottery_draw, pattern="^lottery_draw_"))
    application.add_handler(CallbackQueryHandler(shop.handle_shop_buy, pattern="^shop_buy")) 
    
    # 5. Global Message Handler (Must be last)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), global_message_handler))
    # Also handle Captions (Photos with text) for filtering
    application.add_handler(MessageHandler(filters.CAPTION, global_message_handler))
    
    print("Bot is running...")
    application.run_polling()