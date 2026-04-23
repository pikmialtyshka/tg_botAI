import asyncio
import json
from database.crud import (
    get_task,
    update_task_status,
    update_task_stats,
    get_script,
    get_or_create_contact,
    add_dialog_message,
)
from database.models import SessionLocal
from services.logger import log
from services.persona_service import choose_persona, render_first_message
from services.excel_crm import ExcelCRMService


class TaskRunner:
    def __init__(self, account_manager):
        self.account_manager = account_manager
        self.running_tasks = {}

    async def run_task(self, task_id: int):
        print(f"🔍 TaskRunner: Начинаю задачу {task_id}")
        db = SessionLocal()
        task = get_task(db, task_id)
        print(f"🔍 TaskRunner: task={task}, status={task.status if task else 'None'}")

        if not task or task.status != "pending":
            print(f"🔍 TaskRunner: Задача {task_id} не pending, выход")
            db.close()
            self.running_tasks.pop(task_id, None)
            return

        update_task_status(db, task_id, "running")
        print("🔍 TaskRunner: Статус обновлён на running")
        task_accounts_raw = task.accounts
        task_recipients_raw = task.recipients
        task_script_id = task.script_id
        script = get_script(db, task_script_id)
        print(f"🔍 TaskRunner: script после get_script = {script}")
        script_name = script.name if script else None
        script_first_message = script.first_message if script else None
        db.close()
        print("🔍 TaskRunner: БД закрыта")

        if not script:
            print(f"🔍 TaskRunner: Скрипт {task.script_id} не найден!")
            await log("SYSTEM", "❌ Скрипт не найден")
            db = SessionLocal()
            update_task_status(db, task_id, "failed")
            db.close()
            self.running_tasks.pop(task_id, None)
            return

        try:
            accounts = json.loads(task_accounts_raw)
            recipients = json.loads(task_recipients_raw)
            print("🔍 TaskRunner: JSON parsed OK")
        except Exception as e:
            print(f"🔍 TaskRunner: Ошибка парсинга JSON: {e}")
            print(f"🔍 TaskRunner: accounts raw = {task_accounts_raw}")
            print(f"🔍 TaskRunner: recipients raw = {task_recipients_raw}")
            await log("SYSTEM", f"❌ Ошибка JSON: {e}")
            db = SessionLocal()
            update_task_status(db, task_id, "failed")
            db.close()
            self.running_tasks.pop(task_id, None)
            return

        print(f"🔍 TaskRunner: Скрипт={script_name}, Аккаунты={accounts}, Получатели={recipients}")

        await log("SYSTEM", f"🚀 Запуск задачи #{task_id}: {script_name}")
        await log("SYSTEM", f"📱 Аккаунтов: {len(accounts)}, Получателей: {len(recipients)}")

        sent = 0
        errors = 0

        try:
            for i, recipient in enumerate(recipients):
                account_phone = accounts[i % len(accounts)]
                print(f"🔍 TaskRunner: Отправка с {account_phone} на {recipient}")

                if account_phone not in self.account_manager.workers:
                    print(f"🔍 TaskRunner: Аккаунт {account_phone} не запущен")
                    await log("SYSTEM", f"❌ Аккаунт {account_phone} не запущен")
                    errors += 1
                    continue

                worker = self.account_manager.workers[account_phone]
                persona = choose_persona()
                first_message = render_first_message(persona, script_first_message)

                try:
                    if recipient == "me":
                        await worker.client.send_message("me", first_message)
                        success = True
                        recipient_user_id = "me"
                        recipient_username = "me"
                    else:
                        success = await worker.send_message(recipient, first_message)
                        recipient_user_id = recipient
                        recipient_username = recipient if recipient.startswith("@") else None

                    if success:
                        sent += 1
                        print(f"🔍 TaskRunner: Успешно отправлено на {recipient}")
                        await log(account_phone, f"📤 Отправлено первое сообщение для {recipient}")

                        db = SessionLocal()
                        contact = get_or_create_contact(
                            db,
                            account_phone=account_phone,
                            user_id=str(recipient_user_id),
                            username=recipient_username,
                            source_task_id=task_id,
                            persona_name=persona.get("name"),
                            persona_role=persona.get("role"),
                            persona_company=persona.get("company"),
                        )
                        ExcelCRMService().upsert_contact(contact)
                        add_dialog_message(
                            db,
                            account_phone=account_phone,
                            user_id=str(recipient_user_id),
                            role="bot",
                            text=first_message,
                        )
                        db.close()
                    else:
                        errors += 1
                        print(f"🔍 TaskRunner: Ошибка отправки на {recipient}")
                        await log(account_phone, f"❌ Ошибка отправки для {recipient}")

                    await asyncio.sleep(2)

                except Exception as e:
                    errors += 1
                    print(f"🔍 TaskRunner: Исключение при отправке: {e}")
                    await log(account_phone, f"❌ Ошибка: {e}")

        except asyncio.CancelledError:
            print(f"🔍 TaskRunner: Задача {task_id} остановлена пользователем")
            db = SessionLocal()
            update_task_stats(db, task_id, sent, errors)
            update_task_status(db, task_id, "stopped")
            db.close()
            await log("SYSTEM", f"⏹ Задача #{task_id} остановлена. Отправлено: {sent}, Ошибок: {errors}")
            raise

        print(f"🔍 TaskRunner: Отправка завершена. Отправлено={sent}, Ошибок={errors}")

        db = SessionLocal()
        update_task_stats(db, task_id, sent, errors)
        db.close()

        await log(
            "SYSTEM",
            f"✅ Рассылка задачи #{task_id} завершена. Отправлено: {sent}, Ошибок: {errors}. Ожидание ответов..."
        )
        self.running_tasks.pop(task_id, None)

    async def start_task(self, task_id: int):
        print(f"🔍 TaskRunner: start_task вызван для {task_id}")
        if task_id in self.running_tasks:
            print(f"🔍 TaskRunner: Задача {task_id} уже выполняется")
            return False

        task = asyncio.create_task(self.run_task(task_id))
        self.running_tasks[task_id] = task
        return True

    async def stop_task(self, task_id: int):
        print(f"🔍 TaskRunner: stop_task вызван для {task_id}")
        running_task = self.running_tasks.get(task_id)
        if not running_task:
            return False

        running_task.cancel()
        try:
            await running_task
        except asyncio.CancelledError:
            pass
        finally:
            self.running_tasks.pop(task_id, None)

        return True
