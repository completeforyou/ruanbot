# handlers/admin_products.py
from multiprocessing import context
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from sqlalchemy import select
from database import AsyncSessionLocal, Product
from utils.decorators import admin_only, private_chat_only

# Steps
TYPE, NAME, COST, CHANCE, STOCK = range(5)

def get_cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="admin_cancel_prod")]])

# Entry Points
@admin_only
@private_chat_only
async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This can be triggered by command /add_product or button
    context.user_data['new_product'] = {}
    
    # Ask Type
    keyboard = [
        [InlineKeyboardButton("🛒 积分商店 (100% 获得)", callback_data="type_shop")],
        [InlineKeyboardButton("🃏 积分刮刮乐 (概率获得)", callback_data="type_scratcher")], 
        [InlineKeyboardButton("🎟 代币抽奖 (概率获得)", callback_data="type_lottery")],
        [InlineKeyboardButton("❌ 取消", callback_data="admin_cancel_prod")]
    ]
    
    text = "🎁 新增商品\n\n请选择商品类型:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return TYPE

async def receive_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    p_type = query.data.split('_')[1] # 'shop', 'scratcher', or 'lottery'
    context.user_data['new_product']['type'] = p_type
    
    type_names = {
        'shop': "🛒 兑换商城",
        'scratcher': "🃏 娱乐抽奖",
        'lottery': "🎟 付费抽奖"
    }
    
    t_name = type_names.get(p_type, p_type)
    
    await query.edit_message_text(f"✅ 类型: {t_name}\n\n请输入商品名称:",
                                  reply_markup=get_cancel_kb(),
                                  parse_mode='Markdown')
    return NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_product']['name'] = update.message.text
    p_type = context.user_data['new_product']['type']
    
    # Determine Currency based on type
    # Lottery uses Vouchers, Shop and Scratcher use Points
    currency = "兑奖券" if p_type == 'lottery' else "积分"
    
    await update.message.reply_text(f"💰 请设置所需 {currency} 数量:", reply_markup=get_cancel_kb())
    return COST

async def receive_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cost = float(update.message.text)
        context.user_data['new_product']['cost'] = cost
       
        p_type = context.user_data['new_product']['type']
        
        # If it's a game of chance (Lottery OR Scratcher), ask for probability
        if p_type in ['lottery', 'scratcher']:
            await update.message.reply_text("🎲 设置中奖概率 (0 = 0%, 100 = 100%):", reply_markup=get_cancel_kb())
            return CHANCE
        else:
            # Shop items have 100% chance, skip to stock
            context.user_data['new_product']['chance'] = 1.0            
            await update.message.reply_text("📦 设置商品库存 (0-999):", reply_markup=get_cancel_kb())
            return STOCK
            
    except ValueError:
        await update.message.reply_text("❌ 无效数字，请重新输入:")
        return COST

async def receive_chance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chance = float(update.message.text)
        if not (0 <= chance <= 100): raise ValueError
        context.user_data['new_product']['chance'] = chance / 100.0
        await update.message.reply_text("📦 设置商品库存 (0-999):", reply_markup=get_cancel_kb())
        return STOCK
    except ValueError:
        await update.message.reply_text("❌ 无效数字，请重新输入 (0-100):")
        return CHANCE

async def receive_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stock = int(update.message.text)
        data = context.user_data['new_product']
        
        async with AsyncSessionLocal() as session:
            new_prod = Product(
                name=data['name'],
                type=data['type'],
                cost=data['cost'],
                chance=data['chance'],
                stock=stock
            )
            session.add(new_prod)
            await session.commit()
        
        keyboard = [[InlineKeyboardButton("🔙 返回控制面板", callback_data="admin_home")]]
        await update.message.reply_text(f"✅ {data['type'].title()} 商品已添加！\n{data['name']}", 
                                        reply_markup=InlineKeyboardMarkup(keyboard)
                                        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ 无效数字，请重新输入:")
        return STOCK

async def cancel_op(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the conversation and returns to admin home."""
    if update.callback_query:
        await update.callback_query.answer("已取消")
        # Call the admin panel function directly to refresh the UI
        from handlers.admin import admin_panel
        await admin_panel(update, context)
    else:
        await update.message.reply_text("🚫 操作已取消。输入 /admin 返回。")
    return ConversationHandler.END

@admin_only
async def start_remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists products with delete buttons."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Product))
        products = result.scalars().all()

    if not products:
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_shop_menu")]]
        await update.callback_query.edit_message_text(
            "🗑 删除商品\n\n现无商品", 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='Markdown'
        )
        return

    text = "🗑 删除商品\n请选择一个会永久删除:"
    keyboard = []
    
    for p in products:
        # Button Format: "Name (Type) - 🗑"
        btn_text = f"{p.name} ({p.type}) 🗑"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"admin_delete_prod_{p.id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 返回", callback_data="admin_shop_menu")])
    
    await update.callback_query.edit_message_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )

@admin_only
async def handle_remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deletes the product and refreshes the list."""
    query = update.callback_query
    prod_id = int(query.data.split('_')[-1])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Product).filter_by(id=prod_id))
        product = result.scalars().first()
        
        if product:
            name = product.name
            await session.delete(product)
            await session.commit()
            await query.answer(f"✅ 删除: {name}", show_alert=True)
        else:
            await query.answer("❌ 商品已删除.", show_alert=True)
    
    # Refresh the list
    await start_remove_product(update, context)

# Registry
conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('add', start_add_product),
        CallbackQueryHandler(start_add_product, pattern="^admin_prod_add$")
    ],
    states={
        TYPE: [CallbackQueryHandler(receive_type, pattern="^type_")],
        NAME: [MessageHandler(filters.TEXT, receive_name)],
        COST: [MessageHandler(filters.TEXT, receive_cost)],
        CHANCE: [MessageHandler(filters.TEXT, receive_chance)],
        STOCK: [MessageHandler(filters.TEXT, receive_stock)],
    },
    fallbacks=[CommandHandler('cancel', cancel_op),
               CallbackQueryHandler(cancel_op, pattern="^admin_cancel_prod$")],
)