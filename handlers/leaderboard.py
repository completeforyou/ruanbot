# ruanbot/handlers/leaderboard.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services import economy
from telegram.helpers import mention_html
import math

# Constants
ITEMS_PER_PAGE = 10
MAX_ITEMS = 30

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Entry point for /rank or 排名
    Defaults to Page 0, Sort by Points.
    """
    # Default state
    await render_leaderboard(update, page=0, sort_by='points', is_new=True)

async def leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles pagination buttons: lb_points_1, lb_daily_0, etc.
    """
    query = update.callback_query
    data = query.data  # Format: lb_{sort_by}_{page}
    
    parts = data.split('_')
    sort_by = parts[1] # 'points' or 'msg'
    page = int(parts[2])
    
    await render_leaderboard(update, page, sort_by, is_new=False)
    await query.answer()

async def render_leaderboard(update: Update, page: int, sort_by: str, is_new: bool):
    """
    Generates the text and keyboard, then sends or edits the message.
    """
    # 1. Fetch Data
    users = economy.get_leaderboard(sort_by=sort_by if sort_by == 'msg' else 'daily_msg' if sort_by == 'msg' else 'points', limit=MAX_ITEMS)
    
    # Handle empty DB
    if not users:
        text = "📊 还没有用户数据!"
        if is_new:
            await update.message.reply_text(text)
        else:
            await update.callback_query.edit_message_text(text)
        return

    # 2. Slice for Pagination
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_users = users[start_idx:end_idx]
    
    # 3. Build Text
    title = "🏆 积分排行榜" if sort_by == 'points' else "🗣 今日活跃榜"
    text = f"{title} (Top {MAX_ITEMS})\n"
    text += "━━━━━━━━━━━━━━\n"
    
    rank_start = start_idx + 1
    
    for i, user in enumerate(page_users):
        rank = rank_start + i
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
        
        name = user.full_name if user.full_name else "User"
        # Sanitize name to avoid HTML errors
        name = name.replace("<", "&lt;").replace(">", "&gt;")
        
        if sort_by == 'points':
            val = int(user.points)
            text += f"{medal} <b>{name}</b>: 💰 {val}\n"
        else:
            val = user.msg_count_daily
            text += f"{medal} <b>{name}</b>: 🗣 {val} 条\n"
            
    text += "━━━━━━━━━━━━━━\n"
    text += f"📄 页数: {page + 1}/{math.ceil(len(users)/ITEMS_PER_PAGE)}"

    # 4. Build Buttons
    keyboard = []
    nav_row = []
    
    # Back Button
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"lb_{sort_by}_{page-1}"))
    else:
        nav_row.append(InlineKeyboardButton("⬛", callback_data="ignore")) # Spacer
        
    # Toggle Button (Middle)
    if sort_by == 'points':
        nav_row.append(InlineKeyboardButton("🔄看活跃", callback_data=f"lb_msg_0"))
    else:
        nav_row.append(InlineKeyboardButton("🔄看积分", callback_data=f"lb_points_0"))

    # Next Button
    if end_idx < len(users):
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"lb_{sort_by}_{page+1}"))
    else:
        nav_row.append(InlineKeyboardButton("⬛", callback_data="ignore")) # Spacer
        
    keyboard.append(nav_row)
    
    # Refresh/Close
    # MODIFIED: Only show Close button in Private Chats
    if update.effective_chat.type == 'private':
        keyboard.append([InlineKeyboardButton("❌ 关闭", callback_data="admin_close")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 5. Send
    if is_new:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Use edit_message_text for smooth transition
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')