# ruanbot/handlers/leaderboard.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services import economy
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
    # 1. Calculate Offsets
    start_idx = page * ITEMS_PER_PAGE

    # 2. Fetch EXACTLY 10 users from the DB (Super Fast!)
    page_users = economy.get_leaderboard(sort_by=sort_by, limit=ITEMS_PER_PAGE, offset=start_idx)
    
    # 3. Fetch Total Pages
    total_users = economy.get_total_ranked_users(max_limit=MAX_ITEMS)
    total_pages = math.ceil(total_users / ITEMS_PER_PAGE)
    if total_pages == 0: total_pages = 1
    
    # Handle empty DB
    if not page_users and page == 0:
        text = "📊 还没有用户数据!"
        if is_new:
            await update.message.reply_text(text)
        else:
            await update.callback_query.edit_message_text(text)
        return
    
    # 4. Build Text
    title = "🏆 积分排行榜" if sort_by == 'points' else "🗣 活跃榜"
    text = f"<b>{title} (Top {MAX_ITEMS})</b>\n"
    text += "━━━━━━━━━━━━━━\n"
    
    rank_start = start_idx + 1
    
    for i, user in enumerate(page_users):
        rank = rank_start + i
        
        raw_name = user['full_name'] if user['full_name'] else "User"
        name = raw_name.replace("<", "").replace(">", "") # Sanitize HTML
        if len(name) > 6:
            name = name[:5] + "…"
        
        # Decoration Logic
        if rank == 1:
            medal = "🥇"
            suffix = "🐲"
        elif rank == 2:
            medal = "🥈"
            suffix = "🐮"
        elif rank == 3:
            medal = "🥉"
            suffix = "🚰"
        else:
            medal = "  "
            suffix = "🌟"

        # Value Logic
        if sort_by == 'points':
            val = int(user['points'])
            unit = "积分"
        else:
            val = user['msg_count_daily']
            unit = "条"

        # Format Construction
        line = f"第{rank}名{medal}"
        line += f"{val}{unit}{suffix}"+ (" " * 5)
        line += f"{name:<8}"
        
        text += f"<code>{line}</code>\n"
            
    text += "━━━━━━━━━━━━━━\n"
    text += f"📄 页数: {page + 1}/{total_pages}"

    # 5. Build Buttons
    keyboard = []
    nav_row = []
    
    # Back Button
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"lb_{sort_by}_{page-1}"))
    else:
        nav_row.append(InlineKeyboardButton("⬛", callback_data="ignore"))
        
    # Toggle Button
    if sort_by == 'points':
        nav_row.append(InlineKeyboardButton("🔄 看活跃", callback_data=f"lb_msg_0"))
    else:
        nav_row.append(InlineKeyboardButton("🔄 看积分", callback_data=f"lb_points_0"))

    # Next Button
    if (page + 1) < total_pages:
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"lb_{sort_by}_{page+1}"))
    else:
        nav_row.append(InlineKeyboardButton("⬛", callback_data="ignore"))

    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 6. Send
    if is_new:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')