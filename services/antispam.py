# services/antispam.py
from datetime import datetime, timedelta

# In-Memory Caches
_spam_cache = {}          # {user_id: [timestamp1, timestamp2...]}
_shadow_mutes = {}        # {user_id: timestamp_when_penalty_ends}

def check_is_spamming(user_id: int, limit: int, timeframe: float) -> bool:
    """Returns True if user sent > limit messages in timeframe seconds."""
    now = datetime.now().timestamp()
    
    if user_id not in _spam_cache:
        _spam_cache[user_id] = []
    
    _spam_cache[user_id].append(now)
    
    # Keep only timestamps within the timeframe
    _spam_cache[user_id] = [t for t in _spam_cache[user_id] if now - t <= timeframe]
    
    if len(_spam_cache[user_id]) > limit:
        _spam_cache[user_id] = [] # Reset cache to prevent double-firing
        return True
    return False

def add_shadow_mute(user_id: int, duration_minutes: int):
    """Admin penalty: User can speak but earns no points."""
    end_time = datetime.now() + timedelta(minutes=duration_minutes)
    _shadow_mutes[user_id] = end_time.timestamp()

def is_shadow_muted(user_id: int) -> bool:
    """Checks if a user is currently under shadow mute."""
    if user_id in _shadow_mutes:
        if datetime.now().timestamp() < _shadow_mutes[user_id]:
            return True
        else:
            del _shadow_mutes[user_id] # Expired
    return False