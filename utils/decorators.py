# utils/decorators.py
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import config

def admin_only(func):
    """
    Decorator: Only allows users listed in config.ADMIN_IDS to use this command.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        # Check if user is in the approved list
        if user_id not in config.ADMIN_IDS:
            # Option 1: Silent ignore (Best for security)
            return
            
            # Option 2: Reply with error (Use carefully to avoid spam)
            # await update.message.reply_text("⛔ You are not authorized.")
            # return

        # If authorized, run the actual function
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def private_chat_only(func):
    """
    Decorator: Forces the command to work only in Private DMs (not groups).
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.type != 'private':
            await update.message.reply_text("⚠️ 请用私聊使用此命令!")
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper