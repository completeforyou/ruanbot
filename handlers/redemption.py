# handlers/redemption.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import AsyncSessionLocal, Product, User
from sqlalchemy import select
import random

async def open_lottery_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows only LOTTERY items (Cost = Vouchers)."""
    async with AsyncSessionLocal() as session:
        result_prod = await session.execute(select(Product).filter_by(is_active=True, type='lottery').filter(Product.stock > 0))
        products = result_prod.scalars().all()

    msg = f"🎰 付费抽奖 🎰\n"
    msg += f"━━━━━━━━━━━━━━\n"
    
    if not products:
        msg += "目前没有进行中的抽奖活动。"
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    keyboard = []
    for p in products:
        cost = int(p.cost)
        msg += f"🎁 \n{p.name}\n   • 花费: 🎟 {cost} 兑奖券\n   • 库存: {p.stock}\n\n"
        keyboard.append([InlineKeyboardButton(f"🎲 抽奖: {p.name}", callback_data=f"lottery_draw_{p.id}")])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_lottery_draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    product_id = int(query.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result_user = await session.execute(select(User).filter_by(id=user.id))
        db_user = result_user.scalars().first()
        
        # Row locking here too
        result_prod = await session.execute(select(Product).filter_by(id=product_id).with_for_update())
        product = result_prod.scalars().first()
        
        if not product or product.stock <= 0:
            await query.answer("❌ 库存不足!", show_alert=True)
            return

        cost = int(product.cost)
        if not db_user or db_user.vouchers < cost:
            await query.answer(f"❌ 需要 {cost} 兑奖券! 您有 {db_user.vouchers if db_user else 0}.", show_alert=True)
            return

        db_user.vouchers -= cost
        
        if random.random() < product.chance:
            product.stock -= 1
            await session.commit()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"🎉 中奖!!!!!🎉 {user.mention_html()} 花费 {cost} 兑奖券并赢得了 {product.name}!",
                parse_mode='HTML'
            )
            await query.answer("🎉 中奖!!!!!", show_alert=True)
        else:
            await session.commit()
            await query.answer("📉 本次没有中奖。再试一次!", show_alert=True)