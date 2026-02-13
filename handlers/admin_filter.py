# handlers/admin_filter.py
from telegram import Update
from telegram.ext import ContextTypes
from services import content_filter
from utils.decorators import admin_only, private_chat_only

@admin_only
@private_chat_only
async def add_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /add_word badword"""
    if not context.args:
        await update.message.reply_text("Usage: `/add_word <word>`", parse_mode='Markdown')
        return

    word = " ".join(context.args).lower()
    if content_filter.add_word(word):
        await update.message.reply_text(f"✅ {word} 已添加到黑名单.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"⚠️ {word} 已在黑名单中.", parse_mode='Markdown')

@admin_only
@private_chat_only
async def del_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /del_word badword"""
    if not context.args:
        await update.message.reply_text("Usage: `/del_word <word>`", parse_mode='Markdown')
        return

    word = " ".join(context.args).lower()
    if content_filter.remove_word(word):
        await update.message.reply_text(f"{word} 已从黑名单中移除.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"⚠️ {word} 不在黑名单中.", parse_mode='Markdown')

@admin_only
@private_chat_only
async def list_words_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = content_filter.get_all_words()
    if not words:
        await update.message.reply_text("📜 黑名单是空的.")
    else:
        # Join words with commas
        msg = "🚫 敏感词:\n\n" + ", ".join(words)
        await update.message.reply_text(msg, parse_mode='Markdown')