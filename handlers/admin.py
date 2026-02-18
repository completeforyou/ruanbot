# handlers/admin.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.helpers import mention_html
from utils.decorators import admin_only, private_chat_only
from services import economy
from database import Session, Product
from models.user import User
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
    status_icon = "✅ 开启" if is_enabled else "🔴 关闭"
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
    conf = economy.get_system_config()

    text = (
        f"⚙️ 系统配置\n\n"
        f"📅 签到奖励\n"
        f"• 积分: `{conf['check_in_points']}`\n"
        f"• 每日限制: `{conf['check_in_limit']}`\n\n"

        f"🤝 邀请\n"
        f"• 奖励: `{conf['invite_reward_points']}`\n\n"

        f"🛡 防刷屏 \n"
        f"• 阈值(秒): `{conf['spam_threshold']}`\n"
        f"• 限制(条): `{conf['spam_limit']}`\n\n"

        f"💰 经济\n"
        f"• 每日上限: `{conf['max_daily_points']}`\n"

        f"🗑 媒体自删 \n"
        f"• 时间: `{conf['media_delete_time']} 秒` (0 = 关闭)\n"
    )
    keyboard = [
        [InlineKeyboardButton("✏️ 签到积分", callback_data="admin_set_cpts"),
         InlineKeyboardButton("✏️ 签到次数", callback_data="admin_set_clim")],

        [InlineKeyboardButton("✏️ 邀请奖励", callback_data="admin_set_invite"),
         InlineKeyboardButton("✏️ 每日上限", callback_data="admin_set_daily")],

        [InlineKeyboardButton("✏️ 刷屏时间", callback_data="admin_set_sthr"),
         InlineKeyboardButton("✏️ 刷屏条数", callback_data="admin_set_slim")],

        [InlineKeyboardButton("✏️ 设置媒体自删时间", callback_data="admin_set_mdel")],

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
        "admin_set_invite": ("邀请奖励积分", "float"),
        "admin_set_daily": ("每日获得积分上限", "integer"),
        "admin_set_sthr": ("防刷屏判断时间 (秒)", "float"),
        "admin_set_slim": ("防刷屏判断条数", "integer"),
        "admin_set_mdel": ("媒体自动删除时间 (秒, 0=关闭)", "integer")
    }
    
    s_type = query.data
    name, dtype = setting_map.get(s_type, ("Unknown", "string"))
    
    context.user_data['setting_type'] = s_type
    context.user_data['setting_dtype'] = dtype
    
    kb = [[InlineKeyboardButton("🔙 返回", callback_data="admin_home")]]
    
    await query.edit_message_text(
        f"✏️ 设置名称: {name}\n\n"
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
            
        # --- LOGIC MAPPING ---
        if s_type == "admin_set_vcost":
            economy.update_system_config(voucher_cost=val)
        elif s_type == "admin_set_cpts":
            economy.update_system_config(check_in_points=val)
        elif s_type == "admin_set_clim":
            economy.update_system_config(check_in_limit=val)
        elif s_type == "admin_set_invite":
            economy.update_system_config(invite_reward_points=val)
        elif s_type == "admin_set_daily":
            economy.update_system_config(max_daily_points=val)
        elif s_type == "admin_set_sthr":
            economy.update_system_config(spam_threshold=val)
        elif s_type == "admin_set_slim":
            economy.update_system_config(spam_limit=val)
        elif s_type == "admin_set_mdel":
            economy.update_system_config(media_delete_time=val)
                
        keyboard = [[InlineKeyboardButton("🔙 返回控制面板", callback_data="admin_home")]]
        await update.message.reply_text(
            "✅ 配置已更新", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text("❌ 无效格式。请输入一个数字.")
        return WAIT_INPUT

async def cancel_op(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("取消操作")
    await update.callback_query.edit_message_text("🚫 操作已取消")
    return ConversationHandler.END

async def back_to_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Exits the conversation cleanly and returns to the admin panel.
    """
    await admin_panel(update, context)
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
    target_name = "用户"
    amount = None

    # Case 1: Reply to a message
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_id = target_user.id
        target_name = target_user.full_name
        try: 
            amount = int(args[0])
        except: 
            pass
            
    # Case 2: ID and Amount arguments
    elif len(args) >= 2:
        try:
            if args[0].isdigit(): 
                target_id = int(args[0])
                session = Session()
                db_user = session.query(User).filter_by(id=target_id).first()
                if db_user:
                    target_name = db_user.full_name
                session.close()
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
        user_mention = mention_html(target_id, target_name)
        await update.message.reply_text(f"✅ {user_mention} 获得 {amount} 兑奖券", parse_mode='HTML')
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
        CallbackQueryHandler(start_setting, pattern="^admin_set_")
    ],
    states={
        WAIT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_setting)]
    },
    fallbacks=[
        CallbackQueryHandler(cancel_op, pattern="^admin_cancel_op$"),
        CallbackQueryHandler(back_to_home, pattern="^admin_home$"),
        MessageHandler(filters.COMMAND, cancel_op)
    ]
)