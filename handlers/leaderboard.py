# ruanbot/handlers/leaderboard.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services import economy
import math
import unicodedata

# Constants
ITEMS_PER_PAGE = 10
MAX_ITEMS = 30

def get_visual_width(s):
    """
    Calculates the visual width of a string.
    Wide characters (CJK, Emojis) count as 2, others as 1.
    """
    width = 0
    for char in s:
        # 'W' = Wide, 'F' = Fullwidth (usually CJK)
        # 'A' = Ambiguous (often Emoji in monospace contexts)
        if unicodedata.east_asian_width(char) in ('F', 'W', 'A'):
            width += 2
        else:
            width += 1
    return width

def smart_pad_truncate(text, target_width):
    """
    Truncates text if too long, pads with spaces if too short.
    Ensures the final visual width is exactly target_width.
    """
    # 1. Truncate if too long
    current_width = get_visual_width(text)
    if current_width > target_width:
        # Strip chars one by one until it fits
        while get_visual_width(text) > target_width - 1: # Leave room for ellipsis? Or just cut.
            text = text[:-1]
        # Optional: Add ellipsis "…" (width 1 or 2 depending on font, safely 1)
        # For strict alignment, we just cut.
    
    # 2. Pad if too short
    current_width = get_visual_width(text)
    padding = max(0, target_width - current_width)
    return text + (" " * padding)

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Entry point for /rank or 排名
    """
    await render_leaderboard(update, page=0, sort_by='points', is_new=True)

async def leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    parts = data.split('_')
    sort_by = parts[1] 
    page = int(parts[2])
    
    await render_leaderboard(update, page, sort_by, is_new=False)
    await query.answer()

async def render_leaderboard(update: Update, page: int, sort_by: str, is_new: bool):
    users = economy.get_leaderboard(sort_by=sort_by if sort_by == 'msg' else 'daily_msg' if sort_by == 'msg' else 'points', limit=MAX_ITEMS)
    
    if not users:
        text = "📊 还没有用户数据!"
        if is_new:
            await update.message.reply_text(text)
        else:
            await update.callback_query.edit_message_text(text)
        return

    # Pagination
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_users = users[start_idx:end_idx]
    
    title = "🏆 积分排行榜" if sort_by == 'points' else "🗣 今日活跃榜"
    text = f"<b>{title} (Top {MAX_ITEMS})</b>\n"
    text += "━━━━━━━━━━━━━━\n"
    
    rank_start = start_idx + 1
    
    for i, user in enumerate(page_users):
        rank = rank_start + i
        name = user.full_name if user.full_name else "User"
        name = name.replace("<", "").replace(">", "") # Sanitize
        
        # --- ALIGNMENT LOGIC ---
        
        # 1. Prepare Rank Column (Visual Width: 8)
        # "第 1名" (Wide chars=2, spaces/digits=1) -> 2+1+1+2 = 6 width
        # Plus Medal (2 width) = 8 width Total
        if rank < 10:
            rank_str = f"第 {rank}名" # Add space for alignment
        else:
            rank_str = f"第{rank}名"
            
        # 2. Prepare Medal & Suffix
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
            medal = "  " # 2 spaces (width 2) to match medal
            suffix = "🌟"

        # 3. Prepare Name Column (Visual Width: 12 - approx 6 Chinese chars)
        name_padded = smart_pad_truncate(name, 12)
        
        # 4. Prepare Value
        if sort_by == 'points':
            val = int(user.points)
            unit = "积分"
        else:
            val = user.msg_count_daily
            unit = "条"

        # 5. Construct Line
        # [Rank+Medal (8)] [Name (12)] [Spacer (10)] [Value...]
        spacer = " " * 10
        line = f"{rank_str}{medal}{name_padded}{spacer}{val}{unit}{suffix}"
        
        text += f"<code>{line}</code>\n"
            
    text += "━━━━━━━━━━━━━━\n"
    text += f"📄 页数: {page + 1}/{math.ceil(len(users)/ITEMS_PER_PAGE)}"

    # Buttons
    keyboard = []
    nav_row = []
    
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"lb_{sort_by}_{page-1}"))
    else:
        nav_row.append(InlineKeyboardButton("⬛", callback_data="ignore"))
        
    if sort_by == 'points':
        nav_row.append(InlineKeyboardButton("🔄 看活跃", callback_data=f"lb_msg_0"))
    else:
        nav_row.append(InlineKeyboardButton("🔄 看积分", callback_data=f"lb_points_0"))

    if end_idx < len(users):
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"lb_{sort_by}_{page+1}"))
    else:
        nav_row.append(InlineKeyboardButton("⬛", callback_data="ignore"))
        
    keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("❌ 关闭", callback_data="admin_close")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_new:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')