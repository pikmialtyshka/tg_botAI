from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class Setting(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    value = Column(Text)


class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key=True)
    phone = Column(String, unique=True)
    proxy = Column(Text, nullable=True)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    session_file = Column(String, nullable=True)


class Dialog(Base):
    __tablename__ = 'dialogs'
    id = Column(Integer, primary_key=True)
    account_phone = Column(String)
    user_id = Column(String)
    username = Column(String, nullable=True)
    status = Column(String, default='new')
    created_at = Column(DateTime, default=datetime.utcnow)


class Contact(Base):
    __tablename__ = 'contacts'
    id = Column(Integer, primary_key=True)
    account_phone = Column(String, index=True)
    user_id = Column(String, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    display_contact = Column(String, nullable=True)
    status = Column(String, default='new')
    source_task_id = Column(Integer, nullable=True)
    persona_name = Column(String, nullable=True)
    persona_role = Column(String, nullable=True)
    persona_company = Column(String, nullable=True)
    follow_up_count = Column(Integer, default=0)
    last_user_message_at = Column(DateTime, nullable=True)
    last_bot_message_at = Column(DateTime, nullable=True)
    last_follow_up_at = Column(DateTime, nullable=True)
    handoff_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DialogMessage(Base):
    __tablename__ = 'dialog_messages'
    id = Column(Integer, primary_key=True)
    account_phone = Column(String, index=True)
    user_id = Column(String, index=True)
    role = Column(String)
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Script(Base):
    __tablename__ = 'scripts'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    first_message = Column(Text)
    prompt = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    script_id = Column(Integer)
    accounts = Column(Text)
    recipients = Column(Text)
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    sent_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)


DATABASE_URL = 'sqlite:///bot.db'
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


def _ensure_column(conn, table_name: str, column_name: str, ddl: str):
    columns = conn.exec_driver_sql(f'PRAGMA table_info({table_name})').fetchall()
    existing = {row[1] for row in columns}
    if column_name not in existing:
        conn.exec_driver_sql(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}')


def _ensure_sqlite_migrations():
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE INDEX IF NOT EXISTS ix_contacts_account_phone ON contacts (account_phone)')
        conn.exec_driver_sql('CREATE INDEX IF NOT EXISTS ix_contacts_user_id ON contacts (user_id)')
        conn.exec_driver_sql('CREATE INDEX IF NOT EXISTS ix_dialog_messages_account_phone ON dialog_messages (account_phone)')
        conn.exec_driver_sql('CREATE INDEX IF NOT EXISTS ix_dialog_messages_user_id ON dialog_messages (user_id)')
        for name, ddl in [
            ('first_name', 'VARCHAR'),
            ('last_name', 'VARCHAR'),
            ('phone', 'VARCHAR'),
            ('display_contact', 'VARCHAR'),
            ('follow_up_count', 'INTEGER DEFAULT 0'),
            ('last_user_message_at', 'DATETIME'),
            ('last_bot_message_at', 'DATETIME'),
            ('last_follow_up_at', 'DATETIME'),
            ('handoff_sent_at', 'DATETIME'),
            ('persona_name', 'VARCHAR'),
            ('persona_role', 'VARCHAR'),
            ('persona_company', 'VARCHAR'),
            ('source_task_id', 'INTEGER'),
            ('updated_at', 'DATETIME'),
            ('created_at', 'DATETIME'),
            ('status', "VARCHAR DEFAULT 'new'"),
        ]:
            _ensure_column(conn, 'contacts', name, ddl)
        for name, ddl in [
            ('started_at', 'DATETIME'),
            ('finished_at', 'DATETIME'),
            ('sent_count', 'INTEGER DEFAULT 0'),
            ('error_count', 'INTEGER DEFAULT 0'),
        ]:
            _ensure_column(conn, 'tasks', name, ddl)


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_migrations()
