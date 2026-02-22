# handlers/scratchers.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import AsyncSessionLocal, Product, User
from sqlalchemy import select
import random

async def open_scratcher_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows only SCRATCHER items (Cost = Points)."""
    async with AsyncSessionLocal() as session:
        result_prod = await session.execute(select(Product).filter_by(is_active=True, type='scratcher').filter(Product.stock > 0))
        products = result_prod.scalars().all()

    msg = f"🃏 积分刮刮乐 🃏\n"
    msg += f"━━━━━━━━━━━━━━\n"
    
    if not products:
        msg += "目前没有刮刮乐活动。"
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    keyboard = []
    for p in products:
        cost = int(p.cost)
        msg += f"🎁 **{p.name}**\n   • 花费: {cost} 积分\n   • 库存: {p.stock}\n\n"
        keyboard.append([InlineKeyboardButton(f"🖐 刮一刮: {p.name}", callback_data=f"scratcher_play_{p.id}")])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_scratcher_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    product_id = int(query.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result_user = await session.execute(select(User).filter_by(id=user.id).with_for_update())        
        db_user = result_user.scalars().first()
        
        # Row locking
        result_prod = await session.execute(select(Product).filter_by(id=product_id).with_for_update())
        product = result_prod.scalars().first()
        
        if not product or product.stock <= 0:
            await query.answer("❌ 库存不足或商品已下架!", show_alert=True)
            return

        cost = int(product.cost)
        if not db_user or db_user.points < cost:
            await query.answer(f"❌ 需要 {cost} 积分! 您有 {int(db_user.points) if db_user else 0}.", show_alert=True)
            return

        db_user.points -= cost
        
        if random.random() < product.chance:
            product.stock -= 1
            await session.commit()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"🎉 **中奖啦!!** 🎉\n\n{user.mention_html()} 刮开了一张卡片并赢得了: \n**{product.name}**!",
                parse_mode='HTML'
            )
            await query.answer("🎉 恭喜中奖!!!!!", show_alert=True)
        else:
            await session.commit()
            await query.answer("📉 很遗憾，没有刮中。再试一次吧!", show_alert=True)