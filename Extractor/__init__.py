import logging
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN

logging.basicConfig(
    format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)

app = Client(
    ":Extractor:",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=120,
    workers=200
)

import os
import glob

for file in glob.glob("Extractor/modules/*.py"):
    module_name = file.replace("/", ".")[:-3]
    __import__(module_name)
