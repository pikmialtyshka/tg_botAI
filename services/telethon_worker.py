import os
from telethon import TelegramClient, events
from typing import Optional, Dict, Callable
from telethon.sessions import StringSession

class TelethonWorker:
    def __init__(self, phone: str, api_id: int, api_hash: str, proxy: Optional[str] = None, session_file: Optional[str] = None):
        self.phone = phone
        self.api_id = api_id
        self.api_hash = api_hash
        
        if session_file and os.path.exists(session_file):
            self.client = TelegramClient(session_file, api_id, api_hash)
        else:
            session_path = f"sessions/{phone}.session"
            self.client = TelegramClient(session_path, api_id, api_hash)
        
        if proxy:
            self.client.set_proxy(self._parse_proxy(proxy))
        
        self.is_running = False
        self.message_handler = None
        
    def _parse_proxy(self, proxy_str: str) -> Dict:
        from urllib.parse import urlparse
        parsed = urlparse(proxy_str)
        proxy_type = 'socks5' if 'socks5' in parsed.scheme else 'http'
        return {
            'proxy_type': proxy_type,
            'addr': parsed.hostname,
            'port': parsed.port,
            'username': parsed.username,
            'password': parsed.password
        }
    
    async def start(self, message_handler: Optional[Callable] = None, code_callback: Optional[Callable] = None):
        try:
            if code_callback:
                await self.client.start(phone=self.phone, code_callback=code_callback)
            else:
                await self.client.start(phone=self.phone)
            
            self.is_running = True
            me = await self.client.get_me()
            print(f"✅ Аккаунт {self.phone} запущен как @{me.username or me.first_name}")
            
            if message_handler:
                self.message_handler = message_handler
                @self.client.on(events.NewMessage(incoming=True))
                async def handler(event):
                    try:
                        print(f"📥 EVENT {self.phone}: {event.raw_text[:50] if event.raw_text else 'нет текста'}")
                        
                        if event.is_private:
                            await self.message_handler(self.phone, event)
                    
                    except Exception as e:
                        print(f"❌ HANDLER CRASH: {e}")
                        import traceback
                        traceback.print_exc()
            
            return True, "ОК"
        except Exception as e:
            print(f"❌ Ошибка запуска {self.phone}: {e}")
            return False, str(e)
    
    async def stop(self):
        if self.is_running:
            await self.client.disconnect()
            self.is_running = False
            print(f"🛑 Аккаунт {self.phone} остановлен")
    
    async def send_message(self, user_id, text):
        try:
            await self.client.send_message(user_id, text)
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
            return False
    
    async def get_dialogs(self, limit=50):
        try:
            dialogs = await self.client.get_dialogs(limit=limit)
            return dialogs
        except:
            return []