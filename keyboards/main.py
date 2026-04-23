from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text='👥 Аккаунты', callback_data='accounts'),
        InlineKeyboardButton(text='📒 Контакты', callback_data='contacts'),
    )
    builder.row(
        InlineKeyboardButton(text='🚀 Задачи', callback_data='new_task'),
        InlineKeyboardButton(text='📋 Скрипты', callback_data='scripts'),
    )
    builder.row(
        InlineKeyboardButton(text='⚙️ Настройки', callback_data='settings'),
        InlineKeyboardButton(text='📊 Статистика', callback_data='contacts_stats'),
    )
    builder.row(
        InlineKeyboardButton(text='📤 Excel CRM', callback_data='contacts_export_excel'),
    )
    return builder.as_markup()


def back_button():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text='🔙 Назад', callback_data='back'))
    return builder.as_markup()
