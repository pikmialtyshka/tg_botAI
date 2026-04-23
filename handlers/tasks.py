from aiogram import Router, F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiofiles
import os
import json

router = Router()
account_manager = None
task_runner = None

async def safe_edit_message(message, text, reply_markup=None):
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if 'message is not modified' in str(e).lower():
            return
        raise


class TaskStates(StatesGroup):
    waiting_script = State()
    waiting_accounts = State()
    waiting_recipients = State()
    waiting_confirm = State()


def tasks_menu():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text='🚀 Новая задача', callback_data='task_create'))
    builder.row(types.InlineKeyboardButton(text='📋 Мои задачи', callback_data='task_list'))
    builder.row(
        types.InlineKeyboardButton(text='⏹ Остановить активные', callback_data='task_stop_all'),
        types.InlineKeyboardButton(text='🧹 Очистить завершённые', callback_data='task_clear_finished'),
    )
    builder.row(types.InlineKeyboardButton(text='🗑 Сбросить список задач', callback_data='task_clear_all'))
    builder.row(types.InlineKeyboardButton(text='🔙 Назад', callback_data='back'))
    return builder.as_markup()


def back_to_tasks():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text='🔙 Назад', callback_data='new_task'))
    return builder.as_markup()


def build_tasks_list_markup(tasks):
    builder = InlineKeyboardBuilder()
    for task in tasks[:20]:
        status_icon = {'running': '🟢', 'pending': '🟡', 'stopped': '⏹', 'failed': '🔴', 'completed': '✅'}.get(task.status, '⚪')
        builder.add(types.InlineKeyboardButton(text=f'{status_icon} Задача #{task.id}', callback_data=f'task_view_{task.id}'))
    builder.row(
        types.InlineKeyboardButton(text='⏹ Остановить активные', callback_data='task_stop_all'),
        types.InlineKeyboardButton(text='🧹 Очистить завершённые', callback_data='task_clear_finished'),
    )
    builder.row(types.InlineKeyboardButton(text='🗑 Сбросить список задач', callback_data='task_clear_all'))
    builder.row(types.InlineKeyboardButton(text='🔙 Назад', callback_data='new_task'))
    builder.adjust(1)
    return builder.as_markup()


def build_task_details_markup(task):
    builder = InlineKeyboardBuilder()
    if task.status in {'running', 'pending'}:
        builder.row(types.InlineKeyboardButton(text='⏹ Остановить задачу', callback_data=f'task_stop_{task.id}'))
    builder.row(types.InlineKeyboardButton(text='🗑 Удалить задачу', callback_data=f'task_delete_{task.id}'))
    builder.row(types.InlineKeyboardButton(text='📋 К списку задач', callback_data='task_list'))
    builder.row(types.InlineKeyboardButton(text='🔙 Назад', callback_data='new_task'))
    return builder.as_markup()


async def _show_task(callback: types.CallbackQuery, task):
    accounts = json.loads(task.accounts or '[]')
    recipients = json.loads(task.recipients or '[]')
    text = (
        f'📌 Задача #{task.id}\n\n'
        f'Статус: {task.status}\n'
        f'Аккаунтов: {len(accounts)}\n'
        f'Получателей: {len(recipients)}\n'
        f'Отправлено: {task.sent_count}\n'
        f'Ошибок: {task.error_count}\n'
        f'Создана: {task.created_at.strftime("%d.%m.%Y %H:%M")}'
    )
    await safe_edit_message(callback.message, text, reply_markup=build_task_details_markup(task))


@router.callback_query(F.data == 'new_task')
async def new_task_handler(callback: types.CallbackQuery):
    await safe_edit_message(callback.message, '🚀 Задачи\n\nСоздание, остановка и очистка списка задач.', reply_markup=tasks_menu())
    await callback.answer()


@router.callback_query(F.data == 'task_create')
async def task_create(callback: types.CallbackQuery, state: FSMContext):
    from database.crud import get_scripts
    from database.models import SessionLocal
    db = SessionLocal()
    try:
        scripts = get_scripts(db)
    finally:
        db.close()
    if not scripts:
        await safe_edit_message(callback.message, '❌ У вас нет скриптов. Сначала создайте скрипт в разделе 📋 Скрипты.', reply_markup=back_to_tasks())
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    for s in scripts:
        builder.add(types.InlineKeyboardButton(text=f'📌 {s.name}', callback_data=f'task_script_{s.id}'))
    builder.add(types.InlineKeyboardButton(text='🔙 Назад', callback_data='new_task'))
    builder.adjust(1)
    await safe_edit_message(callback.message, '📝 Выберите скрипт для задачи:', reply_markup=builder.as_markup())
    await state.set_state(TaskStates.waiting_script)
    await callback.answer()


@router.callback_query(F.data.startswith('task_script_'))
async def task_select_script(callback: types.CallbackQuery, state: FSMContext):
    script_id = int(callback.data.replace('task_script_', ''))
    await state.update_data(script_id=script_id)
    active_accounts = account_manager.get_active_accounts() if account_manager else []
    if not active_accounts:
        await safe_edit_message(callback.message, '❌ Нет запущенных аккаунтов. Сначала запустите аккаунты в разделе 👥 Аккаунты.', reply_markup=back_to_tasks())
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    for phone in active_accounts:
        builder.add(types.InlineKeyboardButton(text=f'📱 {phone}', callback_data=f'task_acc_{phone}'))
    builder.add(types.InlineKeyboardButton(text='✅ Выбрать все', callback_data='task_acc_all'))
    builder.add(types.InlineKeyboardButton(text='▶️ Продолжить', callback_data='task_acc_done'))
    builder.add(types.InlineKeyboardButton(text='🔙 Назад', callback_data='task_create'))
    builder.adjust(1)
    await state.update_data(selected_accounts=[])
    await safe_edit_message(callback.message, f'📱 Выберите аккаунты для задачи\n\nДоступно: {len(active_accounts)}\nВыбрано: 0', reply_markup=builder.as_markup())
    await state.set_state(TaskStates.waiting_accounts)
    await callback.answer()


@router.callback_query(F.data == 'task_acc_all')
async def task_select_all_accounts(callback: types.CallbackQuery, state: FSMContext):
    active_accounts = account_manager.get_active_accounts()
    await state.update_data(selected_accounts=active_accounts.copy())
    builder = InlineKeyboardBuilder()
    for p in active_accounts:
        builder.add(types.InlineKeyboardButton(text=f'✅ 📱 {p}', callback_data=f'task_acc_{p}'))
    builder.add(types.InlineKeyboardButton(text='✅ Выбрать все', callback_data='task_acc_all'))
    builder.add(types.InlineKeyboardButton(text='▶️ Продолжить', callback_data='task_acc_done'))
    builder.add(types.InlineKeyboardButton(text='🔙 Назад', callback_data='task_create'))
    builder.adjust(1)
    await safe_edit_message(callback.message, f'📱 Выберите аккаунты для задачи\n\nДоступно: {len(active_accounts)}\nВыбрано: {len(active_accounts)}', reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith('task_acc_') & ~F.data.in_({'task_acc_all', 'task_acc_done'}))
async def task_toggle_account(callback: types.CallbackQuery, state: FSMContext):
    phone = callback.data.replace('task_acc_', '')
    data = await state.get_data()
    selected = data.get('selected_accounts', [])
    if phone in selected:
        selected.remove(phone)
    else:
        selected.append(phone)
    await state.update_data(selected_accounts=selected)
    active_accounts = account_manager.get_active_accounts()
    builder = InlineKeyboardBuilder()
    for p in active_accounts:
        mark = '✅ ' if p in selected else ''
        builder.add(types.InlineKeyboardButton(text=f'{mark}📱 {p}', callback_data=f'task_acc_{p}'))
    builder.add(types.InlineKeyboardButton(text='✅ Выбрать все', callback_data='task_acc_all'))
    builder.add(types.InlineKeyboardButton(text='▶️ Продолжить', callback_data='task_acc_done'))
    builder.add(types.InlineKeyboardButton(text='🔙 Назад', callback_data='task_create'))
    builder.adjust(1)
    await safe_edit_message(callback.message, f'📱 Выберите аккаунты для задачи\n\nДоступно: {len(active_accounts)}\nВыбрано: {len(selected)}', reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == 'task_acc_done')
async def task_accounts_done(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get('selected_accounts', [])
    if not selected:
        await callback.answer('Выберите хотя бы один аккаунт', show_alert=True)
        return
    await safe_edit_message(callback.message, '📎 Отправьте список получателей\n\nМожно отправить текстом по одному в строке или загрузить файл .txt.', reply_markup=back_to_tasks())
    await state.set_state(TaskStates.waiting_recipients)
    await callback.answer()


@router.message(TaskStates.waiting_recipients)
async def task_recipients(message: types.Message, state: FSMContext):
    recipients = []
    if message.document:
        file = await message.bot.get_file(message.document.file_id)
        temp_file = f'temp_recipients_{message.from_user.id}.txt'
        await message.bot.download_file(file.file_path, temp_file)
        async with aiofiles.open(temp_file, 'r', encoding='utf-8') as f:
            recipients = [r.strip() for r in (await f.read()).split('\n') if r.strip()]
        os.remove(temp_file)
    else:
        recipients = [r.strip() for r in message.text.strip().split('\n') if r.strip()]
    if not recipients:
        await message.answer('❌ Список получателей пуст', reply_markup=back_to_tasks())
        return
    await state.update_data(recipients=recipients)
    data = await state.get_data()
    await message.answer(
        f'✅ Проверьте данные задачи:\n\nАккаунтов: {len(data.get("selected_accounts", []))}\nПолучателей: {len(recipients)}\n\nПодтвердить создание?',
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text='✅ Создать задачу', callback_data='task_confirm')],
            [types.InlineKeyboardButton(text='🔙 Назад', callback_data='new_task')],
        ])
    )
    await state.set_state(TaskStates.waiting_confirm)


@router.callback_query(F.data == 'task_confirm')
async def task_confirm(callback: types.CallbackQuery, state: FSMContext):
    from database.crud import create_task
    from database.models import SessionLocal
    data = await state.get_data()
    db = SessionLocal()
    try:
        task = create_task(db, data['script_id'], data['selected_accounts'], data['recipients'])
    finally:
        db.close()
    started = await task_runner.start_task(task.id) if task_runner else False
    await state.clear()
    if started:
        await safe_edit_message(callback.message, f'✅ Задача #{task.id} создана и запущена.', reply_markup=tasks_menu())
    else:
        await safe_edit_message(callback.message, f'⚠️ Задача #{task.id} создана, но не запустилась автоматически.', reply_markup=tasks_menu())
    await callback.answer()


@router.callback_query(F.data == 'task_list')
async def task_list(callback: types.CallbackQuery):
    from database.crud import get_tasks
    from database.models import SessionLocal
    db = SessionLocal()
    try:
        tasks = get_tasks(db)
    finally:
        db.close()
    if not tasks:
        await safe_edit_message(callback.message, '📋 Список задач пуст.', reply_markup=tasks_menu())
    else:
        lines = ['📋 Мои задачи\n']
        for task in tasks[:20]:
            lines.append(f'#{task.id} — {task.status} | отправлено: {task.sent_count} | ошибок: {task.error_count}')
        await safe_edit_message(callback.message, '\n'.join(lines), reply_markup=build_tasks_list_markup(tasks))
    await callback.answer()


@router.callback_query(F.data.startswith('task_view_'))
async def task_view(callback: types.CallbackQuery):
    from database.crud import get_task
    from database.models import SessionLocal
    task_id = int(callback.data.split('_')[-1])
    db = SessionLocal()
    try:
        task = get_task(db, task_id)
    finally:
        db.close()
    if not task:
        await callback.answer('Задача не найдена', show_alert=True)
        return
    await _show_task(callback, task)
    await callback.answer()


@router.callback_query(F.data.startswith('task_stop_') & ~F.data.in_({'task_stop_all'}))
async def task_stop(callback: types.CallbackQuery):
    from database.crud import get_task, update_task_status
    from database.models import SessionLocal
    task_id = int(callback.data.split('_')[-1])
    stopped = await task_runner.stop_task(task_id) if task_runner else False
    if not stopped:
        db = SessionLocal()
        try:
            update_task_status(db, task_id, 'stopped')
        finally:
            db.close()
    db = SessionLocal()
    try:
        task = get_task(db, task_id)
    finally:
        db.close()
    if task:
        await _show_task(callback, task)
    else:
        await safe_edit_message(callback.message, '⏹ Задача остановлена.', reply_markup=tasks_menu())
    await callback.answer('Задача остановлена')


@router.callback_query(F.data == 'task_stop_all')
async def task_stop_all(callback: types.CallbackQuery):
    from database.crud import get_tasks, update_task_status
    from database.models import SessionLocal
    stopped_count = 0
    running_ids = list(task_runner.running_tasks.keys()) if task_runner else []
    for task_id in running_ids:
        if await task_runner.stop_task(task_id):
            stopped_count += 1
    db = SessionLocal()
    try:
        tasks = get_tasks(db)
        for task in tasks:
            if task.status in {'running', 'pending'}:
                update_task_status(db, task.id, 'stopped')
    finally:
        db.close()
    await callback.answer(f'Остановлено: {stopped_count}')
    await task_list(callback)


@router.callback_query(F.data == 'task_clear_finished')
async def task_clear_finished(callback: types.CallbackQuery):
    from database.crud import delete_finished_tasks
    from database.models import SessionLocal
    db = SessionLocal()
    try:
        count = delete_finished_tasks(db)
    finally:
        db.close()
    await callback.answer(f'Удалено задач: {count}')
    await task_list(callback)


@router.callback_query(F.data == 'task_clear_all')
async def task_clear_all(callback: types.CallbackQuery):
    from database.crud import clear_tasks
    from database.models import SessionLocal
    if task_runner:
        for task_id in list(task_runner.running_tasks.keys()):
            await task_runner.stop_task(task_id)
    db = SessionLocal()
    try:
        count = clear_tasks(db)
    finally:
        db.close()
    await callback.answer(f'Список задач очищен: {count}')
    await safe_edit_message(callback.message, '🗑 Все задачи удалены.', reply_markup=tasks_menu())


@router.callback_query(F.data.startswith('task_delete_'))
async def task_delete(callback: types.CallbackQuery):
    from database.crud import delete_task
    from database.models import SessionLocal
    task_id = int(callback.data.split('_')[-1])
    if task_runner and task_id in task_runner.running_tasks:
        await task_runner.stop_task(task_id)
    db = SessionLocal()
    try:
        delete_task(db, task_id)
    finally:
        db.close()
    await callback.answer('Задача удалена')
    await task_list(callback)
