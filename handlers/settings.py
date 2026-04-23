from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

# ========== СОСТОЯНИЯ ==========
class LogBotStates(StatesGroup):
    waiting_token = State()
    waiting_chat_id = State()

class OpenAIStates(StatesGroup):
    waiting_api_key = State()
    waiting_prompt_id = State()
    waiting_prompt_version = State()
    waiting_vector_store = State()
    waiting_first_message = State()

# ========== КЛАВИАТУРЫ ==========
def settings_menu():
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="📝 Бот для логов", callback_data="settings_logbot"),
        types.InlineKeyboardButton(text="🤖 OpenAI настройки", callback_data="settings_openai"),
        types.InlineKeyboardButton(text="📊 Airtable настройки", callback_data="settings_airtable"),
        types.InlineKeyboardButton(text="⏰ Follow-up настройки", callback_data="settings_followup"),
        types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")
    )
    builder.adjust(1)
    return builder.as_markup()

def logbot_menu():
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="🔑 Ввести токен", callback_data="logbot_set_token"),
        types.InlineKeyboardButton(text="💬 Ввести Chat ID", callback_data="logbot_set_chatid"),
        types.InlineKeyboardButton(text="📊 Показать настройки", callback_data="logbot_show"),
        types.InlineKeyboardButton(text="🔙 Назад", callback_data="settings")
    )
    builder.adjust(1)
    return builder.as_markup()

def back_to_logbot():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="settings_logbot"))
    return builder.as_markup()

def openai_menu():
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="🔑 API-ключ", callback_data="openai_set_key"),
        types.InlineKeyboardButton(text="📝 StorePromp ID", callback_data="openai_set_prompt"),
        types.InlineKeyboardButton(text="🔄 Версия промпта", callback_data="openai_set_version"),
        types.InlineKeyboardButton(text="📚 Vector Store ID", callback_data="openai_set_vector"),
        types.InlineKeyboardButton(text="💬 Первое сообщение", callback_data="openai_set_firstmsg"),
        types.InlineKeyboardButton(text="📊 Показать настройки", callback_data="openai_show"),
        types.InlineKeyboardButton(text="🔙 Назад", callback_data="settings")
    )
    builder.adjust(1)
    return builder.as_markup()

def back_to_openai():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="settings_openai"))
    return builder.as_markup()

# ========== ГЛАВНОЕ МЕНЮ НАСТРОЕК ==========
@router.callback_query(F.data == "settings")
async def settings_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "⚙️ Настройки\nВыберите раздел:",
        reply_markup=settings_menu()
    )
    await callback.answer()

# ========== НАСТРОЙКИ ЛОГ-БОТА ==========
@router.callback_query(F.data == "settings_logbot")
async def settings_logbot(callback: types.CallbackQuery):
    from database.crud import get_setting
    from database.models import SessionLocal
    
    db = SessionLocal()
    token = get_setting(db, "log_bot_token")
    chat_id = get_setting(db, "log_chat_id")
    db.close()
    
    token_status = "✅ установлен" if token else "❌ не установлен"
    chat_status = "✅ установлен" if chat_id else "❌ не установлен"
    
    text = f"""📝 Настройка бота для логов

Статус:
🔑 Токен: {token_status}
💬 Chat ID: {chat_status}

Выберите действие:"""
    
    await callback.message.edit_text(text, reply_markup=logbot_menu())
    await callback.answer()

@router.callback_query(F.data == "logbot_set_token")
async def logbot_set_token(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔑 Введите токен бота для логов\n\n"
        "Пример: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz\n\n"
        "Получить токен можно у @BotFather",
        reply_markup=back_to_logbot()
    )
    await state.set_state(LogBotStates.waiting_token)
    await callback.answer()

@router.message(LogBotStates.waiting_token)
async def process_logbot_token(message: types.Message, state: FSMContext):
    from database.crud import save_setting
    from database.models import SessionLocal
    
    token = message.text.strip()
    
    db = SessionLocal()
    save_setting(db, "log_bot_token", token)
    db.close()
    
    await message.answer(
        f"✅ Токен сохранен!\n\n`{token[:15]}...{token[-10:]}`",
        parse_mode="Markdown"
    )
    await state.clear()
    
    from database.crud import get_setting
    db = SessionLocal()
    chat_id = get_setting(db, "log_chat_id")
    db.close()
    
    token_status = "✅ установлен"
    chat_status = "✅ установлен" if chat_id else "❌ не установлен"
    
    text = f"""📝 Настройка бота для логов

Статус:
🔑 Токен: {token_status}
💬 Chat ID: {chat_status}

Выберите действие:"""
    
    await message.answer(text, reply_markup=logbot_menu())

@router.callback_query(F.data == "logbot_set_chatid")
async def logbot_set_chatid(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💬 Введите Chat ID для логов\n\n"
        "Как узнать Chat ID:\n"
        "1. Добавьте бота @getmyid_bot в Telegram\n"
        "2. Напишите ему /start\n"
        "3. Он пришлет ваш Chat ID\n\n"
        "Пример: 7497345483",
        reply_markup=back_to_logbot()
    )
    await state.set_state(LogBotStates.waiting_chat_id)
    await callback.answer()

@router.message(LogBotStates.waiting_chat_id)
async def process_logbot_chatid(message: types.Message, state: FSMContext):
    from database.crud import save_setting
    from database.models import SessionLocal
    
    chat_id = message.text.strip()
    
    db = SessionLocal()
    save_setting(db, "log_chat_id", chat_id)
    db.close()
    
    await message.answer(f"✅ Chat ID сохранен: `{chat_id}`", parse_mode="Markdown")
    await state.clear()
    
    from database.crud import get_setting
    db = SessionLocal()
    token = get_setting(db, "log_bot_token")
    db.close()
    
    token_status = "✅ установлен" if token else "❌ не установлен"
    chat_status = "✅ установлен"
    
    text = f"""📝 Настройка бота для логов

Статус:
🔑 Токен: {token_status}
💬 Chat ID: {chat_status}

Выберите действие:"""
    
    await message.answer(text, reply_markup=logbot_menu())

@router.callback_query(F.data == "logbot_show")
async def logbot_show(callback: types.CallbackQuery):
    from database.crud import get_setting
    from database.models import SessionLocal
    
    db = SessionLocal()
    token = get_setting(db, "log_bot_token") or "не установлен"
    chat_id = get_setting(db, "log_chat_id") or "не установлен"
    db.close()
    
    if token != "не установлен":
        token = f"{token[:15]}...{token[-10:]}"
    
    text = f"""📊 Текущие настройки лог-бота

🔑 Токен: {token}
💬 Chat ID: {chat_id}"""
    
    await callback.message.edit_text(text, reply_markup=back_to_logbot())
    await callback.answer()

# ========== OPENAI НАСТРОЙКИ ==========
@router.callback_query(F.data == "settings_openai")
async def settings_openai(callback: types.CallbackQuery):
    from database.crud import get_setting
    from database.models import SessionLocal
    
    db = SessionLocal()
    api_key = get_setting(db, "openai_api_key")
    prompt_id = get_setting(db, "openai_prompt_id")
    db.close()
    
    key_status = "✅ установлен" if api_key else "❌ не установлен"
    prompt_status = "✅ установлен" if prompt_id else "❌ не установлен"
    
    text = f"""🤖 Настройки OpenAI

Статус:
🔑 API Key: {key_status}
📝 StorePromp ID: {prompt_status}

Выберите параметр для настройки:
• API-ключ - ключ доступа к OpenAI API
• StorePromp ID - ID промпта из OpenAI Dashboard
• Первое сообщение - текст для начала диалога"""
    
    await callback.message.edit_text(text, reply_markup=openai_menu())
    await callback.answer()

@router.callback_query(F.data == "openai_set_key")
async def openai_set_key(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔑 Введите OpenAI API ключ\n\n"
        "Формат: sk-proj-...\n\n"
        "Получить ключ можно в OpenAI Dashboard:\n"
        "https://platform.openai.com/api-keys",
        reply_markup=back_to_openai()
    )
    await state.set_state(OpenAIStates.waiting_api_key)
    await callback.answer()

@router.message(OpenAIStates.waiting_api_key)
async def process_openai_key(message: types.Message, state: FSMContext):
    from database.crud import save_setting
    from database.models import SessionLocal
    
    api_key = message.text.strip()
    
    db = SessionLocal()
    save_setting(db, "openai_api_key", api_key)
    db.close()
    
    masked = f"{api_key[:20]}...{api_key[-10:]}" if len(api_key) > 30 else api_key
    await message.answer(f"✅ API ключ сохранен!\n\n`{masked}`", parse_mode="Markdown")
    await state.clear()
    
    await message.answer("🤖 Настройки OpenAI", reply_markup=openai_menu())

@router.callback_query(F.data == "openai_set_prompt")
async def openai_set_prompt(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Введите StorePromp ID\n\n"
        "Создать промпт можно в OpenAI Dashboard:\n"
        "https://platform.openai.com/prompts",
        reply_markup=back_to_openai()
    )
    await state.set_state(OpenAIStates.waiting_prompt_id)
    await callback.answer()

@router.message(OpenAIStates.waiting_prompt_id)
async def process_openai_prompt(message: types.Message, state: FSMContext):
    from database.crud import save_setting
    from database.models import SessionLocal
    
    prompt_id = message.text.strip()
    
    db = SessionLocal()
    save_setting(db, "openai_prompt_id", prompt_id)
    db.close()
    
    await message.answer(f"✅ StorePromp ID сохранен!\n\n`{prompt_id}`", parse_mode="Markdown")
    await state.clear()
    await message.answer("🤖 Настройки OpenAI", reply_markup=openai_menu())

@router.callback_query(F.data == "openai_set_version")
async def openai_set_version(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔄 Введите версию промпта\n\n"
        "Например: 1 или 2\n"
        "Оставьте пустым для использования последней версии",
        reply_markup=back_to_openai()
    )
    await state.set_state(OpenAIStates.waiting_prompt_version)
    await callback.answer()

@router.message(OpenAIStates.waiting_prompt_version)
async def process_openai_version(message: types.Message, state: FSMContext):
    from database.crud import save_setting
    from database.models import SessionLocal
    
    version = message.text.strip()
    
    db = SessionLocal()
    save_setting(db, "openai_prompt_version", version)
    db.close()
    
    await message.answer(f"✅ Версия промпта сохранена: {version}")
    await state.clear()
    await message.answer("🤖 Настройки OpenAI", reply_markup=openai_menu())

@router.callback_query(F.data == "openai_set_vector")
async def openai_set_vector(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📚 Введите Vector Store ID\n\n"
        "Используется для RAG FileSearch",
        reply_markup=back_to_openai()
    )
    await state.set_state(OpenAIStates.waiting_vector_store)
    await callback.answer()

@router.message(OpenAIStates.waiting_vector_store)
async def process_openai_vector(message: types.Message, state: FSMContext):
    from database.crud import save_setting
    from database.models import SessionLocal
    
    vector_id = message.text.strip()
    
    db = SessionLocal()
    save_setting(db, "openai_vector_store", vector_id)
    db.close()
    
    await message.answer(f"✅ Vector Store ID сохранен!")
    await state.clear()
    await message.answer("🤖 Настройки OpenAI", reply_markup=openai_menu())

@router.callback_query(F.data == "openai_set_firstmsg")
async def openai_set_firstmsg(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💬 Введите первое сообщение (приветствие)\n\n"
        "Пример:\n"
        "Привет! Меня зовут Анна. Я специалист компании...",
        reply_markup=back_to_openai()
    )
    await state.set_state(OpenAIStates.waiting_first_message)
    await callback.answer()

@router.message(OpenAIStates.waiting_first_message)
async def process_openai_firstmsg(message: types.Message, state: FSMContext):
    from database.crud import save_setting
    from database.models import SessionLocal
    
    first_msg = message.text.strip()
    
    db = SessionLocal()
    save_setting(db, "openai_first_message", first_msg)
    db.close()
    
    await message.answer(f"✅ Первое сообщение сохранено!\n\n{first_msg[:100]}...")
    await state.clear()
    await message.answer("🤖 Настройки OpenAI", reply_markup=openai_menu())

@router.callback_query(F.data == "openai_show")
async def openai_show(callback: types.CallbackQuery):
    from database.crud import get_setting
    from database.models import SessionLocal
    
    db = SessionLocal()
    api_key = get_setting(db, "openai_api_key") or "не установлен"
    prompt_id = get_setting(db, "openai_prompt_id") or "не установлен"
    version = get_setting(db, "openai_prompt_version") or "не установлена"
    vector = get_setting(db, "openai_vector_store") or "не установлен"
    first_msg = get_setting(db, "openai_first_message") or "не установлено"
    db.close()
    
    if api_key != "не установлен" and len(api_key) > 30:
        api_key = f"{api_key[:20]}...{api_key[-10:]}"
    
    text = f"""📊 Текущие настройки OpenAI

🔑 API Key: {api_key}
📝 StorePromp ID: {prompt_id}
🔄 Версия: {version}
📚 Vector Store ID: {vector}
💬 Первое сообщение: {first_msg[:50] if first_msg != "не установлено" else first_msg}..."""
    
    await callback.message.edit_text(text, reply_markup=back_to_openai())
    await callback.answer()

# ========== AIRTABLE НАСТРОЙКИ ==========
class AirtableStates(StatesGroup):
    waiting_api_key = State()
    waiting_base_id = State()
    waiting_table_id = State()

def airtable_menu():
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="🔑 API Key", callback_data="airtable_set_key"),
        types.InlineKeyboardButton(text="📁 Base ID", callback_data="airtable_set_base"),
        types.InlineKeyboardButton(text="📊 Table ID", callback_data="airtable_set_table"),
        types.InlineKeyboardButton(text="📈 Показать настройки", callback_data="airtable_show"),
        types.InlineKeyboardButton(text="🔙 Назад", callback_data="settings")
    )
    builder.adjust(1)
    return builder.as_markup()

def back_to_airtable():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="settings_airtable"))
    return builder.as_markup()

@router.callback_query(F.data == "settings_airtable")
async def settings_airtable(callback: types.CallbackQuery):
    from database.crud import get_setting
    from database.models import SessionLocal
    
    db = SessionLocal()
    api_key = get_setting(db, "airtable_api_key")
    base_id = get_setting(db, "airtable_base_id")
    table_id = get_setting(db, "airtable_table_id")
    db.close()
    
    key_status = "✅ установлен" if api_key else "❌ не установлен"
    base_status = "✅ установлен" if base_id else "❌ не установлен"
    table_status = "✅ установлен" if table_id else "❌ не установлен"
    
    text = f"""📊 Настройки Airtable

Статус:
🔑 API Key: {key_status}
📁 Base ID: {base_status}
📊 Table ID: {table_status}

Выберите параметр для настройки."""
    
    await callback.message.edit_text(text, reply_markup=airtable_menu())
    await callback.answer()

@router.callback_query(F.data == "airtable_set_key")
async def airtable_set_key(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔑 Введите Airtable API Key\n\n"
        "Получить можно на https://airtable.com/create/tokens\n"
        "Нужны права: data.records:write, data.records:read",
        reply_markup=back_to_airtable()
    )
    await state.set_state(AirtableStates.waiting_api_key)
    await callback.answer()

@router.message(AirtableStates.waiting_api_key)
async def process_airtable_key(message: types.Message, state: FSMContext):
    from database.crud import save_setting
    from database.models import SessionLocal
    
    api_key = message.text.strip()
    
    db = SessionLocal()
    save_setting(db, "airtable_api_key", api_key)
    db.close()
    
    masked = f"{api_key[:10]}...{api_key[-5:]}" if len(api_key) > 15 else api_key
    await message.answer(f"✅ API Key сохранен: `{masked}`", parse_mode="Markdown")
    await state.clear()
    await message.answer("📊 Настройки Airtable", reply_markup=airtable_menu())

@router.callback_query(F.data == "airtable_set_base")
async def airtable_set_base(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📁 Введите Airtable Base ID\n\n"
        "Найти можно в URL вашей базы:\n"
        "https://airtable.com/appXXXXXXXXX",
        reply_markup=back_to_airtable()
    )
    await state.set_state(AirtableStates.waiting_base_id)
    await callback.answer()

@router.message(AirtableStates.waiting_base_id)
async def process_airtable_base(message: types.Message, state: FSMContext):
    from database.crud import save_setting
    from database.models import SessionLocal
    
    base_id = message.text.strip()
    
    db = SessionLocal()
    save_setting(db, "airtable_base_id", base_id)
    db.close()
    
    await message.answer(f"✅ Base ID сохранен: `{base_id}`", parse_mode="Markdown")
    await state.clear()
    await message.answer("📊 Настройки Airtable", reply_markup=airtable_menu())

@router.callback_query(F.data == "airtable_set_table")
async def airtable_set_table(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📊 Введите Airtable Table ID (имя таблицы)\n\n"
        "Например: Dialogs или Table 1",
        reply_markup=back_to_airtable()
    )
    await state.set_state(AirtableStates.waiting_table_id)
    await callback.answer()

@router.message(AirtableStates.waiting_table_id)
async def process_airtable_table(message: types.Message, state: FSMContext):
    from database.crud import save_setting
    from database.models import SessionLocal
    
    table_id = message.text.strip()
    
    db = SessionLocal()
    save_setting(db, "airtable_table_id", table_id)
    db.close()
    
    await message.answer(f"✅ Table ID сохранен: `{table_id}`", parse_mode="Markdown")
    await state.clear()
    await message.answer("📊 Настройки Airtable", reply_markup=airtable_menu())

@router.callback_query(F.data == "airtable_show")
async def airtable_show(callback: types.CallbackQuery):
    from database.crud import get_setting
    from database.models import SessionLocal
    
    db = SessionLocal()
    api_key = get_setting(db, "airtable_api_key") or "не установлен"
    base_id = get_setting(db, "airtable_base_id") or "не установлен"
    table_id = get_setting(db, "airtable_table_id") or "не установлена"
    db.close()
    
    if api_key != "не установлен" and len(api_key) > 15:
        api_key = f"{api_key[:10]}...{api_key[-5:]}"
    
    text = f"""📊 Текущие настройки Airtable

🔑 API Key: {api_key}
📁 Base ID: {base_id}
📊 Table ID: {table_id}"""
    
    await callback.message.edit_text(text, reply_markup=back_to_airtable())
    await callback.answer()

# ========== FOLLOW-UP НАСТРОЙКИ (ЗАГЛУШКА) ==========
@router.callback_query(F.data == "settings_followup")
async def settings_followup(callback: types.CallbackQuery):
    await callback.answer("🔧 Follow-up настройки в разработке", show_alert=True)