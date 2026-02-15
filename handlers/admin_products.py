# handlers/admin_products.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from database import Session, Product
from utils.decorators import admin_only, private_chat_only

# Steps
TYPE, NAME, COST, CHANCE, STOCK = range(5)
product_cache = {}

def get_cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel_prod")]])
# Entry Points
@admin_only
@private_chat_only
async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This can be triggered by command /add_product or button
    user_id = update.effective_user.id
    product_cache[user_id] = {}
    
    # Ask Type
    keyboard = [
        [InlineKeyboardButton("🛒 Point Shop (Guaranteed)", callback_data="type_shop")],
        [InlineKeyboardButton("🎰 Lottery (Voucher + Chance)", callback_data="type_lottery")]
    ]
    
    text = "🎁 **Add New Product**\n\nSelect the Product Type:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return TYPE

async def receive_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    p_type = query.data.split('_')[1] # 'shop' or 'lottery'
    product_cache[query.from_user.id]['type'] = p_type
    
    await query.edit_message_text(f"✅ Type: **{p_type.upper()}**\n\nNow enter the **Product Name**:", parse_mode='Markdown')
    return NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_cache[update.effective_user.id]['name'] = update.message.text
    p_type = product_cache[update.effective_user.id]['type']
    
    currency = "POINTS" if p_type == 'shop' else "VOUCHERS"
    await update.message.reply_text(f"💰 Enter the cost in **{currency}**:")
    return COST

async def receive_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cost = float(update.message.text)
        product_cache[update.effective_user.id]['cost'] = cost
        
        p_type = product_cache[update.effective_user.id]['type']
        
        if p_type == 'lottery':
            await update.message.reply_text("🎲 Enter **Win Chance** (0-100)%:")
            return CHANCE
        else:
            # Shop items have 100% chance, skip to stock
            product_cache[update.effective_user.id]['chance'] = 1.0
            await update.message.reply_text("📦 Enter **Stock Quantity**:")
            return STOCK
            
    except ValueError:
        await update.message.reply_text("❌ Invalid number.")
        return COST

async def receive_chance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chance = float(update.message.text)
        if not (0 < chance <= 100): raise ValueError
        product_cache[update.effective_user.id]['chance'] = chance / 100.0
        await update.message.reply_text("📦 Enter **Stock Quantity**:")
        return STOCK
    except ValueError:
        await update.message.reply_text("❌ Invalid. Enter number 0-100.")
        return CHANCE

async def receive_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stock = int(update.message.text)
        data = product_cache[update.effective_user.id]
        
        session = Session()
        new_prod = Product(
            name=data['name'],
            type=data['type'],
            cost=data['cost'],
            chance=data['chance'],
            stock=stock
        )
        session.add(new_prod)
        session.commit()
        session.close()
        
        await update.message.reply_text(f"✅ **{data['type'].title()} Product Added!**\n{data['name']}")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Invalid integer.")
        return STOCK

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Cancelled.")
    return ConversationHandler.END

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
    fallbacks=[CommandHandler('cancel', cancel)],
)