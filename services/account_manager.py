import asyncio
from typing import Dict, List, Optional
from .telethon_worker import TelethonWorker
from .logger import log
from utils.buffer import Buffer
from config import API_ID, API_HASH
from database.crud import get_account, update_account_status
from database.models import SessionLocal, Account, Task, Script
from services.persona_service import should_use_evasive_reply, get_evasive_reply
from services.excel_crm import ExcelCRMService


class AccountManager:
    def __init__(self):
        self.workers: Dict[str, TelethonWorker] = {}
        self.buffers: Dict[str, Buffer] = {}
        self.pending_codes: Dict[str, asyncio.Future] = {}
        self.dialog_histories: Dict[str, Dict[str, List[str]]] = {}

    def _cache_history(self, phone: str, user_id: str, history: List[str]):
        self.dialog_histories.setdefault(phone, {})[user_id] = history.copy()

    async def message_handler(self, acc_phone, event):
        """Метод класса для обработки входящих сообщений"""
        try:
            if not event.sender_id:
                return

            sender = await event.get_sender()

            user_id = str(event.sender_id)
            username = sender.username or "нет username"
            first_name = getattr(sender, "first_name", None)
            last_name = getattr(sender, "last_name", None)
            sender_phone = getattr(sender, "phone", None)
            text = event.raw_text or ""

            print(f"📥 Сообщение для {acc_phone} от @{username}: {text[:50]}...")
            await log(acc_phone, f"📨 Сообщение от @{username} ({user_id}): {text[:50]}...")

            db = SessionLocal()
            from database.crud import add_dialog_message, get_dialog_history, get_or_create_contact

            active_task = db.query(Task).filter(
                Task.status == "running",
                Task.accounts.contains(acc_phone)
            ).order_by(Task.created_at.desc()).first()

            source_task_id = active_task.id if active_task else None
            contact = get_or_create_contact(
                db,
                account_phone=acc_phone,
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                phone=sender_phone,
                source_task_id=source_task_id,
            )
            ExcelCRMService().upsert_contact(contact)
            add_dialog_message(db, acc_phone, user_id, "user", text)
            history = get_dialog_history(db, acc_phone, user_id, limit=40)
            db.close()

            self._cache_history(acc_phone, user_id, history)
            print(f"🧠 История диалога @{username}: {len(history)} сообщений")
            await log(acc_phone, f"🧠 В CRM сохранено сообщение. Всего записей: {len(history)}")

            await self.process_dialog(acc_phone, user_id, history, username)

        except Exception as e:
            print(f"❌ message_handler ERROR: {e}")
            import traceback
            traceback.print_exc()

    async def add_account(self, phone: str, proxy: Optional[str] = None, session_file: Optional[str] = None):
        if phone in self.workers:
            return False, "Уже запущен"

        worker = TelethonWorker(phone, API_ID, API_HASH, proxy, session_file)
        self.buffers[phone] = Buffer(delay=30)

        code_future = asyncio.Future()
        self.pending_codes[phone] = code_future

        async def code_callback():
            await log(phone, "📱 Требуется код подтверждения. Ожидаю ввода...")
            code = await code_future
            return code

        success, error = await worker.start(self.message_handler, code_callback)

        if phone in self.pending_codes:
            del self.pending_codes[phone]

        if success:
            self.workers[phone] = worker
            db = SessionLocal()
            update_account_status(db, phone, True)
            db.close()
            await log(phone, "✅ Аккаунт запущен")
            return True, "ОК"
        else:
            await log(phone, f"❌ Ошибка запуска: {error}")
            return False, error

    async def process_dialog(self, phone: str, user_id: str, messages: list, username: str):
        from services.openai_service import generate_response, analyze_dialog_status
        from database.crud import (
            get_dialog_by_user,
            create_dialog,
            update_dialog_status,
            add_dialog_message,
            update_contact_status,
            get_or_create_contact,
            get_contact,
        )

        print(f"🤖 process_dialog: phone={phone}, user_id={user_id}, username={username}, messages={len(messages)}")
        await log(phone, f"🤖 Генерация ответа для @{username} на {len(messages)} сообщений")

        db = SessionLocal()
        task = db.query(Task).filter(
            Task.status == "running",
            Task.accounts.contains(phone)
        ).order_by(Task.created_at.desc()).first()

        if not task:
            print(f"❌ process_dialog: Нет активной задачи для {phone}")
            await log(phone, f"❌ Нет активной задачи для аккаунта {phone}")
            db.close()
            return

        script = db.query(Script).filter(Script.id == task.script_id).first()
        if not script:
            db.close()
            print(f"❌ process_dialog: Скрипт не найден")
            await log(phone, f"❌ Скрипт не найден")
            return

        task_id = task.id
        script_prompt = script.prompt or ""
        script_first_message_value = script.first_message or ""
        contact = get_or_create_contact(
            db,
            account_phone=phone,
            user_id=user_id,
            username=username,
            source_task_id=task_id,
        )
        ExcelCRMService().upsert_contact(contact)
        persona_name = contact.persona_name or "специалист"
        persona_role = contact.persona_role or "специалист по откликам"
        persona_company = contact.persona_company or "JobWalker"
        db.close()

        latest_user_text = ""
        for line in reversed(messages):
            if line.startswith("Пользователь:"):
                latest_user_text = line.replace("Пользователь:", "", 1).strip()
                break

        if should_use_evasive_reply(latest_user_text):
            answer = get_evasive_reply()
            status = await analyze_dialog_status(messages)
            print("🤖 process_dialog: Использован evasive-ответ")
        else:
            script_first_message = script_first_message_value or f"Здравствуйте! Меня зовут {persona_name}, я {persona_role} в компании «{persona_company}»."
            answer, status = await generate_response(messages, script_prompt, script_first_message)

        print(f"🤖 process_dialog: Ответ={answer[:50]}..., статус={status}")
        status = await analyze_dialog_status(messages + [f"Бот: {answer}"])
        await log(phone, f"✅ Ответ сгенерирован (статус: {status})")

        worker = self.workers.get(phone)
        if worker:
            success = False

            if username and username != "нет username":
                try:
                    await worker.client.send_message(f"@{username}", answer)
                    success = True
                except Exception as e:
                    print(f"❌ Ошибка отправки по @{username}: {e}")

            if not success:
                try:
                    await worker.client.send_message(int(user_id), answer)
                    success = True
                except Exception as e:
                    print(f"❌ Ошибка отправки по ID {user_id}: {e}")

            if success:
                db = SessionLocal()
                add_dialog_message(db, phone, user_id, "bot", answer)
                history = self.dialog_histories.get(phone, {}).get(user_id, []).copy()
                history.append(f"Бот: {answer}")
                self._cache_history(phone, user_id, history)
                update_contact_status(db, phone, user_id, status)
                contact = get_contact(db, phone, user_id)
                ExcelCRMService().upsert_contact(contact)
                db.close()
                history_len = len(self.dialog_histories.get(phone, {}).get(user_id, []))
                print(f"📤 Ответ отправлен @{username}")
                await log(phone, f"📤 Ответ отправлен @{username}. История обновлена: {history_len} записей")
            else:
                print(f"❌ Не удалось отправить ответ @{username}")
                await log(phone, f"❌ Ошибка отправки ответа @{username}")

        db = SessionLocal()
        dialog = get_dialog_by_user(db, phone, user_id)
        if dialog:
            update_dialog_status(db, phone, user_id, status)
        else:
            create_dialog(db, phone, user_id, username)
            update_dialog_status(db, phone, user_id, status)
        db.close()

        from services.airtable_service import AirtableService
        airtable = AirtableService()
        if airtable.is_configured():
            airtable.save_dialog(phone, username, user_id, status, len(messages))

    async def stop_account(self, phone: str):
        if phone in self.workers:
            await self.workers[phone].stop()
            del self.workers[phone]
            if phone in self.buffers:
                del self.buffers[phone]
            if phone in self.dialog_histories:
                del self.dialog_histories[phone]

            db = SessionLocal()
            update_account_status(db, phone, False)
            db.close()

            await log(phone, "🛑 Аккаунт остановлен")
            return True, "ОК"
        return False, "Аккаунт не найден"

    async def stop_all(self):
        for phone in list(self.workers.keys()):
            await self.stop_account(phone)

    async def start_all_from_db(self):
        db = SessionLocal()
        accounts = db.query(Account).filter(Account.is_active == False).all()
        db.close()

        started = []
        for acc in accounts:
            success, msg = await self.add_account(acc.phone, acc.proxy, acc.session_file)
            if success:
                started.append(acc.phone)

        return started

    def get_active_accounts(self):
        return list(self.workers.keys())

    def is_account_running(self, phone: str):
        return phone in self.workers

    def has_pending_code(self, phone: str) -> bool:
        return phone in self.pending_codes

    def submit_code(self, phone: str, code: str):
        if phone in self.pending_codes:
            self.pending_codes[phone].set_result(code)
            return True
        return False
