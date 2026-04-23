import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database.models import init_db, SessionLocal
from database.crud import get_contacts
from handlers import admin, accounts, tasks, settings, scripts, contacts
from services.account_manager import AccountManager
from services.task_runner import TaskRunner
from services.excel_crm import ExcelCRMService
from services.followup_service import FollowUpService

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

init_db()
excel_crm = ExcelCRMService()
excel_crm.ensure_workbook()
_db = SessionLocal()
try:
    excel_crm.sync_all_contacts(get_contacts(_db))
finally:
    _db.close()

account_manager = AccountManager()
task_runner = TaskRunner(account_manager)
followup_service = FollowUpService(account_manager)

import handlers.accounts
import handlers.tasks
handlers.accounts.account_manager = account_manager
handlers.tasks.account_manager = account_manager
handlers.tasks.task_runner = task_runner


dp.include_router(admin.router)
dp.include_router(accounts.router)
dp.include_router(tasks.router)
dp.include_router(contacts.router)
dp.include_router(settings.router)
dp.include_router(scripts.router)


async def main():
    print('🚀 Бот запускается...')
    started = await account_manager.start_all_from_db()
    if started:
        print(f'✅ Автозапуск {len(started)} аккаунтов')
    await followup_service.start()
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print('👋 Бот остановлен')
    finally:
        await followup_service.stop()
        await account_manager.stop_all()


if __name__ == '__main__':
    asyncio.run(main())
