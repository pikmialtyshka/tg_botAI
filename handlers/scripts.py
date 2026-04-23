from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

class ScriptStates(StatesGroup):
    waiting_name = State()
    waiting_first_message = State()
    waiting_prompt = State()

def scripts_menu():
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="➕ Создать скрипт", callback_data="script_create"),
        types.InlineKeyboardButton(text="📋 Мои скрипты", callback_data="script_list"),
        types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")
    )
    builder.adjust(1)
    return builder.as_markup()

def back_to_scripts():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="scripts"))
    return builder.as_markup()

@router.callback_query(F.data == "scripts")
async def scripts_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📋 Скрипты\n\nЗдесь вы можете создавать и управлять скриптами для нейро-диалогов.\n\n"
        "Скрипт содержит:\n"
        "• Название\n"
        "• Первое сообщение (приветствие)\n"
        "• Промпт (инструкция для ИИ)",
        reply_markup=scripts_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "script_create")
async def script_create(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Создание нового скрипта\n\n"
        "Шаг 1/3\n"
        "Введите название скрипта:\n"
        "Например: JobWalker Анна",
        reply_markup=back_to_scripts()
    )
    await state.set_state(ScriptStates.waiting_name)
    await callback.answer()

@router.message(ScriptStates.waiting_name)
async def process_script_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    
    await message.answer(
        "💬 Шаг 2/3\n\n"
        "Введите первое сообщение (приветствие):\n\n"
        "Пример:\n"
        "Приветствую!\n"
        "Меня зовут Анна, я специалист по направлению оценки клиентского сервиса в компании «JobWalker».\n"
        "Мы зарегистрировали ваш отклик на подработку — пишу по поводу возможного трудоустройства.\n\n"
        "Вышлю Вам условия для ознакомления?",
        reply_markup=back_to_scripts()
    )
    await state.set_state(ScriptStates.waiting_first_message)

@router.message(ScriptStates.waiting_first_message)
async def process_script_firstmsg(message: types.Message, state: FSMContext):
    await state.update_data(first_message=message.text.strip())
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="📝 Ввести текстом", callback_data="prompt_text"))
    builder.add(types.InlineKeyboardButton(text="📎 Загрузить файл .txt", callback_data="prompt_file"))
    builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="scripts"))
    builder.adjust(1)
    
    await message.answer(
        "🤖 Шаг 3/3\n\n"
        "Как хотите ввести промпт?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ScriptStates.waiting_prompt)

@router.callback_query(F.data == "prompt_text")
async def prompt_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Введите промпт (инструкцию) для ИИ текстом:\n\n"
        "Можно отправить длинное сообщение — бот примет все части.",
        reply_markup=back_to_scripts()
    )
    await state.set_state(ScriptStates.waiting_prompt)
    await callback.answer()

@router.callback_query(F.data == "prompt_file")
async def prompt_file(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📎 Отправьте файл .txt с промптом\n\n"
        "Просто перетащите файл в чат или выберите через скрепку.",
        reply_markup=back_to_scripts()
    )
    await state.set_state(ScriptStates.waiting_prompt)
    await callback.answer()

@router.message(ScriptStates.waiting_prompt)
async def process_script_prompt(message: types.Message, state: FSMContext):
    from database.crud import save_script
    from database.models import SessionLocal
    
    prompt_text = ""
    
    if message.document:
        import aiofiles
        import os
        
        file_id = message.document.file_id
        file = await message.bot.get_file(file_id)
        file_path = file.file_path
        
        await message.bot.download_file(file_path, f"temp_prompt_{message.from_user.id}.txt")
        
        async with aiofiles.open(f"temp_prompt_{message.from_user.id}.txt", "r", encoding="utf-8") as f:
            prompt_text = await f.read()
        
        os.remove(f"temp_prompt_{message.from_user.id}.txt")
    else:
        prompt_text = message.text.strip()
    
    if not prompt_text:
        await message.answer("❌ Промпт пустой. Попробуйте снова.")
        return
    
    data = await state.get_data()
    name = data.get("name")
    first_message = data.get("first_message")
    
    db = SessionLocal()
    save_script(db, name, first_message, prompt_text)
    db.close()
    
    preview = prompt_text[:200] + "..." if len(prompt_text) > 200 else prompt_text
    
    await message.answer(
        f"✅ Скрипт сохранен!\n\n"
        f"📌 Название: {name}\n"
        f"💬 Первое сообщение: {first_message[:50]}...\n"
        f"📝 Промпт ({len(prompt_text)} символов): {preview}"
    )
    await state.clear()
    await message.answer("📋 Скрипты", reply_markup=scripts_menu())

@router.callback_query(F.data == "script_list")
async def script_list(callback: types.CallbackQuery):
    from database.crud import get_scripts
    from database.models import SessionLocal
    
    db = SessionLocal()
    scripts = get_scripts(db)
    db.close()
    
    if not scripts:
        text = "📋 У вас пока нет скриптов.\nНажмите «Создать скрипт» чтобы добавить."
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="scripts"))
        builder.adjust(1)
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    else:
        text = "📋 Ваши скрипты:\n\n"
        for i, s in enumerate(scripts, 1):
            text += f"{i}. {s.name}\n"
        text += "\nНажмите на скрипт чтобы посмотреть детали."
        
        builder = InlineKeyboardBuilder()
        for s in scripts:
            builder.add(types.InlineKeyboardButton(
                text=f"📌 {s.name}", 
                callback_data=f"script_view_{s.id}"
            ))
        builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="scripts"))
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    
    await callback.answer()

@router.callback_query(F.data.startswith("script_view_"))
async def script_view(callback: types.CallbackQuery):
    from database.crud import get_script
    from database.models import SessionLocal
    
    script_id = int(callback.data.split("_")[2])
    
    db = SessionLocal()
    script = get_script(db, script_id)
    db.close()
    
    if script:
        text = f"""📌 Скрипт: {script.name}

💬 Первое сообщение:
{script.first_message}

📝 Промпт:
{script.prompt[:500]}..."""

        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(
            text="🚀 Запустить задачу", 
            callback_data=f"script_run_{script.id}"
        ))
        builder.add(types.InlineKeyboardButton(
            text="🗑 Удалить", 
            callback_data=f"script_delete_{script.id}"
        ))
        builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="script_list"))
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await callback.answer("Скрипт не найден", show_alert=True)
    
    await callback.answer()

@router.callback_query(F.data.startswith("script_run_"))
async def script_run(callback: types.CallbackQuery):
    await callback.answer("🚀 Запуск задачи будет доступен в следующем обновлении", show_alert=True)

@router.callback_query(F.data.startswith("script_delete_"))
async def script_delete(callback: types.CallbackQuery):
    from database.crud import delete_script
    from database.models import SessionLocal
    
    script_id = int(callback.data.split("_")[2])
    
    db = SessionLocal()
    delete_script(db, script_id)
    db.close()
    
    await callback.answer("✅ Скрипт удален")
    await script_list(callback)