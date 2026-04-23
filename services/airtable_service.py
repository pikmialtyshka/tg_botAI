from airtable import Airtable
from database.crud import get_setting
from database.models import SessionLocal
from datetime import datetime

class AirtableService:
    def __init__(self):
        db = SessionLocal()
        self.api_key = get_setting(db, "airtable_api_key")
        self.base_id = get_setting(db, "airtable_base_id")
        self.table_name = get_setting(db, "airtable_table_id")
        db.close()
        
        self.airtable = None
        if self.api_key and self.base_id:
            self.airtable = Airtable(self.base_id, self.table_name or "Dialogs", self.api_key)
    
    def is_configured(self):
        return self.airtable is not None
    
    def save_dialog(self, account_phone: str, username: str, user_id: str, status: str, messages_count: int = 0):
        if not self.is_configured():
            print("⚠️ Airtable не настроен")
            return False
        
        try:
            data = {
                "Account": account_phone,
                "Username": username or "",
                "UserID": str(user_id),
                "Status": status,
                "MessagesCount": messages_count,
                "LastUpdate": datetime.now().isoformat()
            }
            
            # Проверяем, есть ли уже запись
            existing = self.airtable.search("UserID", str(user_id))
            if existing:
                record_id = existing[0]["id"]
                self.airtable.update(record_id, data)
            else:
                self.airtable.insert(data)
            
            return True
        except Exception as e:
            print(f"❌ Ошибка Airtable: {e}")
            return False
    
    def update_status(self, user_id: str, status: str):
        if not self.is_configured():
            return False
        
        try:
            existing = self.airtable.search("UserID", str(user_id))
            if existing:
                record_id = existing[0]["id"]
                self.airtable.update(record_id, {"Status": status, "LastUpdate": datetime.now().isoformat()})
                return True
        except Exception as e:
            print(f"❌ Ошибка Airtable: {e}")
        return False