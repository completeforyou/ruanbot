# handlers/admin_products.py
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from database import Session, Product
from utils.decorators import admin_only, private_chat_only

# Steps for the conversation
NAME, COST, CHANCE, STOCK = range(4)

# Temporary cache
product_cache = {}

@admin_only
@private_chat_only
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎁 **加入新商品**\n\n"
        "请输入商品名称:\n"
        "(输入 /cancel 停止操作)",
        parse_mode='Markdown'
    )
    return NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_cache[update.effective_user.id] = {'name': update.message.text}
    await update.message.reply_text("💰 输入抽奖所需积分:")
    return COST

async def receive_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cost = float(update.message.text)
        if cost < 0: raise ValueError
        product_cache[update.effective_user.id]['cost'] = cost
        await update.message.reply_text("🎲 输入抽奖概率 0-100 ( 比如 10 = 10%, 3 = 3%):")
        return CHANCE
    except ValueError:
        await update.message.reply_text("❌ Invalid number. Enter a positive number.")
        return COST

async def receive_chance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chance = float(update.message.text)
        if not (0 < chance <= 100): raise ValueError
        # Convert 10% -> 0.1
        product_cache[update.effective_user.id]['chance'] = chance / 100.0
        await update.message.reply_text("📦 输入商品数量:")
        return STOCK
    except ValueError:
        await update.message.reply_text("❌ Invalid. Enter number between 0.1 and 100.")
        return CHANCE

async def receive_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stock = int(update.message.text)
        data = product_cache[update.effective_user.id]
        
        # Save to DB
        session = Session()
        new_prod = Product(
            name=data['name'],
            cost=data['cost'],
            chance=data['chance'],
            stock=stock
        )
        session.add(new_prod)
        session.commit()
        session.close()
        
        await update.message.reply_text(
            f"✅ **Product Added!**\n\n"
            f"📌 Name: {data['name']}\n"
            f"💰 Cost: {data['cost']}\n"
            f"🎲 Chance: {data['chance']*100:.1f}%\n"
            f"📦 Stock: {stock}",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Invalid integer.")
        return STOCK

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Operation cancelled.")
    return ConversationHandler.END

# Handler Registry
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('add_product', add_product_start)],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cost)],
        CHANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_chance)],
        STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_stock)],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)