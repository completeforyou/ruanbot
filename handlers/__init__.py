# handlers/__init__.py
from telegram.ext import MessageHandler, CommandHandler, CallbackQueryHandler, filters
from . import moderation, economy, admin, admin_products, redemption, verification, admin_welcome, shop, scratchers

def register_handlers(application):
    """
    Registers all bot handlers in the correct priority order.
    """
    # 1. Verification & Welcome (High Priority)
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, verification.welcome_new_member))
    application.add_handler(CallbackQueryHandler(verification.verify_button_click, pattern="^verify_"))
    
    # 2. Admin Wizards (Conversation Handlers)
    application.add_handler(admin_welcome.welcome_conv_handler)
    application.add_handler(admin_products.conv_handler)
    application.add_handler(admin.settings_conv_handler)
    
    # 3. Admin Panel & Commands
    application.add_handler(CommandHandler("admin", admin.admin_panel))
    application.add_handler(CommandHandler("give", admin.give_voucher_command))
    
    # --- ADMIN CALLBACK ROUTING ---
    # FIX: Specific handlers must be registered BEFORE the generic 'admin_' catch-all
    application.add_handler(CallbackQueryHandler(admin_products.handle_remove_product, pattern="^admin_delete_prod_"))
    application.add_handler(CallbackQueryHandler(admin.admin_callback, pattern="^admin_"))

    # 4. Economy & Games
    application.add_handler(MessageHandler(filters.Regex(r'^积分$'), economy.check_balance))
    application.add_handler(MessageHandler(filters.Regex(r'(?i)^(签到|checkin)$'), economy.handle_check_in_request))
    application.add_handler(MessageHandler(filters.Regex(r'^抽奖$'), redemption.open_lottery_menu))
    application.add_handler(MessageHandler(filters.Regex(r'^商店$'), shop.open_shop_menu))
    application.add_handler(MessageHandler(filters.Regex(r'^刮刮乐$'), scratchers.open_scratcher_menu))

    application.add_handler(CallbackQueryHandler(redemption.handle_lottery_draw, pattern="^lottery_draw_"))
    application.add_handler(CallbackQueryHandler(shop.handle_shop_buy, pattern="^shop_buy"))
    application.add_handler(CallbackQueryHandler(scratchers.handle_scratcher_play, pattern="^scratcher_play_"))
