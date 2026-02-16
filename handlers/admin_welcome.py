# handlers/admin_welcome.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from database import Session, WelcomeConfig
from utils.decorators import admin_only, private_chat_only

# Conversation states
MEDIA, TEXT, BUTTONS = range(3)
_cache = {}

def get_cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="admin_welcome_cancel")]])

@admin_only
@private_chat_only
async def set_welcome_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _cache[update.effective_user.id] = {'media_id': None, 'media_type': None, 'text': '', 'buttons': []}
    
    text_msg = (
        "📝 欢迎消息设置\n\n"
        "1: 发送一张照片、视频或GIF以附加到欢迎消息。\n\n"
        "(输入 /skip 跳过此步骤, 仅使用文本欢迎消息)"
    )

    # Handle if clicked from Admin Panel (Callback) vs Command
    if update.callback_query:
        await update.callback_query.answer()
        # Send a NEW message because we can't upload media to an existing text-only message easily later
        await update.callback_query.message.reply_text(text_msg, parse_mode='Markdown')
    else:
        await update.message.reply_text(text_msg, parse_mode='Markdown')
        
    return MEDIA

async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if update.message.text == '/skip':
        pass 
    elif update.message.photo:
        _cache[user_id]['media_id'] = update.message.photo[-1].file_id
        _cache[user_id]['media_type'] = 'photo'
    elif update.message.video:
        _cache[user_id]['media_id'] = update.message.video.file_id
        _cache[user_id]['media_type'] = 'video'
    elif update.message.animation:
        _cache[user_id]['media_id'] = update.message.animation.file_id
        _cache[user_id]['media_type'] = 'animation'
    else:
        await update.message.reply_text("❌ 请发送照片,视频或GIF,或输入 /skip.")
        return MEDIA

    await update.message.reply_text(
        "2: 发送欢迎消息的文本\n\n"
        "💡 提示: 在文本中使用 `{user}` 来标记用户\n",
        parse_mode='Markdown'
    )
    return TEXT

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _cache[update.effective_user.id]['text'] = update.message.text
    
    await update.message.reply_text(
        "3: 添加自定义URL按钮。\n"
        "格式: `按钮名称 : https://link.com`\n"
        "每行一个.\n\n"
        "*(或输入 /skip)*",
        parse_mode='Markdown'
    )
    return BUTTONS

async def receive_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text_input = update.message.text
    
    if text_input != '/skip':
        lines = text_input.split('\n')
        for line in lines:
            if ':' in line:
                parts = line.split(':', 1)
                _cache[user_id]['buttons'].append([parts[0].strip(), parts[1].strip()])

    # Save to Database
    data = _cache[user_id]
    session = Session()
    
    config = session.query(WelcomeConfig).filter_by(id=1).first()
    if not config:
        config = WelcomeConfig(id=1)
        session.add(config)
        
    config.media_file_id = data['media_id']
    config.media_type = data['media_type']
    config.text = data['text']
    config.buttons = data['buttons']
    
    session.commit()
    session.close()
    
    await update.message.reply_text("✅ 欢迎消息已更新!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 设置已取消.")
    return ConversationHandler.END

welcome_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('set_welcome', set_welcome_start),
        CallbackQueryHandler(set_welcome_start, pattern="^admin_welcome_set$")
    ],
    states={
        MEDIA: [MessageHandler(filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.TEXT & ~filters.COMMAND, receive_media), CommandHandler('skip', receive_media)],
        TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)],
        BUTTONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_buttons), CommandHandler('skip', receive_buttons)],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
    # Removed per_message=False to fix warning
)