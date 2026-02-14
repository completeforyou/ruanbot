# handlers/redemption.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Session, Product, User
import random

async def open_lottery_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows only LOTTERY items (Cost = Vouchers)."""
    session = Session()
    # Filter for type='lottery'
    products = session.query(Product).filter_by(is_active=True, type='lottery').filter(Product.stock > 0).all()
    session.close()
    
    # Get User Balance
    user = update.effective_user
    session = Session()
    db_user = session.query(User).filter_by(id=user.id).first()
    vouchers = db_user.vouchers if db_user else 0
    session.close()

    msg = f"🎰 **Voucher Lottery** 🎰\nYour Balance: 🎟 **{vouchers} Vouchers**\n\n"
    
    if not products:
        msg += "No lottery events running currently."
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    keyboard = []
    for p in products:
        cost = int(p.cost)
        msg += f"🎁 **{p.name}**\n   • Cost: 🎟 {cost} Voucher(s)\n   • Stock: {p.stock}\n\n"
        keyboard.append([InlineKeyboardButton(f"🎲 Draw: {p.name}", callback_data=f"lottery_draw_{p.id}")])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_lottery_draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    product_id = int(query.data.split("_")[2])
    
    session = Session()
    try:
        db_user = session.query(User).filter_by(id=user.id).first()
        product = session.query(Product).filter_by(id=product_id).first()
        
        if not product or product.stock <= 0:
            await query.answer("❌ Out of stock!", show_alert=True)
            return

        # CHECK VOUCHERS
        cost = int(product.cost)
        if not db_user or db_user.vouchers < cost:
            await query.answer(f"❌ Need {cost} Vouchers! You have {db_user.vouchers}.", show_alert=True)
            return

        # Deduct Vouchers
        db_user.vouchers -= cost
        
        # Calculate Win
        if random.random() < product.chance:
            product.stock -= 1
            session.commit()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"🎉 **JACKPOT!** {user.mention_html()} used {cost} Voucher and won **{product.name}**!",
                parse_mode='HTML'
            )
            await query.answer("🎉 YOU WON!", show_alert=True)
        else:
            session.commit()
            await query.answer("📉 No luck this time. Try again!", show_alert=True)
            
    finally:
        session.close()