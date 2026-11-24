"""One-command check that the Telegram bot token works.

Usage:
    python scripts/telegram_smoke_test.py

It never prints the token. It:
  1. reads TELEGRAM_BOT_TOKEN from .env,
  2. asks Telegram who the bot is (getMe),
  3. finds the last chat that messaged the bot (getUpdates),
  4. sends a short "Pong" reply to that chat.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
API = "https://api.telegram.org/bot{token}/{method}"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def call(token: str, method: str, payload: dict | None = None) -> dict:
    url = API.format(token=token, method=method)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    env = load_env(ENV_FILE)
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")
    if not token or "paste_" in token or "here" in token:
        print("Bot token is not set yet.")
        print(f"Open {ENV_FILE} and replace the placeholder with your bot token.")
        print("Get the token from @BotFather, or use the desktop app's")
        print("Messaging -> Telegram -> Create with QR button.")
        return 2

    try:
        me = call(token, "getMe")
    except Exception as exc:
        print(f"Could not reach Telegram: {exc}")
        print("Check the token in .env, then try again.")
        return 1

    if not me.get("ok"):
        print(f"Telegram rejected the token: {me.get('description', 'unknown error')}")
        return 1

    bot = me["result"]
    print(f"Bot OK: @{bot.get('username', 'unknown')} (id {bot.get('id')})")

    try:
        updates = call(token, "getUpdates", {"limit": 10, "offset": -10})
    except Exception as exc:
        print(f"Could not read updates: {exc}")
        return 1

    messages = [
        item["message"]
        for item in updates.get("result", [])
        if "message" in item and "chat" in item["message"]
    ]
    if not messages:
        print("Bot is alive, but nobody has messaged it yet.")
        print("Send any message to your bot in Telegram, then re-run this script.")
        return 0

    chat_id = messages[-1]["chat"]["id"]
    try:
        sent = call(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "Pong from the presentation agent. The Telegram bridge works.",
            },
        )
    except Exception as exc:
        print(f"Could not send the reply: {exc}")
        return 1

    if not sent.get("ok"):
        print(f"Send failed: {sent.get('description', 'unknown error')}")
        return 1

    print(f"Pong sent to chat {chat_id}. Telegram bridge is working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
