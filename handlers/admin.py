# handlers/admin.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.decorators import admin_only, private_chat_only  # Import decorators
from database import Session, User
from services import economy

@admin_only           # Security Check 1: Must be Bot Admin
@private_chat_only    # Security Check 2: Must be in DM (optional, prevents clutter)
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Opens the Admin Control Panel.
    """
    keyboard = [
        [
            InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
            InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="admin_close"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("👑 **Admin Panel**", reply_markup=reply_markup, parse_mode='Markdown')

# Note: Callbacks also need protection if you want to be extra safe!
@admin_only
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_stats":
        await query.edit_message_text("📊 Stats feature coming soon!")
    elif query.data == "admin_settings":
        await query.edit_message_text("⚙️ Settings feature coming soon!")
    elif query.data == "admin_close":
        await query.delete_message()

@admin_only
async def give_voucher_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: `/give_voucher <user_id> <amount>`", parse_mode='Markdown')
        return
        
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        
        economy.add_vouchers(target_id, amount)
        await update.message.reply_text(f"✅ Added **{amount} Vouchers** to User ID `{target_id}`.", parse_mode='Markdown')
        
    except ValueError:
        await update.message.reply_text("❌ IDs and Amounts must be numbers.")