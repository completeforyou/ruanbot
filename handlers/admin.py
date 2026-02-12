# handlers/admin.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.decorators import admin_only, private_chat_only  # Import decorators

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