# handlers/shop.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Session, Product, User
from services import economy

# Config: How many points = 1 Voucher?
VOUCHER_PRICE_POINTS = 500

async def open_shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows Point Shop items + Option to buy Vouchers."""
    session = Session()
    try:
        # Filter for type='shop'
        products = session.query(Product).filter_by(is_active=True, type='shop').filter(Product.stock > 0).all()
        
        user = update.effective_user
        db_user = session.query(User).filter_by(id=user.id).first()
        points = int(db_user.points) if db_user else 0
        vouchers = db_user.vouchers if db_user else 0
        
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
            
        # 2. Buy Vouchers Button (Check if enabled)
        msg += "\n**Exchange:**"
        if economy.is_voucher_buy_enabled():
            keyboard.append([InlineKeyboardButton(f"🎟 Buy 1 Voucher ({VOUCHER_PRICE_POINTS} pts)", callback_data="shop_buy_voucher")])
        else:
            msg += "\n🚫 *Voucher purchasing is currently disabled by Admin.*"
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        # --- FIX: Handle both Command (New Message) and Callback (Edit Message) ---
        if update.callback_query:
            # If called from a button (refresh), edit the old message
            await update.callback_query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            # If called from /shop command, send a new message
            await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='Markdown')

    finally:
        session.close()

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
            # Check if enabled
            if not economy.is_voucher_buy_enabled():
                await query.answer("❌ Voucher purchasing is disabled!", show_alert=True)
                await open_shop_menu(update, context) # Refresh to update UI
                return

            if db_user.points >= VOUCHER_PRICE_POINTS:
                db_user.points -= VOUCHER_PRICE_POINTS
                db_user.vouchers += 1
                session.commit()
                await query.answer("✅ Voucher purchased!", show_alert=True)
                # Refresh the menu to show new balance
                await open_shop_menu(update, context) 
            else:
                await query.answer(f"❌ Need {VOUCHER_PRICE_POINTS} points!", show_alert=True)
            return

        # B. Buying a Product
        product_id = int(data.split("_")[2])
        
        # Atomic Check (prevent race conditions)
        # We need to re-query to get the object for logic, 
        # but strictly speaking, we should use atomic UPDATE here as discussed previously.
        # For now, we will fix the 'NoneType' error first.
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