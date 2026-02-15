# handlers/admin.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from utils.decorators import admin_only, private_chat_only
from services import economy
from database import Session, SystemConfig, User, Product

# --- MAIN PANEL ---
@admin_only
@private_chat_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Entry point: /admin
    """
    text = (
        "👑 **Admin Control Panel**\n"
        "Select a module to manage:"
    )
    keyboard = [
        [
            InlineKeyboardButton("🏪 Shop & Lottery", callback_data="admin_shop_menu"),
            InlineKeyboardButton("🎟 Vouchers", callback_data="admin_voucher_menu")
        ],
        [
            InlineKeyboardButton("⚙️ System Config", callback_data="admin_config_menu"),
            InlineKeyboardButton("👥 User Mgmt", callback_data="admin_users_menu")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="admin_close")
        ]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- CALLBACK DISPATCHER ---
@admin_only
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    # 1. Navigation
    if data == "admin_home":
        await admin_panel(update, context)
        return
    elif data == "admin_close":
        await query.message.delete()
        return

    # 2. Sub-Menus
    if data == "admin_shop_menu":
        await show_shop_menu(update)
    elif data == "admin_voucher_menu":
        await show_voucher_menu(update)
    elif data == "admin_config_menu":
        await show_config_menu(update)
    elif data == "admin_users_menu":
        await show_users_menu(update)
        
    # 3. Actions
    elif data == "admin_toggle_voucher":
        # Toggle and refresh
        current = economy.is_voucher_buy_enabled()
        economy.set_voucher_buy_status(not current)
        await show_voucher_menu(update) # Refresh UI

# --- SUB-MENU FUNCTIONS ---

async def show_shop_menu(update: Update):
    session = Session()
    prod_count = session.query(Product).count()
    session.close()

    text = (
        f"🏪 **Shop Management**\n"
        f"📦 Total Products: `{prod_count}`\n\n"
        "Select an action:"
    )
    keyboard = [
        [InlineKeyboardButton("➕ Add New Product", callback_data="admin_prod_add")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_home")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_voucher_menu(update: Update):
    # Check Status
    is_enabled = economy.is_voucher_buy_enabled()
    status_icon = "✅ ON" if is_enabled else "🔴 OFF"
    toggle_btn_text = "Disable Buying" if is_enabled else "Enable Buying"
    
    text = (
        f"🎟 **Voucher Settings**\n"
        f"🛒 Purchase Status: **{status_icon}**\n\n"
        "Controls:"
    )
    keyboard = [
        [InlineKeyboardButton(toggle_btn_text, callback_data="admin_toggle_voucher")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_home")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_config_menu(update: Update):
    session = Session()
    config = session.query(SystemConfig).filter_by(id=1).first()
    pts = config.check_in_points if config else 10.0
    limit = config.check_in_limit if config else 1
    session.close()

    text = (
        f"⚙️ **System Configuration**\n\n"
        f"📅 **Check-in Rewards**\n"
        f"• Points: `{pts}`\n"
        f"• Daily Limit: `{limit}`\n\n"
        f"📝 **Welcome Message**\n"
        f"• Click below to set media/text.\n"
    )
    keyboard = [
        # Note: We can add a button to trigger a conversation for check-in later
        [InlineKeyboardButton("📝 Edit Welcome Msg", callback_data="admin_welcome_set")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_home")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_users_menu(update: Update):
    text = (
        "👥 **User Management**\n\n"
        "To give vouchers, use commands (easier for specific IDs):\n"
        "`/give @username 5`\n"
        "`/give 123456789 5`"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_home")]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- EXISTING COMMANDS (Keep these for manual use) ---
@admin_only
async def give_voucher_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Keep previous logic for /give command) ...
    pass 
    # NOTE: You can paste the original give_voucher_command logic here if you want to keep the command active.
    # For brevity, I assume you kept the logic from the previous file or I can repost it if needed.
    
    # RE-PASTING logic for safety:
    args = context.args
    target_id = None
    amount = None

    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        try: amount = int(args[0])
        except: pass
    elif len(args) >= 2:
        try:
            if args[0].isdigit(): target_id = int(args[0])
            else: 
                # resolving username is hard without cache, usually better to reply
                await update.message.reply_text("⚠️ Please reply to a message or use User ID.")
                return
            amount = int(args[1])
        except: pass
    
    if target_id and amount:
        economy.add_vouchers(target_id, amount)
        await update.message.reply_text(f"✅ Gave {amount} vouchers to ID {target_id}")
    else:
        await update.message.reply_text("Usage: `/give <amount>` (Reply to user)", parse_mode='Markdown')

@admin_only
async def set_checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Keep previous logic) ...
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/set_checkin 50 1`")
        return
    try:
        economy.set_check_in_config(float(context.args[0]), int(context.args[1]))
        await update.message.reply_text("✅ Check-in Updated!")
    except:
        await update.message.reply_text("❌ Error.")