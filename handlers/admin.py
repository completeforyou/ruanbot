# handlers/admin.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from utils.decorators import admin_only, private_chat_only
from services import economy
from database import Session, SystemConfig, Product
from handlers import admin_products

# --- MAIN PANEL ---
@admin_only
@private_chat_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Entry point: /admin
    """
    text = (
        "👑 控制面板\n"
        "选择模块:"
    )
    keyboard = [
        [
            InlineKeyboardButton("🏪 商城 & 刮刮乐", callback_data="admin_shop_menu"),
            InlineKeyboardButton("🎟 兑奖券", callback_data="admin_voucher_menu")
        ],
        [
            InlineKeyboardButton("⚙️ 系统设置", callback_data="admin_config_menu")
        ],
        [
            InlineKeyboardButton("❌ 关闭", callback_data="admin_close")
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
    elif data == "admin_prod_remove":
        await admin_products.start_remove_product(update, context)

# --- SUB-MENUS ---

async def show_shop_menu(update: Update):
    session = Session()
    prod_count = session.query(Product).count()
    session.close()

    text = (
        f"🏪 商城管理\n"
        f"📦 总共商品: `{prod_count}`\n\n"
        "操作:"
    )
    keyboard = [
        [InlineKeyboardButton("➕ 新增", callback_data="admin_prod_add")],
        [InlineKeyboardButton("➖ 删除商品", callback_data="admin_prod_remove")],
        [InlineKeyboardButton("🔙 返回", callback_data="admin_home")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_voucher_menu(update: Update):
    is_enabled = economy.is_voucher_buy_enabled()
    current_cost = economy.get_voucher_cost()
    status_icon = "✅ 关闭" if is_enabled else "🔴 开启"
    toggle_btn_text = "关闭购买模式" if is_enabled else "开启购买模式"
    
    text = (
        f"🎟 兑奖券设置\n"
        f"🛒 可否购买模式{status_icon}\n"
        f"💰 : 需要`{current_cost} 积分兑换`\n\n"
    )
    keyboard = [
        [InlineKeyboardButton("💲 设置所需兑换积分", callback_data="admin_set_vcost")],
        [InlineKeyboardButton(toggle_btn_text, callback_data="admin_toggle_voucher")],
        [InlineKeyboardButton("🔙 返回", callback_data="admin_home")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_config_menu(update: Update):
    session = Session()
    config = session.query(SystemConfig).filter_by(id=1).first()
    pts = config.check_in_points if config else 10.0
    limit = config.check_in_limit if config else 1
    session.close()

    text = (
        f"⚙️ 系统配置\n\n"
        f"📅 签到奖励\n"
        f"• 积分: `{pts}`\n"
        f"• 每日限制: `{limit}`\n\n"
    )
    keyboard = [
        [InlineKeyboardButton("✏️ 编辑积分", callback_data="admin_set_cpts"),
         InlineKeyboardButton("✏️ 编辑限制", callback_data="admin_set_clim")],
        [InlineKeyboardButton("📝 编辑欢迎消息", callback_data="admin_welcome_set")],
        [InlineKeyboardButton("🔙 返回", callback_data="admin_home")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# --- SETTINGS WIZARD (ConversationHandler) ---
WAIT_INPUT = 1

async def start_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    setting_map = {
        "admin_set_vcost": ("兑奖券所需积分", "integer"),
        "admin_set_cpts": ("签到积分", "float"),
        "admin_set_clim": ("每天可签到次数", "integer"),
    }
    
    s_type = query.data
    name, dtype = setting_map.get(s_type, ("Unknown", "string"))
    
    context.user_data['setting_type'] = s_type
    context.user_data['setting_dtype'] = dtype
    
    kb = [[InlineKeyboardButton("❌ 取消", callback_data="admin_cancel_op")]]
    
    await query.edit_message_text(
        f"✏️ 设置名称: {name}**\n\n"
        f"选择新的值:",
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
                
        await update.message.reply_text("✅ 配置已更新", parse_mode='Markdown')
        
        # Return to menu prompt (Admin can click /admin or buttons)
        await update.message.reply_text("输入 /admin 控制版面")
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ 无效格式。请输入一个数字.")
        return WAIT_INPUT

async def cancel_op(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("取消操作")
    await update.callback_query.edit_message_text("🚫 操作已取消")
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
                await update.message.reply_text("⚠️ 请回复用户或直接使用用户ID")
                return
            amount = int(args[1])
        except: 
            pass
    
    if target_id and amount:
        economy.add_vouchers(target_id, amount)
        await update.message.reply_text(f"✅ `{target_id}` 获得 {amount} 兑奖券", parse_mode='Markdown')
    else:
        await update.message.reply_text(
            "用法:\n"
            "1. 回复用户: `/give <数量>`\n"
            "2. 通过ID: `/give <ID> <数量>`", 
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