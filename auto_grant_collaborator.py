"""
Watchdog to automatically grant GitHub collaborator access to Ardalan Ketabchi
Runs periodically via cron / background script.
"""

import os
import sys
import subprocess
import asyncio
import re
from telethon import TelegramClient

API_ID = int(os.environ.get("TELEGRAM_API_ID", 2040))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "b18441a1ff607e10a989891a5462e627")
SESSION_PATH = os.environ.get("TELEGRAM_SESSION_PATH", "/Users/ricksabchez/telegram_userbot/rick_session")
REPO_NAME = os.environ.get("GITHUB_REPO_NAME", "m4tinbeigi-official/trading-bot")
GH_USER_REGEX = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$")

async def check_and_grant():
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()
    
    entity = await client.get_entity("Ketabchi0")
    # Get last 5 messages
    messages = await client.get_messages(entity, limit=5)
    
    # Check if Ardalan sent a github handle / link
    for m in messages:
        if not m.out:
            text = (m.text or "").strip()
            # extract potential github username
            gh_user = text.replace("https://github.com/", "").replace("github.com/", "").replace("@", "").strip()
            if gh_user and GH_USER_REGEX.match(gh_user):
                print(f"Detected validated GitHub handle: {gh_user}")
                # Run gh api via safe argument list (shell=False prevents command injection)
                cmd = ["gh", "api", "-X", "PUT", f"/repos/{REPO_NAME}/collaborators/{gh_user}", "-f", "permission=push"]
                proc = subprocess.run(cmd, shell=False, capture_output=True, text=True)
                if proc.returncode == 0:
                    print(f"Successfully invited {gh_user} to {REPO_NAME}!")
                    await client.send_message(entity, f"دسترسی گیت‌هاب برای اکانت {gh_user} فعال شد و اینوایت برات ارسال شد 🤝")
                    break
                else:
                    print(f"Error inviting collaborator: {proc.stderr.strip()}")
            elif gh_user:
                print(f"Rejected invalid GitHub username pattern: {gh_user}")
                    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(check_and_grant())
