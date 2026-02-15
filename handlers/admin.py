# handlers/admin.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.decorators import admin_only, private_chat_only  # Import decorators
from database import Session, User
from services import economy

@admin_only
@private_chat_only
def get_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🛍 Manage Products", callback_data="admin_menu_products"),
            InlineKeyboardButton("👋 Welcome Setup", callback_data="admin_menu_welcome")
        ],
        [
            InlineKeyboardButton("🛡 Moderation", callback_data="admin_menu_mod"),
            InlineKeyboardButton("⚙️ Bot Settings", callback_data="admin_menu_settings")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_products_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add New Product", callback_data="admin_prod_add")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="admin_back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

@admin_only
@private_chat_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: /admin"""
    await update.message.reply_text(
        "👑 **Admin Dashboard**\nSelect a module to configure:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode='Markdown'
    )

async def admin_navigator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks to switch menus (Navigation)"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "admin_back_main":
        await query.edit_message_text(
            "👑 **Admin Dashboard**\nSelect a module to configure:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
        
    elif data == "admin_menu_products":
        await query.edit_message_text(
            "🛍 **Product Management**\nAdd or remove items for the lottery.",
            reply_markup=get_products_keyboard(),
            parse_mode='Markdown'
        )
        
    elif data == "admin_menu_welcome":
        # We instruct them to use the command or trigger the wizard directly
        # For simplicity, let's just show info, or you can trigger the wizard (advanced)
        await query.edit_message_text(
            "👋 **Welcome Config**\n\nTo change the welcome message, click below to start the wizard.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✨ Start Setup Wizard", callback_data="admin_welcome_start"),
                InlineKeyboardButton("🔙 Back", callback_data="admin_back_main")
            ]]),
            parse_mode='Markdown'
        )
        
    elif data == "admin_close":
        await query.delete_message()


@admin_only
async def give_voucher_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage:
    1. Reply to user: /give_voucher <amount>
    2. Mention user:  /give_voucher @username <amount>
    3. User ID:       /give_voucher <user_id> <amount>
    """
    args = context.args
    target_id = None
    amount = None

    # Scenario 1: Reply to a message
    if update.message.reply_to_message:
        try:
            target_id = update.message.reply_to_message.from_user.id
            amount = int(args[0])
        except (IndexError, ValueError):
            await update.message.reply_text("⚠️ Usage (Reply): `/give <amount>`", parse_mode='Markdown')
            return

    # Scenario 2 & 3: Arguments provided
    elif len(args) >= 2:
        identifier = args[0]
        try:
            amount = int(args[1])
        except ValueError:
            await update.message.reply_text("❌ Amount must be a number.", parse_mode='Markdown')
            return

        # Check if it's a @username
        if identifier.startswith("@"):
            username = identifier[1:] # Strip the '@'
            session = Session()
            user = session.query(User).filter(User.username.ilike(username)).first() # Case-insensitive search
            session.close()
            
            if user:
                target_id = user.id
            else:
                await update.message.reply_text(f"❌ User `@{username}` not found in database.\n(They must interact with the bot first).", parse_mode='Markdown')
                return
        # Assume it's an ID
        elif identifier.isdigit():
            target_id = int(identifier)
        else:
            await update.message.reply_text("❌ Invalid user. Use @username or ID.")
            return
            
    else:
        await update.message.reply_text(
            "⚠️ **Usage Options:**\n"
            "1. Reply to msg: `/give_voucher 5`\n"
            "2. By Username: `/give_voucher @username 5`\n"
            "3. By ID: `/give_voucher 123456 5`",
            parse_mode='Markdown'
        )
        return

    # Execute the transaction
    if target_id and amount:
        economy.add_vouchers(target_id, amount)
        
        # Try to get the user's name for the success message
        session = Session()
        user_db = session.query(User).filter_by(id=target_id).first()
        name = user_db.full_name if user_db else f"ID {target_id}"
        session.close()

        await update.message.reply_text(f"✅ 恭喜 {name} 获得 {amount} 张兑奖券！", parse_mode='Markdown')
@admin_only
@private_chat_only
async def set_checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: `/set_checkin <points> <limit>`\nExample: `/set_checkin 50 1`", parse_mode='Markdown')
        return
        
    try:
        points = float(context.args[0])
        limit = int(context.args[1])
        
        economy.set_check_in_config(points, limit)
        await update.message.reply_text(f"✅ **Check-in Updated!**\n💰 Points: {points}\n📅 Daily Limit: {limit}", parse_mode='Markdown')
        
    except ValueError:
        await update.message.reply_text("❌ Points must be a number and Limit must be an integer.")