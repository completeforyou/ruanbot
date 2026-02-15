import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    filters
)
from telegram.request import HTTPXRequest

# --- Config & Database ---
import config
from database import init_db

# --- Services ---
from services.antispam import cleanup_cache
from services import economy

# --- Handlers ---
from handlers import (
    admin, 
    admin_products, 
    admin_welcome, 
    verification, 
    redemption, 
    shop, 
    moderation
)

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

async def global_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Runs on every text message to check for spam and award activity points.
    """
    # 1. Security & Spam Check (Stops processing if spam detected)
    if await moderation.check_spam(update, context):
        return 
    
    # 2. Track Activity (Award Points)
    await economy.track_activity(update, context)

if __name__ == '__main__':
    # 1. Initialize Database (Create tables & migrate columns)
    init_db()
    
    # 2. Configure Robust Network Settings
    # Prevents "Server disconnected" and "Timeout" errors
    req = HTTPXRequest(connection_pool_size=8, read_timeout=60, connect_timeout=60)
    
    # 3. Build Application
    app = ApplicationBuilder().token(config.TOKEN).request(req).build()
    
    # --- BACKGROUND JOBS ---
    # Runs every 60 mins to clean old spam/verification data from RAM
    app.job_queue.run_repeating(cleanup_cache, interval=3600, first=3600)

    # --- HANDLERS ---
    
    # A. Wizards (ConversationHandlers must be added first)
    app.add_handler(admin_products.conv_handler)
    app.add_handler(admin_welcome.welcome_conv_handler)
    
    # B. Admin Dashboard & Commands
    app.add_handler(CommandHandler("admin", admin.admin_panel))
    app.add_handler(CallbackQueryHandler(admin.admin_navigator, pattern="^admin_"))
    
    # Admin Tools
    app.add_handler(CommandHandler("give_voucher", admin.give_voucher_command))
    app.add_handler(CommandHandler("set_checkin", admin.set_checkin_command))
    app.add_handler(CommandHandler("toggle_voucher_buy", admin.toggle_voucher_buy_command))
    
    # C. Verification (New Members)
    app.add_handler(verification.welcome_new_member_handler)
    app.add_handler(CallbackQueryHandler(verification.verify_button_click, pattern=r"^verify_"))

    # D. Features (Shop, Lottery, Check-in)
    app.add_handler(CommandHandler("start", verification.start_command))
    app.add_handler(CommandHandler("lottery", redemption.open_lottery_menu))
    app.add_handler(CommandHandler("shop", shop.open_shop_menu))
    
    # Feature Callbacks (Buttons)
    app.add_handler(CallbackQueryHandler(redemption.handle_lottery_draw, pattern="^lottery_draw_"))
    app.add_handler(CallbackQueryHandler(shop.handle_shop_buy, pattern="^shop_buy"))

    # E. Message Triggers (Regex)
    # Check-in: "签到" or "checkin" (Case insensitive)
    app.add_handler(MessageHandler(filters.Regex(r'(?i)^(签到|checkin)$'), economy.handle_check_in_request))
    
    # Balance: "积分" or "Points"
    app.add_handler(MessageHandler(filters.Regex(r'(?i)^(积分|points)$'), economy.check_balance))

    # F. Global Message Handler (Spam & Activity Tracking)
    # Must be last to catch all other text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, global_message_handler))

    # --- RUN BOT ---
    print("🚀 Bot is running...")
    app.run_polling()