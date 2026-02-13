# services/content_filter.py
from sqlalchemy import select, delete
from database import Session, SensitiveWord
from telegram import Message, MessageEntity
import re

# In-memory cache to avoid DB hits on every message
_word_cache = set()
_cache_loaded = False

def load_cache():
    """Loads sensitive words from DB into memory."""
    global _cache_loaded
    session = Session()
    try:
        words = session.scalars(select(SensitiveWord.word)).all()
        _word_cache.clear()
        for w in words:
            _word_cache.add(w.lower())
        _cache_loaded = True
    finally:
        session.close()

def add_word(word: str):
    """Adds a word to the blocklist."""
    session = Session()
    try:
        if not session.get(SensitiveWord, word.lower()):
            session.add(SensitiveWord(word=word.lower()))
            session.commit()
            _word_cache.add(word.lower())
            return True
        return False
    finally:
        session.close()

def remove_word(word: str):
    """Removes a word from the blocklist."""
    session = Session()
    try:
        obj = session.get(SensitiveWord, word.lower())
        if obj:
            session.delete(obj)
            session.commit()
            if word.lower() in _word_cache:
                _word_cache.remove(word.lower())
            return True
        return False
    finally:
        session.close()

def get_all_words():
    if not _cache_loaded:
        load_cache()
    return list(_word_cache)

def check_violation(message: Message) -> str | None:
    """
    Checks for:
    1. Forwarded from Channel
    2. Links
    3. Sensitive Words
    Returns the reason (str) or None if safe.
    """
    if not _cache_loaded:
        load_cache()

    # 1. Check Forward from Channel (Updated for PTB v21+)
    # We use getattr safely in case the attribute doesn't exist
    if getattr(message, 'forward_origin', None):
        if getattr(message.forward_origin, 'type', None) == 'channel':
            return "Channel Forward"

    # 2. Check Links
    if message.entities or message.caption_entities:
        entities = message.entities or message.caption_entities
        for entity in entities:
            if entity.type in [MessageEntity.URL, MessageEntity.TEXT_LINK]:
                return "Unauthorized Link"

    # 3. Check Sensitive Words
    text = message.text or message.caption or ""
    if text:
        text_lower = text.lower()
        for bad_word in _word_cache:
            if bad_word in text_lower:
                return f"Sensitive Word: {bad_word}"

    return None