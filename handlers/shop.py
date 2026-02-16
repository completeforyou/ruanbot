# handlers/shop.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Session, Product, User
from services import economy
import config

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
        
        # --- CAPTION TEXT ---
        msg = f"🛒 积分商城\n"
        msg += f"━━━━━━━━━━━━━━\n"
        msg += f"💰 积分: `{points}` | 🎟 兑奖券: `{vouchers}`\n\n"
        
        keyboard = []
        
        # 1. Standard Products
        if products:
            msg += "可兑换商品\n"
            row = []
            for p in products:
                cost = int(p.cost)
                msg += f"• {p.name} - 💰 {cost}\n"
                row.append(InlineKeyboardButton(f"{p.name} ({cost})", callback_data=f"shop_buy_{p.id}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
        else:
            msg += "(库存不足)\n"
            
        # 2. Buy Vouchers Button (Check if enabled)
        msg += "\n积分兑换兑奖券:\n"
        if economy.is_voucher_buy_enabled():
            v_price = economy.get_voucher_cost()
            msg += f"\n🎟 兑换\n1 兑奖券 = {v_price} 积分"
            keyboard.append([InlineKeyboardButton(f"🎟 兑换 1 张兑奖券 ({v_price} 分)", callback_data="shop_buy_voucher")])
        else:
            msg += "\n🚫 兑奖券兑换功能目前已禁用"
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        # --- SENDING LOGIC ---
        banner_url = config.SHOP_BANNER_URL
        if update.callback_query:
            # If refreshing (clicking a button), we edit the CAPTION
            # Note: We can't turn a text msg into a photo msg, but if the menu 
            # was started with /shop, it's already a photo.
            try:
                await update.callback_query.edit_message_caption(caption=msg, reply_markup=reply_markup, parse_mode='Markdown')
            except Exception:
                # Fallback: If the original message was text (old version), delete and send new photo
                await update.callback_query.message.delete()
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=banner_url,
                    caption=msg,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        else:
            # If called from /shop command, send a PHOTO
            await update.message.reply_photo(
                photo=banner_url,
                caption=msg,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

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
                await query.answer("❌ 兑奖券购买功能已禁用!", show_alert=True)
                await open_shop_menu(update, context) # Refresh to update UI
                return

            v_price = economy.get_voucher_cost()
            if db_user.points >= v_price:
                db_user.points -= v_price
                db_user.vouchers += 1
                session.commit()
                await query.answer("✅ 兑奖券购买成功!", show_alert=True)
                # Refresh the menu to show new balance
                await open_shop_menu(update, context) 
            else:
                await query.answer(f"❌ 需要 {v_price} 积分!", show_alert=True)
            return

        # B. Buying a Product
        product_id = int(data.split("_")[2])
        
        # Atomic Check (prevent race conditions)
        # We need to re-query to get the object for logic, 
        # but strictly speaking, we should use atomic UPDATE here as discussed previously.
        # For now, we will fix the 'NoneType' error first.
        product = session.query(Product).filter_by(id=product_id).first()
        
        if not product or product.stock <= 0:
            await query.answer("❌ 库存不足!", show_alert=True)
            return
            
        cost = int(product.cost)
        if db_user.points >= cost:
            db_user.points -= cost
            product.stock -= 1
            session.commit()
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"🛒 购买成功 \n{user.mention_html()},{product.name} 花费 {cost} 积分",
                parse_mode='HTML'
            )
            await query.answer("✅ 购买成功!", show_alert=True)
            await query.message.delete()
        else:
            await query.answer(f"❌ 需要 {cost} 积分!", show_alert=True)
            
    finally:
        session.close()