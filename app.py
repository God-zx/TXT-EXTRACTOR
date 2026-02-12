import os
import threading
from flask import Flask
from Extractor import app as bot_app
from pyrogram import idle

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running 🚀"

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    # Flask in background
    threading.Thread(target=run_flask).start()

    # Bot in main thread (IMPORTANT)
    bot_app.start()
    idle()
