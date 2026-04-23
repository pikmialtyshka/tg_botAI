from datetime import datetime
from typing import List, Optional
import json

from sqlalchemy.orm import Session

from .models import Account, Setting, Dialog, Script, Task, SessionLocal, Contact, DialogMessage

STATUS_NEW = 'новый'
STATUS_AGREED = 'согласился'
STATUS_DECLINED = 'отказался'
STATUS_NO_RESPONSE = 'не ответил'
VALID_CONTACT_STATUSES = {STATUS_NEW, STATUS_AGREED, STATUS_DECLINED, STATUS_NO_RESPONSE}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Accounts

def create_account(db: Session, phone: str, proxy: str = None) -> Account:
    account = Account(phone=phone, proxy=proxy)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_accounts(db: Session) -> List[Account]:
    return db.query(Account).order_by(Account.created_at.desc(), Account.id.desc()).all()


def get_account(db: Session, phone: str) -> Optional[Account]:
    return db.query(Account).filter(Account.phone == phone).first()


def update_account_status(db: Session, phone: str, is_active: bool):
    account = get_account(db, phone)
    if account:
        account.is_active = is_active
        db.commit()


def update_account(db: Session, phone: str, **kwargs):
    account = get_account(db, phone)
    if not account:
        return None
    for key, value in kwargs.items():
        if hasattr(account, key):
            setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return account


def update_all_accounts_proxy(db: Session, proxy: str) -> int:
    accounts = db.query(Account).all()
    for account in accounts:
        account.proxy = proxy
    db.commit()
    return len(accounts)


def delete_account(db: Session, phone: str):
    account = get_account(db, phone)
    if account:
        db.delete(account)
        db.commit()


# Settings

def save_setting(db: Session, key: str, value: str):
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.add(setting)
    db.commit()


def get_setting(db: Session, key: str) -> Optional[str]:
    setting = db.query(Setting).filter(Setting.key == key).first()
    return setting.value if setting else None


# Dialog header

def create_dialog(db: Session, account_phone: str, user_id: str, username: str = None):
    dialog = Dialog(account_phone=account_phone, user_id=user_id, username=username)
    db.add(dialog)
    db.commit()
    return dialog


def get_dialog_by_user(db: Session, account_phone: str, user_id: str) -> Optional[Dialog]:
    return db.query(Dialog).filter(Dialog.account_phone == account_phone, Dialog.user_id == user_id).first()


def update_dialog_status(db: Session, account_phone: str, user_id: str, status: str):
    dialog = get_dialog_by_user(db, account_phone, user_id)
    if dialog:
        dialog.status = normalize_status(status)
        db.commit()


# Contacts / CRM

def normalize_status(status: Optional[str]) -> str:
    value = (status or STATUS_NEW).strip().lower()
    mapping = {
        'interested': STATUS_AGREED,
        'interesred': STATUS_AGREED,
        'accepted': STATUS_AGREED,
        'active': STATUS_AGREED,
        'agree': STATUS_AGREED,
        'agreed': STATUS_AGREED,
        'согласен': STATUS_AGREED,
        'согласилась': STATUS_AGREED,
        'согласился': STATUS_AGREED,
        'decline': STATUS_DECLINED,
        'declined': STATUS_DECLINED,
        'refused': STATUS_DECLINED,
        'отказ': STATUS_DECLINED,
        'отказался': STATUS_DECLINED,
        'отказалась': STATUS_DECLINED,
        'нет': STATUS_DECLINED,
        'neutral': STATUS_NEW,
        'new': STATUS_NEW,
        'новый': STATUS_NEW,
        'new_status': STATUS_NEW,
        'no_response': STATUS_NO_RESPONSE,
        'не ответил': STATUS_NO_RESPONSE,
        'не ответила': STATUS_NO_RESPONSE,
    }
    return mapping.get(value, value if value in VALID_CONTACT_STATUSES else STATUS_NEW)


def get_or_create_contact(
    db: Session,
    account_phone: str,
    user_id: str,
    username: str = None,
    first_name: str = None,
    last_name: str = None,
    phone: str = None,
    source_task_id: int = None,
    persona_name: str = None,
    persona_role: str = None,
    persona_company: str = None,
) -> Contact:
    contact = db.query(Contact).filter(Contact.account_phone == account_phone, Contact.user_id == user_id).first()
    if not contact:
        contact = Contact(
            account_phone=account_phone,
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            display_contact=username or user_id,
            source_task_id=source_task_id,
            persona_name=persona_name,
            persona_role=persona_role,
            persona_company=persona_company,
            status=STATUS_NEW,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact

    changed = False
    for field, value in {
        'username': username,
        'first_name': first_name,
        'last_name': last_name,
        'source_task_id': source_task_id,
        'persona_name': persona_name,
        'persona_role': persona_role,
        'persona_company': persona_company,
    }.items():
        if value and getattr(contact, field) != value:
            setattr(contact, field, value)
            changed = True

    display_contact = username or contact.username or contact.user_id
    if display_contact != contact.display_contact:
        contact.display_contact = display_contact
        changed = True

    if changed:
        contact.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(contact)
    return contact


def get_contact(db: Session, account_phone: str, user_id: str) -> Optional[Contact]:
    return db.query(Contact).filter(Contact.account_phone == account_phone, Contact.user_id == user_id).first()


def get_contacts(db: Session) -> List[Contact]:
    return db.query(Contact).order_by(Contact.updated_at.desc().nullslast(), Contact.id.desc()).all()


def get_contacts_page(db: Session, page: int = 1, per_page: int = 15) -> tuple[list[Contact], int]:
    query = db.query(Contact).order_by(Contact.updated_at.desc().nullslast(), Contact.id.desc())
    total = query.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(page, 1), total_pages)
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total_pages

def get_contact_stats(db: Session) -> dict:
    contacts = db.query(Contact.status).all()
    total = len(contacts)
    stats = {
        'total': total,
        'agreed': 0,
        'declined': 0,
        'no_response': 0,
    }
    for (status,) in contacts:
        normalized = normalize_status(status)
        if normalized == STATUS_AGREED:
            stats['agreed'] += 1
        elif normalized == STATUS_DECLINED:
            stats['declined'] += 1
        elif normalized == STATUS_NO_RESPONSE:
            stats['no_response'] += 1
    return stats


def update_contact_status(db: Session, account_phone: str, user_id: str, status: str):
    contact = get_contact(db, account_phone, user_id)
    if contact:
        contact.status = normalize_status(status)
        contact.display_contact = contact.username or contact.user_id
        contact.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(contact)


def add_dialog_message(db: Session, account_phone: str, user_id: str, role: str, text: str) -> DialogMessage:
    message = DialogMessage(account_phone=account_phone, user_id=user_id, role=role, text=text)
    db.add(message)
    contact = get_or_create_contact(db, account_phone, user_id)
    now = datetime.utcnow()
    if role == 'user':
        contact.last_user_message_at = now
        if contact.status == STATUS_NO_RESPONSE:
            contact.status = STATUS_NEW
    elif role == 'bot':
        contact.last_bot_message_at = now
    contact.updated_at = now
    db.commit()
    db.refresh(message)
    return message


def get_dialog_history(db: Session, account_phone: str, user_id: str, limit: int = 30) -> List[str]:
    rows = (
        db.query(DialogMessage)
        .filter(DialogMessage.account_phone == account_phone, DialogMessage.user_id == user_id)
        .order_by(DialogMessage.created_at.asc(), DialogMessage.id.asc())
        .limit(limit)
        .all()
    )
    history = []
    for row in rows:
        prefix = 'Пользователь' if row.role == 'user' else 'Бот' if row.role == 'bot' else 'Система'
        history.append(f'{prefix}: {row.text}')
    return history


def get_dialog_messages(db: Session, account_phone: str, user_id: str, limit: int = 50) -> List[DialogMessage]:
    return (
        db.query(DialogMessage)
        .filter(DialogMessage.account_phone == account_phone, DialogMessage.user_id == user_id)
        .order_by(DialogMessage.created_at.desc(), DialogMessage.id.desc())
        .limit(limit)
        .all()
    )


def get_all_dialog_messages(db: Session, account_phone: str, user_id: str) -> List[DialogMessage]:
    return (
        db.query(DialogMessage)
        .filter(DialogMessage.account_phone == account_phone, DialogMessage.user_id == user_id)
        .order_by(DialogMessage.created_at.asc(), DialogMessage.id.asc())
        .all()
    )


def get_dialog_messages_page(db: Session, account_phone: str, user_id: str, page: int = 1, per_page: int = 15) -> tuple[list[DialogMessage], int]:
    query = (
        db.query(DialogMessage)
        .filter(DialogMessage.account_phone == account_phone, DialogMessage.user_id == user_id)
        .order_by(DialogMessage.created_at.desc(), DialogMessage.id.desc())
    )
    total = query.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(page, 1), total_pages)
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total_pages


# Scripts

def save_script(db: Session, name: str, first_message: str, prompt: str) -> Script:
    script = Script(name=name, first_message=first_message, prompt=prompt)
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


def get_scripts(db: Session) -> List[Script]:
    return db.query(Script).order_by(Script.created_at.desc(), Script.id.desc()).all()


def get_script(db: Session, script_id: int) -> Optional[Script]:
    return db.query(Script).filter(Script.id == script_id).first()


def delete_script(db: Session, script_id: int):
    script = get_script(db, script_id)
    if script:
        db.delete(script)
        db.commit()


# Tasks

def create_task(db: Session, script_id: int, accounts: list, recipients: list) -> Task:
    task = Task(script_id=script_id, accounts=json.dumps(accounts), recipients=json.dumps(recipients))
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_tasks(db: Session) -> List[Task]:
    return db.query(Task).order_by(Task.created_at.desc(), Task.id.desc()).all()


def get_task(db: Session, task_id: int) -> Optional[Task]:
    return db.query(Task).filter(Task.id == task_id).first()


def update_task_status(db: Session, task_id: int, status: str):
    task = get_task(db, task_id)
    if task:
        task.status = status
        if status == 'running' and not task.started_at:
            task.started_at = datetime.utcnow()
        elif status in {'completed', 'failed', 'stopped', 'cancelled'}:
            task.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(task)


def update_task_stats(db: Session, task_id: int, sent: int = 0, errors: int = 0):
    task = get_task(db, task_id)
    if task:
        task.sent_count = (task.sent_count or 0) + sent
        task.error_count = (task.error_count or 0) + errors
        db.commit()


def delete_task(db: Session, task_id: int) -> bool:
    task = get_task(db, task_id)
    if not task:
        return False
    db.delete(task)
    db.commit()
    return True


def clear_tasks(db: Session) -> int:
    count = db.query(Task).count()
    db.query(Task).delete()
    db.commit()
    return count


def delete_finished_tasks(db: Session) -> int:
    query = db.query(Task).filter(Task.status.in_(['completed', 'failed', 'stopped', 'cancelled']))
    count = query.count()
    query.delete(synchronize_session=False)
    db.commit()
    return count


# Follow-ups

def get_pending_followups(db: Session, due_before: datetime, max_followups: int = 2) -> List[Contact]:
    return (
        db.query(Contact)
        .filter(Contact.last_bot_message_at.isnot(None))
        .filter(Contact.last_bot_message_at <= due_before)
        .filter((Contact.last_user_message_at.is_(None)) | (Contact.last_user_message_at < Contact.last_bot_message_at))
        .filter((Contact.follow_up_count.is_(None)) | (Contact.follow_up_count < max_followups))
        .filter(Contact.status.notin_([STATUS_AGREED, STATUS_DECLINED]))
        .order_by(Contact.last_bot_message_at.asc())
        .all()
    )


def mark_followup_sent(db: Session, account_phone: str, user_id: str):
    contact = get_contact(db, account_phone, user_id)
    if contact:
        now = datetime.utcnow()
        contact.follow_up_count = (contact.follow_up_count or 0) + 1
        contact.last_follow_up_at = now
        contact.last_bot_message_at = now
        if contact.status == STATUS_NEW:
            contact.status = STATUS_NO_RESPONSE
        contact.updated_at = now
        db.commit()
        db.refresh(contact)


def mark_contact_handoff_sent(db: Session, account_phone: str, user_id: str):
    contact = get_contact(db, account_phone, user_id)
    if contact:
        contact.handoff_sent_at = datetime.utcnow()
        contact.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(contact)
