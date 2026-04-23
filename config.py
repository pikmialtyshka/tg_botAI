import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
LOG_BOT_TOKEN = os.getenv("LOG_BOT_TOKEN")
LOG_CHAT_ID = os.getenv("LOG_CHAT_ID")
OPENAI_KEY = os.getenv("OPENAI_KEY")


API_ID = 38874106 
API_HASH = "3aa43397bb51223926d1d651b4bad34c"  