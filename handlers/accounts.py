from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import json
import zipfile
import os
import aiofiles
import shutil

router = Router()
account_manager = None
PER_PAGE = 10


class AccountStates(StatesGroup):
    waiting_zip = State()
    waiting_proxy = State()
    waiting_bulk_proxy = State()
    waiting_code = State()


def back_to_accounts():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text='🔙 Назад', callback_data='accounts'))
    return builder.as_markup()


def account_detail_menu(phone: str, is_active: bool, pending_code: bool = False):
    builder = InlineKeyboardBuilder()
    if is_active:
        builder.row(types.InlineKeyboardButton(text='⏹️ Остановить', callback_data=f'acc_stop_{phone}'))
    else:
        builder.row(types.InlineKeyboardButton(text='▶️ Запустить', callback_data=f'acc_start_{phone}'))
    if pending_code:
        builder.row(types.InlineKeyboardButton(text='📱 Ввести код', callback_data=f'acc_code_{phone}'))
    builder.row(types.InlineKeyboardButton(text='🌐 Сменить прокси', callback_data=f'acc_proxy_{phone}'))
    builder.row(types.InlineKeyboardButton(text='🗑 Удалить аккаунт', callback_data=f'acc_delete_{phone}'))
    builder.row(types.InlineKeyboardButton(text='🔙 К списку', callback_data='accounts'))
    return builder.as_markup()


async def render_accounts(callback: types.CallbackQuery, page: int = 1):
    from database.crud import get_accounts
    from database.models import SessionLocal

    db = SessionLocal()
    try:
        all_accounts = get_accounts(db)
    finally:
        db.close()

    total_pages = max(1, (len(all_accounts) + PER_PAGE - 1) // PER_PAGE)
    page = min(max(page, 1), total_pages)
    accounts = all_accounts[(page - 1) * PER_PAGE: page * PER_PAGE]

    if not accounts:
        text = (
            '📱 Список аккаунтов пуст\n\n'
            'Добавьте аккаунты через ZIP архив.\n\n'
            'Архив должен содержать пары файлов:\n'
            '• {phone}.session — файл сессии\n'
            '• {phone}.json — конфигурация аккаунта\n\n'
            'Пример JSON:\n'
            '{\n  "phone": "+79961030783",\n  "proxy": "socks5://user:pass@ip:port"\n}'
        )
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text='➕ Добавить аккаунт из ZIP', callback_data='add_account_zip'))
        builder.row(
            types.InlineKeyboardButton(text='▶️ Запустить все', callback_data='start_all_accounts'),
            types.InlineKeyboardButton(text='⏹️ Остановить все', callback_data='stop_all_accounts'),
        )
        builder.row(types.InlineKeyboardButton(text='🌐 Всем новый прокси', callback_data='acc_bulk_proxy'))
        builder.row(types.InlineKeyboardButton(text='🔙 Назад', callback_data='back'))
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        return

    text = f'📱 Аккаунты (страница {page}/{total_pages})\n\nНажми на номер, чтобы сразу запустить аккаунт.\nКнопка ℹ️ открывает карточку с деталями.\n\n'
    builder = InlineKeyboardBuilder()
    for acc in accounts:
        running = account_manager.is_account_running(acc.phone) if account_manager else acc.is_active
        status_icon = '🟢' if running else '🔴'
        proxy_icon = '🌐' if acc.proxy else '⚪'
        text += f'{status_icon} {acc.phone} {proxy_icon}\n'
        builder.row(
            types.InlineKeyboardButton(text=f'{status_icon} {acc.phone}', callback_data=f'acc_quick_{acc.phone}'),
            types.InlineKeyboardButton(text='ℹ️', callback_data=f'acc_view_{acc.phone}')
        )

    if total_pages > 1:
        nav = []
        if page > 1:
            nav.append(types.InlineKeyboardButton(text='⬅️', callback_data=f'acc_page_{page-1}'))
        nav.append(types.InlineKeyboardButton(text=f'{page}/{total_pages}', callback_data='ignore'))
        if page < total_pages:
            nav.append(types.InlineKeyboardButton(text='➡️', callback_data=f'acc_page_{page+1}'))
        builder.row(*nav)

    builder.row(types.InlineKeyboardButton(text='➕ Добавить из ZIP', callback_data='add_account_zip'))
    builder.row(
        types.InlineKeyboardButton(text='▶️ Запустить все', callback_data='start_all_accounts'),
        types.InlineKeyboardButton(text='⏹️ Остановить все', callback_data='stop_all_accounts'),
    )
    builder.row(types.InlineKeyboardButton(text='🌐 Всем новый прокси', callback_data='acc_bulk_proxy'))
    builder.row(types.InlineKeyboardButton(text='🔙 Назад', callback_data='back'))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == 'accounts')
async def accounts_list(callback: types.CallbackQuery):
    await render_accounts(callback, 1)
    await callback.answer()


@router.callback_query(F.data.startswith('acc_page_'))
async def accounts_page(callback: types.CallbackQuery):
    page = int(callback.data.split('_')[2])
    await render_accounts(callback, page)
    await callback.answer()


@router.callback_query(F.data == 'ignore')
async def ignore(callback: types.CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == 'add_account_zip')
async def add_account_zip(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        '📦 Отправьте ZIP архив с аккаунтами\n\n'
        'Архив должен содержать пары файлов:\n'
        '• {phone}.session — файл сессии\n'
        '• {phone}.json — конфигурация\n\n'
        'Пример JSON:\n'
        '{\n  "phone": "+79961030783",\n  "proxy": "socks5://user:pass@ip:port"\n}\n',
        reply_markup=back_to_accounts(),
    )
    await state.set_state(AccountStates.waiting_zip)
    await callback.answer()


@router.message(AccountStates.waiting_zip)
async def process_zip(message: types.Message, state: FSMContext):
    from database.crud import create_account, get_account
    from database.models import SessionLocal

    if not message.document or not message.document.file_name.endswith('.zip'):
        await message.answer('❌ Отправьте ZIP файл', reply_markup=back_to_accounts())
        return

    await message.answer('⏳ Обрабатываю архив...')
    file = await message.bot.get_file(message.document.file_id)
    zip_path = f'temp_accounts_{message.from_user.id}.zip'
    await message.bot.download_file(file.file_path, zip_path)

    db = SessionLocal()
    added, skipped, errors = [], [], []
    extract_path = f'temp_extract_{message.from_user.id}'

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        accounts_data = {}
        for filename in os.listdir(extract_path):
            if filename.endswith('.session'):
                phone = filename[:-8]
                accounts_data.setdefault(phone, {})['session'] = filename
            elif filename.endswith('.json'):
                phone = filename[:-5]
                accounts_data.setdefault(phone, {})['json'] = filename

        os.makedirs('sessions', exist_ok=True)
        for phone, files_dict in accounts_data.items():
            if not files_dict.get('session') or not files_dict.get('json'):
                skipped.append(phone)
                continue
            json_path = os.path.join(extract_path, files_dict['json'])
            async with aiofiles.open(json_path, 'r', encoding='utf-8') as f:
                data = json.loads(await f.read())
            proxy = data.get('proxy', '')
            phone_from_json = data.get('phone', phone)
            if not phone_from_json.startswith('+'):
                phone_from_json = '+' + phone_from_json
            session_src = os.path.join(extract_path, files_dict['session'])
            session_dst = os.path.join('sessions', files_dict['session'])
            shutil.copy2(session_src, session_dst)
            existing = get_account(db, phone_from_json)
            if existing:
                existing.proxy = proxy
                existing.session_file = session_dst
                db.commit()
                added.append(f'{phone_from_json} (обновлён)')
            else:
                acc = create_account(db, phone_from_json, proxy)
                acc.session_file = session_dst
                db.commit()
                added.append(phone_from_json)
    except Exception as e:
        errors.append(str(e))
    finally:
        db.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path, ignore_errors=True)

    text = f'✅ Добавлено/обновлено: {len(added)}\n⏭ Пропущено: {len(skipped)}'
    if added:
        text += '\n\n' + '\n'.join(added[:15])
    if errors:
        text += '\n\n❌ Ошибки:\n' + '\n'.join(errors[:5])
    await message.answer(text)
    await state.clear()
    await message.answer('📱 Аккаунты', reply_markup=back_to_accounts())


@router.callback_query(F.data.startswith('acc_quick_'))
async def account_quick(callback: types.CallbackQuery):
    phone = callback.data.replace('acc_quick_', '')
    if not account_manager:
        await callback.answer('Менеджер аккаунтов не инициализирован', show_alert=True)
        return
    if account_manager.is_account_running(phone):
        await callback.answer('Аккаунт уже активен')
        return
    from database.crud import get_account
    from database.models import SessionLocal
    db = SessionLocal()
    try:
        account = get_account(db, phone)
    finally:
        db.close()
    if not account:
        await callback.answer('Аккаунт не найден', show_alert=True)
        return
    await callback.answer(f'🚀 Запускаю {phone}...')
    success, msg = await account_manager.add_account(phone, account.proxy, account.session_file)
    if success:
        await callback.message.answer(f'✅ Аккаунт {phone} запущен')
    else:
        await callback.message.answer(f'❌ Ошибка запуска {phone}: {msg}')
    await render_accounts(callback, 1)


@router.callback_query(F.data.startswith('acc_view_'))
async def account_view(callback: types.CallbackQuery):
    from database.crud import get_account
    from database.models import SessionLocal

    phone = callback.data.replace('acc_view_', '')
    db = SessionLocal()
    try:
        account = get_account(db, phone)
    finally:
        db.close()
    if not account:
        await callback.answer('Аккаунт не найден', show_alert=True)
        return

    is_active = account_manager.is_account_running(phone) if account_manager else account.is_active
    pending_code = account_manager.has_pending_code(phone) if account_manager else False
    proxy_info = account.proxy or 'не указан'
    session_status = '✅ Есть' if account.session_file and os.path.exists(account.session_file) else '❌ Отсутствует'
    text = (
        f'👤 Аккаунт: {phone}\n'
        f'📊 Статус: {'🟢 Активен' if is_active else '🔴 Остановлен'}\n'
        f'🌐 Прокси: {proxy_info}\n'
        f'📁 Сессия: {session_status}\n'
        f'📅 Добавлен: {account.created_at.strftime("%d.%m.%Y %H:%M")}'
    )
    if pending_code:
        text += '\n\n⚠️ Ожидается код подтверждения.'
    await callback.message.edit_text(text, reply_markup=account_detail_menu(phone, is_active, pending_code))
    await callback.answer()


@router.callback_query(F.data.startswith('acc_start_'))
async def account_start(callback: types.CallbackQuery):
    phone = callback.data.replace('acc_start_', '')
    if not account_manager:
        await callback.answer('Менеджер аккаунтов не инициализирован', show_alert=True)
        return
    from database.crud import get_account
    from database.models import SessionLocal
    db = SessionLocal()
    try:
        account = get_account(db, phone)
    finally:
        db.close()
    if not account:
        await callback.answer('Аккаунт не найден', show_alert=True)
        return
    await callback.answer(f'🚀 Запускаю {phone}...')
    success, msg = await account_manager.add_account(phone, account.proxy, account.session_file)
    if success:
        await callback.message.answer(f'✅ Аккаунт {phone} запущен')
    else:
        await callback.message.answer(f'❌ Ошибка запуска {phone}: {msg}')
    callback.data = f'acc_view_{phone}'
    await account_view(callback)


@router.callback_query(F.data.startswith('acc_stop_'))
async def account_stop(callback: types.CallbackQuery):
    phone = callback.data.replace('acc_stop_', '')
    if not account_manager:
        await callback.answer('Менеджер аккаунтов не инициализирован', show_alert=True)
        return
    await callback.answer(f'🛑 Останавливаю {phone}...')
    success, msg = await account_manager.stop_account(phone)
    if success:
        await callback.message.answer(f'✅ Аккаунт {phone} остановлен')
    else:
        await callback.message.answer(f'❌ Ошибка остановки {phone}: {msg}')
    callback.data = f'acc_view_{phone}'
    await account_view(callback)


@router.callback_query(F.data == 'start_all_accounts')
async def start_all_accounts(callback: types.CallbackQuery):
    if not account_manager:
        await callback.answer('Менеджер аккаунтов не инициализирован', show_alert=True)
        return
    await callback.answer('🚀 Запускаю все аккаунты...')
    started = await account_manager.start_all_from_db()
    await callback.message.answer(f'✅ Запущено аккаунтов: {len(started)}' if started else 'ℹ️ Нет аккаунтов для запуска')
    await render_accounts(callback, 1)


@router.callback_query(F.data == 'stop_all_accounts')
async def stop_all_accounts(callback: types.CallbackQuery):
    if not account_manager:
        await callback.answer('Менеджер аккаунтов не инициализирован', show_alert=True)
        return
    await callback.answer('🛑 Останавливаю все аккаунты...')
    await account_manager.stop_all()
    await callback.message.answer('✅ Все аккаунты остановлены')
    await render_accounts(callback, 1)


@router.callback_query(F.data.startswith('acc_code_'))
async def account_code(callback: types.CallbackQuery, state: FSMContext):
    phone = callback.data.replace('acc_code_', '')
    if not account_manager or not account_manager.has_pending_code(phone):
        await callback.answer('Нет ожидания кода для этого аккаунта', show_alert=True)
        return
    await state.update_data(code_phone=phone)
    await callback.message.edit_text(
        f'📱 Введите код подтверждения для {phone}:\n\nКод должен прийти в Telegram или SMS.',
        reply_markup=back_to_accounts(),
    )
    await state.set_state(AccountStates.waiting_code)
    await callback.answer()


@router.message(AccountStates.waiting_code)
async def process_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    phone = data.get('code_phone')
    code = message.text.strip()
    if not account_manager:
        await message.answer('❌ Менеджер не инициализирован')
        await state.clear()
        return
    if account_manager.submit_code(phone, code):
        await message.answer(f'✅ Код отправлен для {phone}')
    else:
        await message.answer(f'❌ Нет ожидания кода для {phone}')
    await state.clear()


@router.callback_query(F.data.startswith('acc_proxy_'))
async def account_proxy(callback: types.CallbackQuery, state: FSMContext):
    phone = callback.data.replace('acc_proxy_', '')
    await state.update_data(proxy_phone=phone)
    await callback.message.edit_text(
        f'🌐 Введите новый прокси для {phone}\n\nФормат: socks5://user:pass@ip:port',
        reply_markup=back_to_accounts(),
    )
    await state.set_state(AccountStates.waiting_proxy)
    await callback.answer()


@router.callback_query(F.data == 'acc_bulk_proxy')
async def account_bulk_proxy(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        '🌐 Введите новый прокси, который нужно применить ко всем аккаунтам.\n\nФормат: socks5://user:pass@ip:port',
        reply_markup=back_to_accounts(),
    )
    await state.set_state(AccountStates.waiting_bulk_proxy)
    await callback.answer()


@router.message(AccountStates.waiting_proxy)
async def process_proxy(message: types.Message, state: FSMContext):
    from database.crud import get_account
    from database.models import SessionLocal
    data = await state.get_data()
    phone = data.get('proxy_phone')
    proxy = message.text.strip()
    db = SessionLocal()
    try:
        account = get_account(db, phone)
        if account:
            account.proxy = proxy
            db.commit()
            await message.answer(f'✅ Прокси для {phone} обновлён')
        else:
            await message.answer('❌ Аккаунт не найден')
    finally:
        db.close()
    await state.clear()
    await message.answer('📱 Аккаунты', reply_markup=back_to_accounts())


@router.message(AccountStates.waiting_bulk_proxy)
async def process_bulk_proxy(message: types.Message, state: FSMContext):
    from database.crud import update_all_accounts_proxy
    from database.models import SessionLocal
    proxy = message.text.strip()
    db = SessionLocal()
    try:
        count = update_all_accounts_proxy(db, proxy)
    finally:
        db.close()
    await state.clear()
    await message.answer(f'✅ Прокси обновлён для {count} аккаунтов.\nℹ️ Для уже запущенных аккаунтов прокси применится после перезапуска.')
    await message.answer('📱 Аккаунты', reply_markup=back_to_accounts())


@router.callback_query(F.data.startswith('acc_delete_'))
async def account_delete(callback: types.CallbackQuery):
    phone = callback.data.replace('acc_delete_', '')
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text='✅ Да, удалить', callback_data=f'acc_delete_confirm_{phone}'),
        types.InlineKeyboardButton(text='❌ Отмена', callback_data=f'acc_view_{phone}'),
    )
    await callback.message.edit_text(
        f'⚠️ Удалить аккаунт {phone}?\n\nБудут удалены запись из БД и файл сессии.',
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith('acc_delete_confirm_'))
async def account_delete_confirm(callback: types.CallbackQuery):
    from database.crud import delete_account, get_account
    from database.models import SessionLocal
    phone = callback.data.replace('acc_delete_confirm_', '')
    if account_manager and account_manager.is_account_running(phone):
        await account_manager.stop_account(phone)
    db = SessionLocal()
    try:
        account = get_account(db, phone)
        if account and account.session_file and os.path.exists(account.session_file):
            try:
                os.remove(account.session_file)
            except OSError:
                pass
        delete_account(db, phone)
    finally:
        db.close()
    await callback.answer(f'✅ Аккаунт {phone} удалён', show_alert=True)
    await render_accounts(callback, 1)
