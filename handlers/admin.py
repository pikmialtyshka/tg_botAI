from aiogram import Router, F, types
from aiogram.filters import Command
from keyboards.main import main_menu

router = Router()


@router.message(Command('start'))
async def cmd_start(message: types.Message):
    await message.answer('👋 Главное меню\nВыберите действие:', reply_markup=main_menu())


@router.callback_query(F.data == 'back')
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text('👋 Главное меню\nВыберите действие:', reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == 'new_task')
async def new_task(callback: types.CallbackQuery):
    await callback.message.edit_text(
        '🚀 Задачи\n\nСоздание, остановка и очистка списка задач.',
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text='🚀 Новая задача', callback_data='task_create')],
            [types.InlineKeyboardButton(text='📋 Мои задачи', callback_data='task_list')],
            [types.InlineKeyboardButton(text='⏹ Остановить активные', callback_data='task_stop_all')],
            [types.InlineKeyboardButton(text='🧹 Очистить завершённые', callback_data='task_clear_finished')],
            [types.InlineKeyboardButton(text='🗑 Сбросить список задач', callback_data='task_clear_all')],
            [types.InlineKeyboardButton(text='🔙 Назад', callback_data='back')],
        ])
    )
    await callback.answer()


@router.message(Command('test'))
async def cmd_test(message: types.Message):
    import __main__
    if not hasattr(__main__, 'account_manager'):
        await message.answer('❌ Менеджер аккаунтов не найден')
        return
    account_manager = __main__.account_manager
    active = account_manager.get_active_accounts()
    if not active:
        await message.answer('❌ Нет запущенных аккаунтов')
        return
    phone = active[0]
    worker = account_manager.workers[phone]
    try:
        await worker.client.send_message('me', '🧪 Тестовое сообщение от бота!')
        await message.answer(f'✅ Тест отправлен с {phone} в Избранное')
    except Exception as e:
        await message.answer(f'❌ Ошибка отправки: {e}')
