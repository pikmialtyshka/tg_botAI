from datetime import datetime
from aiogram import Bot
from config import LOG_BOT_TOKEN, LOG_CHAT_ID

_log_bot = None
_logging_disabled = False


def _get_bot():
    global _log_bot
    if _log_bot is None and LOG_BOT_TOKEN:
        try:
            _log_bot = Bot(token=LOG_BOT_TOKEN)
        except Exception:
            _log_bot = None
    return _log_bot


async def log(account, text):
    global _logging_disabled
    now = datetime.now().strftime('%H:%M:%S')
    message = f'👤 Аккаунт: {account}\n\nℹ️ [{now}] {text}\n'

    if _logging_disabled:
        print(f'📝 LOG: [{account}] {text}')
        return

    bot = _get_bot()
    chat_id = LOG_CHAT_ID
    if bot and chat_id:
        try:
            if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
                chat_id = int(chat_id)
            await bot.send_message(chat_id, message)
            return
        except Exception as e:
            error_text = str(e)
            print(f'📝 LOG SEND ERROR: {e}')
            if 'chat not found' in error_text.lower() or 'bot was blocked by the user' in error_text.lower():
                _logging_disabled = True
                print('📝 Логирование в Telegram отключено до исправления LOG_CHAT_ID или прав бота.')
    print(f'📝 LOG: [{account}] {text}')
