# handlers/shop.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Session, Product, User
from services import economy

# Config: How many points = 1 Voucher?
VOUCHER_PRICE_POINTS = 500  # <--- Change this if you want

async def open_shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows Point Shop items + Option to buy Vouchers."""
    session = Session()
    # Filter for type='shop'
    products = session.query(Product).filter_by(is_active=True, type='shop').filter(Product.stock > 0).all()
    
    user = update.effective_user
    db_user = session.query(User).filter_by(id=user.id).first()
    points = int(db_user.points) if db_user else 0
    vouchers = db_user.vouchers if db_user else 0
    session.close()
    
    msg = f"🛒 **Point Shop**\n"
    msg += f"💰 Points: `{points}` | 🎟 Vouchers: `{vouchers}`\n\n"
    
    keyboard = []
    
    # 1. Standard Products
    if products:
        msg += "**Redeemable Items:**\n"
        for p in products:
            cost = int(p.cost)
            msg += f"• {p.name} - 💰 {cost} Pts\n"
            keyboard.append([InlineKeyboardButton(f"Buy {p.name} ({cost} pts)", callback_data=f"shop_buy_{p.id}")])
    else:
        msg += "(No items currently in stock)\n"
        
    msg += "\n**Exchange:**"
    # --- CHECK STATUS HERE ---
    if economy.is_voucher_buy_enabled():
        keyboard.append([InlineKeyboardButton(f"🎟 Buy 1 Voucher ({VOUCHER_PRICE_POINTS} pts)", callback_data="shop_buy_voucher")])
    else:
        msg += "\n🚫 *Voucher purchasing is currently disabled by Admin.*"
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_shop_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    session = Session()
    try:
        db_user = session.query(User).filter_by(id=user.id).first()
        if not db_user: return
        
        # A. Buying a Voucher
        if data == "shop_buy_voucher":
            # --- SECURITY CHECK ---
            if not economy.is_voucher_buy_enabled():
                await query.answer("❌ Voucher purchasing is currently disabled!", show_alert=True)
                # Optional: Refresh the menu to show it's gone
                await open_shop_menu(update, context)
                return
            # ----------------------
            if db_user.points >= VOUCHER_PRICE_POINTS:
                db_user.points -= VOUCHER_PRICE_POINTS
                db_user.vouchers += 1
                session.commit()
                await query.answer("✅ Voucher purchased!", show_alert=True)
                # Refresh the menu
                await open_shop_menu(update, context) 
            else:
                await query.answer(f"❌ Need {VOUCHER_PRICE_POINTS} points!", show_alert=True)
            return

        # B. Buying a Product
        product_id = int(data.split("_")[2])
        product = session.query(Product).filter_by(id=product_id).first()
        
        if not product or product.stock <= 0:
            await query.answer("❌ Out of stock!", show_alert=True)
            return
            
        cost = int(product.cost)
        if db_user.points >= cost:
            db_user.points -= cost
            product.stock -= 1
            session.commit()
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"🛒 **Purchase Successful!**\n{user.mention_html()} redeemed **{product.name}** for {cost} points.",
                parse_mode='HTML'
            )
            await query.answer("✅ Redeemed!", show_alert=True)
            await query.message.delete()
        else:
            await query.answer(f"❌ Need {cost} points!", show_alert=True)
            
    finally:
        session.close()