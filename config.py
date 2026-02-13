import os
from os import getenv

API_ID = int(os.environ.get("API_ID", "34943077"))  # Replace with your actual api_id or use .env
API_HASH = os.environ.get("API_HASH", "11aeec678349456f1d190f02975ed89f")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8552471757:AAGGZFfLnFZ-ikjdIb0Jr_2okx8oiCnO0iQ")

OWNER_ID = int(os.environ.get("OWNER_ID", "8260963405"))  # Your Telegram user ID

# Fixed SUDO_USERS parsing - handles empty strings properly
sudo_users_str = os.environ.get("SUDO_USERS", "")
if sudo_users_str:
    SUDO_USERS = list(map(int, sudo_users_str.split()))
else:
    SUDO_USERS = []

MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://cteator898_db_user:X2zbPeJIK6HaLPXq@cluster0.klvyqnx.mongodb.net/?appName=Cluster0")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-"))  # Telegram channel ID (with -100 prefix)
PREMIUM_LOGS = os.environ.get("PREMIUM_LOGS", "-1003828380273")  # Optional here you'll get all logs
