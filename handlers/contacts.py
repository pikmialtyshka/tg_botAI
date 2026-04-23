from datetime import datetime
from pathlib import Path
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import SessionLocal
from database.crud import get_contacts_page, get_contact, get_dialog_messages_page, get_all_dialog_messages, get_contact_stats
from services.excel_crm import ExcelCRMService

router = Router()
PER_PAGE = 15
DIALOGS_PER_PAGE = 12
EXPORTS_DIR = Path('exports')

STATUS_ICONS = {
    'согласился': '🟢',
    'отказался': '🔴',
    'не ответил': '🟡',
    'новый': '⚪',
}


def _safe_name(contact):
    full_name = ' '.join(part for part in [contact.first_name, contact.last_name] if part).strip()
    return full_name or '-'


def _safe_username(contact):
    return f'@{contact.username}' if contact.username else str(contact.user_id)


@router.callback_query(F.data == 'contacts')
async def contacts_list(callback: types.CallbackQuery, page: int = 1):
    db = SessionLocal()
    try:
        contacts, total_pages = get_contacts_page(db, page=page, per_page=PER_PAGE)
    finally:
        db.close()

    builder = InlineKeyboardBuilder()
    if not contacts:
        builder.row(types.InlineKeyboardButton(text='📊 Статистика', callback_data='contacts_stats'))
        builder.row(types.InlineKeyboardButton(text='📤 Скачать Excel CRM', callback_data='contacts_export_excel'))
        builder.row(types.InlineKeyboardButton(text='🔙 Назад', callback_data='back'))
        await callback.message.edit_text('📒 Контакты пока пусты.', reply_markup=builder.as_markup())
        await callback.answer()
        return

    text = f"📒 Контакты CRM ({page}/{total_pages})\n\n"
    for contact in contacts:
        icon = STATUS_ICONS.get(contact.status, '⚪')
        text += f"{icon} {_safe_username(contact)} — {_safe_name(contact)} — {contact.status}\n"
        builder.row(types.InlineKeyboardButton(text=f'{icon} {_safe_username(contact)}', callback_data=f'contact_view_{contact.account_phone}|{contact.user_id}'))

    nav = []
    if page > 1:
        nav.append(types.InlineKeyboardButton(text='⬅️', callback_data=f'contacts_page_{page-1}'))
    nav.append(types.InlineKeyboardButton(text=f'{page}/{total_pages}', callback_data='ignore'))
    if page < total_pages:
        nav.append(types.InlineKeyboardButton(text='➡️', callback_data=f'contacts_page_{page+1}'))
    if nav:
        builder.row(*nav)
    builder.row(types.InlineKeyboardButton(text='📊 Статистика', callback_data='contacts_stats'))
    builder.row(types.InlineKeyboardButton(text='📤 Скачать Excel CRM', callback_data='contacts_export_excel'))
    builder.row(types.InlineKeyboardButton(text='🔙 Назад', callback_data='back'))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()




@router.callback_query(F.data == 'contacts_stats')
async def contacts_stats(callback: types.CallbackQuery):
    db = SessionLocal()
    try:
        stats = get_contact_stats(db)
    finally:
        db.close()

    total = stats['total']
    agreed = stats['agreed']
    declined = stats['declined']
    no_response = stats['no_response']

    def pct(value: int) -> float:
        return round((value / total) * 100, 2) if total else 0.0

    text = (
        '📊 Статистика CRM\n\n'
        f'Всего контактов: {total}\n\n'
        f'🟢 Согласился: {agreed} ({pct(agreed):.2f}%)\n'
        f'🔴 Отказался: {declined} ({pct(declined):.2f}%)\n'
        f'🟡 Не ответил: {no_response} ({pct(no_response):.2f}%)'
    )

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text='📤 Скачать Excel CRM', callback_data='contacts_export_excel'))
    builder.row(types.InlineKeyboardButton(text='🔙 К контактам', callback_data='contacts'))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith('contacts_page_'))
async def contacts_page(callback: types.CallbackQuery):
    page = int(callback.data.split('_')[-1])
    await contacts_list(callback, page)


@router.callback_query(F.data == 'contacts_export_excel')
async def contacts_export_excel(callback: types.CallbackQuery):
    service = ExcelCRMService()
    service.ensure_workbook()
    document = types.FSInputFile(service.FILE_PATH)
    await callback.message.answer_document(document=document, caption='📊 CRM-таблица')
    await callback.answer('Excel отправлен')


@router.callback_query(F.data.startswith('contact_view_'))
async def contact_view(callback: types.CallbackQuery):
    payload = callback.data.replace('contact_view_', '', 1)
    account_phone, user_id = payload.split('|', 1)
    db = SessionLocal()
    try:
        contact = get_contact(db, account_phone, user_id)
        messages, total_pages = get_dialog_messages_page(db, account_phone, user_id, page=1, per_page=DIALOGS_PER_PAGE)
    finally:
        db.close()

    if not contact:
        await callback.answer('Контакт не найден', show_alert=True)
        return

    await _render_contact(callback, contact, messages, 1, total_pages)


@router.callback_query(F.data.startswith('contact_export_dialog_'))
async def contact_export_dialog(callback: types.CallbackQuery):
    payload = callback.data.replace('contact_export_dialog_', '', 1)
    account_phone, user_id = payload.split('|', 1)
    db = SessionLocal()
    try:
        contact = get_contact(db, account_phone, user_id)
        messages = get_all_dialog_messages(db, account_phone, user_id)
    finally:
        db.close()

    if not contact:
        await callback.answer('Контакт не найден', show_alert=True)
        return

    EXPORTS_DIR.mkdir(exist_ok=True)
    safe_username = (contact.username or str(contact.user_id)).replace('@', '')
    file_path = EXPORTS_DIR / f'dialog_{account_phone}_{safe_username}.txt'

    lines = [
        'Выгрузка диалога',
        f'Аккаунт: {contact.account_phone}',
        f'Username: {_safe_username(contact)}',
        f'Имя: {_safe_name(contact)}',
        f'Статус: {contact.status}',
        '',
        'Диалог:',
        ''
    ]

    for item in messages:
        who = 'Пользователь' if item.role == 'user' else 'Бот' if item.role == 'bot' else 'Система'
        ts = item.created_at.strftime('%d.%m.%Y %H:%M:%S') if isinstance(item.created_at, datetime) else str(item.created_at)
        lines.append(f'[{ts}] {who}: {item.text}')

    file_path.write_text('\n'.join(lines), encoding='utf-8')
    document = types.FSInputFile(file_path)
    await callback.message.answer_document(document=document, caption=f'📄 Диалог {_safe_username(contact)}')
    await callback.answer('Диалог выгружен')


@router.callback_query(F.data.startswith('contact_dialog_'))
async def contact_dialog_page(callback: types.CallbackQuery):
    payload = callback.data.replace('contact_dialog_', '', 1)
    account_phone, user_id, page_str = payload.split('|', 2)
    page = int(page_str)
    db = SessionLocal()
    try:
        contact = get_contact(db, account_phone, user_id)
        messages, total_pages = get_dialog_messages_page(db, account_phone, user_id, page=page, per_page=DIALOGS_PER_PAGE)
    finally:
        db.close()

    if not contact:
        await callback.answer('Контакт не найден', show_alert=True)
        return

    await _render_contact(callback, contact, messages, page, total_pages)


async def _render_contact(callback: types.CallbackQuery, contact, messages, page: int, total_pages: int):
    lines = []
    for item in reversed(messages):
        who = '👤' if item.role == 'user' else '🤖' if item.role == 'bot' else '⚙️'
        ts = item.created_at.strftime('%d.%m %H:%M') if isinstance(item.created_at, datetime) else str(item.created_at)
        lines.append(f'{ts} {who} {item.text}')
    history_block = '\n\n'.join(lines) if lines else 'Сообщений пока нет'

    updated = contact.updated_at.strftime('%d.%m.%Y %H:%M') if contact.updated_at else '-'
    text = (
        f'👤 Контакт\n\n'
        f'Username: {_safe_username(contact)}\n'
        f'Имя: {_safe_name(contact)}\n'
        f'Статус: {contact.status}\n'
        f'Аккаунт: {contact.account_phone}\n'
        f'Последняя активность: {updated}\n\n'
        f'💬 Диалог ({page}/{total_pages})\n\n{history_block}'
    )

    builder = InlineKeyboardBuilder()
    nav = []
    if page > 1:
        nav.append(types.InlineKeyboardButton(text='⬅️', callback_data=f'contact_dialog_{contact.account_phone}|{contact.user_id}|{page-1}'))
    nav.append(types.InlineKeyboardButton(text=f'{page}/{total_pages}', callback_data='ignore'))
    if page < total_pages:
        nav.append(types.InlineKeyboardButton(text='➡️', callback_data=f'contact_dialog_{contact.account_phone}|{contact.user_id}|{page+1}'))
    if nav:
        builder.row(*nav)
    builder.row(
        types.InlineKeyboardButton(text='📄 Выгрузить диалог', callback_data=f'contact_export_dialog_{contact.account_phone}|{contact.user_id}'),
        types.InlineKeyboardButton(text='📤 Excel CRM', callback_data='contacts_export_excel')
    )
    builder.row(types.InlineKeyboardButton(text='🔙 К контактам', callback_data='contacts'))
    await callback.message.edit_text(text[:4000], reply_markup=builder.as_markup())
    await callback.answer()
