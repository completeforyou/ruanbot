# handlers/admin.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from utils.decorators import admin_only, private_chat_only
from services import economy
from database import Session, SystemConfig, Product

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
    # REMOVED USER MGMT
    keyboard = [
        [
            InlineKeyboardButton("🏪 Shop & Lottery", callback_data="admin_shop_menu"),
            InlineKeyboardButton("🎟 Vouchers", callback_data="admin_voucher_menu")
        ],
        [
            InlineKeyboardButton("⚙️ System Config", callback_data="admin_config_menu")
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
    
    if data == "admin_home":
        await admin_panel(update, context)
    elif data == "admin_close":
        await query.message.delete()
    elif data == "admin_shop_menu":
        await show_shop_menu(update)
    elif data == "admin_voucher_menu":
        await show_voucher_menu(update)
    elif data == "admin_config_menu":
        await show_config_menu(update)
    elif data == "admin_toggle_voucher":
        current = economy.is_voucher_buy_enabled()
        economy.set_voucher_buy_status(not current)
        await show_voucher_menu(update)

# --- SUB-MENUS ---

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
    is_enabled = economy.is_voucher_buy_enabled()
    current_cost = economy.get_voucher_cost()
    status_icon = "✅ ON" if is_enabled else "🔴 OFF"
    toggle_btn_text = "Disable Buying" if is_enabled else "Enable Buying"
    
    text = (
        f"🎟 **Voucher Settings**\n"
        f"🛒 Purchase Status: **{status_icon}**\n"
        f"💰 Cost: `{current_cost} Points`\n\n"
        "Controls:"
    )
    keyboard = [
        [InlineKeyboardButton("💲 Set Cost", callback_data="admin_set_vcost")],
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
    )
    keyboard = [
        [InlineKeyboardButton("✏️ Edit Points", callback_data="admin_set_cpts"),
         InlineKeyboardButton("✏️ Edit Limit", callback_data="admin_set_clim")],
        [InlineKeyboardButton("📝 Edit Welcome Msg", callback_data="admin_welcome_set")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_home")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# --- SETTINGS WIZARD (ConversationHandler) ---
WAIT_INPUT = 1

async def start_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    setting_map = {
        "admin_set_vcost": ("Voucher Cost", "integer"),
        "admin_set_cpts": ("Check-in Points", "float"),
        "admin_set_clim": ("Check-in Daily Limit", "integer"),
    }
    
    s_type = query.data
    name, dtype = setting_map.get(s_type, ("Unknown", "string"))
    
    context.user_data['setting_type'] = s_type
    context.user_data['setting_dtype'] = dtype
    
    kb = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel_op")]]
    
    await query.edit_message_text(
        f"✏️ **Setting: {name}**\n\n"
        f"Please enter the new value:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode='Markdown'
    )
    return WAIT_INPUT

async def save_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    s_type = context.user_data.get('setting_type')
    dtype = context.user_data.get('setting_dtype')
    
    try:
        if dtype == 'integer':
            val = int(text)
        else:
            val = float(text)
            
        # Save to DB
        if s_type == "admin_set_vcost":
            economy.set_voucher_cost(val)
        elif s_type in ["admin_set_cpts", "admin_set_clim"]:
            # Need to fetch current other value to not overwrite it with default
            session = Session()
            config = session.query(SystemConfig).filter_by(id=1).first()
            c_pts = config.check_in_points if config else 10.0
            c_lim = config.check_in_limit if config else 1
            session.close()
            
            if s_type == "admin_set_cpts":
                economy.set_check_in_config(val, c_lim)
            else:
                economy.set_check_in_config(c_pts, val)
                
        await update.message.reply_text("✅ **Setting Updated!**", parse_mode='Markdown')
        
        # Return to menu prompt (Admin can click /admin or buttons)
        await update.message.reply_text("Type /admin to return to panel.")
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Invalid format. Please enter a number.")
        return WAIT_INPUT

async def cancel_op(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Cancelled")
    await update.callback_query.edit_message_text("🚫 Operation Cancelled.")
    return ConversationHandler.END

@admin_only
async def give_voucher_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /give <amount> (Reply to user)
    OR
    /give <user_id> <amount>
    """
    args = context.args
    target_id = None
    amount = None

    # Case 1: Reply to a message
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        try: 
            amount = int(args[0])
        except: 
            pass
            
    # Case 2: ID and Amount arguments
    elif len(args) >= 2:
        try:
            if args[0].isdigit(): 
                target_id = int(args[0])
            else: 
                # Resolving username requires database lookup or cache, 
                # but ID is safer/easier for this scope.
                await update.message.reply_text("⚠️ Please reply to a message or use User ID.")
                return
            amount = int(args[1])
        except: 
            pass
    
    if target_id and amount:
        economy.add_vouchers(target_id, amount)
        await update.message.reply_text(f"✅ Gave **{amount}** vouchers to ID `{target_id}`", parse_mode='Markdown')
    else:
        await update.message.reply_text(
            "usage:\n"
            "1. Reply to user: `/give <amount>`\n"
            "2. By ID: `/give <user_id> <amount>`", 
            parse_mode='Markdown'
        )

# Export the handler
settings_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_setting, pattern="^admin_set_(vcost|cpts|clim)$")
    ],
    states={
        WAIT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_setting)]
    },
    fallbacks=[
        CallbackQueryHandler(cancel_op, pattern="^admin_cancel_op$"),
        MessageHandler(filters.COMMAND, cancel_op)
    ]
)