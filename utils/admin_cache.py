# ruanbot/utils/admin_cache.py
import time

# In-memory dictionary to store admin lists.
# Format: {chat_id: (timestamp, [admin_user_ids])}
_admin_cache = {} 
CACHE_DURATION = 900  # 15 minutes in seconds

async def is_user_admin(chat_id: int, user_id: int, bot) -> bool:
    """
    Checks if a user is an admin in a specific chat.
    Uses a 15-minute cache to avoid Telegram API rate limits.
    """
    now = time.time()
    
    # 1. Check if we have a valid cache for this group
    if chat_id in _admin_cache and (now - _admin_cache[chat_id][0]) < CACHE_DURATION:
        admin_ids = _admin_cache[chat_id][1]
    else:
        # 2. Cache is missing or expired, fetch a fresh list from Telegram
        try:
            admins = await bot.get_chat_administrators(chat_id)
            admin_ids = [admin.user.id for admin in admins]
            # Update the cache with the current time
            _admin_cache[chat_id] = (now, admin_ids)
        except Exception as e:
            print(f"⚠️ Error fetching admins for chat {chat_id}: {e}")
            return False # Safe fallback if bot lacks permissions
            
    # 3. Return True if the user is in the admin list
    return user_id in admin_ids