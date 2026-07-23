"""Developer helper: print a Telethon StringSession for the configured user.

This script is not part of the MCP server runtime. Run it once to obtain the
``TELEGRAM_SESSION_STRING`` value, then store the result in your environment.
Requires ``python-dotenv`` (declared in the dev extras of ``pyproject.toml``).
"""

import os

from dotenv import load_dotenv
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

load_dotenv()

api_id = int(os.environ["TELEGRAM_API_ID"])
api_hash = os.environ["TELEGRAM_API_HASH"]

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print(client.session.save())
