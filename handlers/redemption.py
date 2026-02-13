# handlers/redemption.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Session, Product, User
from sqlalchemy import update
import random

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Shows available products in the group with a Draw button.
    """
    session = Session()
    products = session.query(Product).filter(Product.is_active == True, Product.stock > 0).all()
    session.close()

    if not products:
        await update.message.reply_text("🏪 现无抽奖.")
        return

    # Build the message
    msg = "🎰 **抽奖中心** 🎰\n\n"
    keyboard = []
    
    for p in products:
        msg += f"🎁 **{p.name}**\n"
        msg += f"   • 价格: `{p.cost}` 积分\n"
        msg += f"   • 库存: {p.stock}\n"
        # msg += f"   • Chance: {p.chance * 100:.1f}%\n\n" # Optional: Hide chance?
        msg += "\n"
        
        # Add a button for this specific product
        # Callback data format: "draw_{product_id}"
        keyboard.append([InlineKeyboardButton(f"点我抽奖 - {p.name} ({p.cost} pts)", callback_data=f"draw_{p.id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the button click.
    """
    query = update.callback_query
    user = query.from_user
    
    # "draw_1" -> product_id = 1
    product_id = int(query.data.split("_")[1])
    
    session = Session()
    try:
        # 1. Get Data
        db_user = session.query(User).filter_by(id=user.id).first()
        product = session.query(Product).filter_by(id=product_id).first()
        
        # 2. Validations
        if not product or not product.is_active or product.stock <= 0:
            await query.answer("❌ 商品不存在或被缺货", show_alert=True)
            return

        if not db_user or db_user.points < product.cost:
            await query.answer(f"❌ 积分不足! 你目前有 {db_user.points if db_user else 0}.", show_alert=True)
            return

        # 3. Deduct Points (Atomic-ish within transaction)
        db_user.points -= product.cost
        
        # 4. Roll the Dice
        # Generate random 0.0 to 1.0. If roll < chance, they win.
        roll = random.random()
        is_winner = roll < product.chance
        
        if is_winner:
            product.stock -= 1
            session.commit()
            
            # Announce Win in Group
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"🎉 **恭喜！！！** 🎉\n\n"
                     f"👤 {user.mention_html()} 抽中 **{product.name}**!\n"
                     f"📉 花费: {product.cost} 分\n"
                     f"📞 请联系 @qingruanjiang_bot 兑奖.",
                parse_mode='HTML'
            )
            await query.answer("🎉 YOU WON! Check the message!", show_alert=True)
        else:
            session.commit() # Save the point deduction
            await query.answer(f"📉 运气不好，没抽中! 你花费了 {product.cost} 分. 再试一次!", show_alert=True)
            
    except Exception as e:
        print(f"Draw Error: {e}")
        session.rollback()
        await query.answer("❌ System error.", show_alert=True)
    finally:
        session.close()