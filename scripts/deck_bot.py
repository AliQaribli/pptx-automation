"""Deck-only Telegram bot.

Listens on a dedicated bot token, accepts only presentation topics, and ignores
or rejects everything else. Each topic runs a headless Hermes turn in the
isolated `deckbot` profile, then the finished file is delivered to Telegram.

The token is read from C:\\Users\\Ali\\.deckbot\\token.txt and is never printed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(r"C:\Users\Ali\presentation-agent")
TOKEN_FILE = Path(r"C:\Users\Ali\.deckbot\token.txt")
API = "https://api.telegram.org"
PROFILE = "deckbot"
PROMPT_PREFIX = "Make a short informative deck about "
REJECT = "Deck bot only — send a topic."
START = "Send a topic and I will make a 5-slide deck and send it back."


def log(message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def load_token() -> str:
    if not TOKEN_FILE.is_file():
        return ""
    return TOKEN_FILE.read_text(encoding="utf-8", errors="ignore").strip()


def api_get(token: str, method: str, params: dict, timeout: int = 20) -> dict:
    response = requests.get(f"{API}/bot{token}/{method}", params=params, timeout=timeout)
    return response.json()


def api_post(token: str, method: str, data: dict, files: dict | None = None) -> dict:
    kwargs = {"data": data, "timeout": 90}
    if files:
        kwargs["files"] = files
    response = requests.post(f"{API}/bot{token}/{method}", **kwargs)
    return response.json()


def send_text(token: str, chat_id: int | str, text: str) -> None:
    api_post(token, "sendMessage", {"chat_id": chat_id, "text": text[:4000]})


def send_file(token: str, chat_id: int | str, path: Path, caption: str) -> bool:
    if not path.is_file():
        return False
    with path.open("rb") as handle:
        result = api_post(
            token,
            "sendDocument",
            {"chat_id": chat_id, "caption": caption[:1000]},
            {"document": (path.name, handle)},
        )
    return bool(result.get("ok"))


def newest_deck() -> Path | None:
    candidates = list((ROOT / "output" / "telegram").rglob("*.pptx"))
    candidates += list((ROOT / "output" / "telegram").rglob("*.pdf"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def run_agent(topic: str, chat_id: int | str, token: str) -> None:
    env = os.environ.copy()
    env["TELEGRAM_BOT_TOKEN"] = token
    env["TELEGRAM_DELIVERY_CHAT_ID"] = str(chat_id)
    command = [
        "hermes", "-p", PROFILE, "chat",
        "-q", PROMPT_PREFIX + topic,
        "--oneshot", "--yolo", "--max-turns", "18",
    ]
    log(f"agent start | chat={chat_id} | topic={topic[:60]!r}")
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=300,
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
    except subprocess.TimeoutExpired:
        output = ""
        log("agent timed out")

    if "SENT:" in output:
        log("agent delivered the deck")
        return

    deck = newest_deck()
    if deck and send_file(token, chat_id, deck, "Your deck is ready."):
        log("fallback delivery succeeded")
    else:
        log("delivery failed — no file sent")
        send_text(token, chat_id, "Could not build that deck. Please try a simpler topic.")


def main() -> int:
    token = load_token()
    if not token:
        log(f"token file missing: {TOKEN_FILE}")
        return 2
    log("deck-only bot started")
    offset: int | None = None
    while True:
        try:
            params = {"offset": offset or 0, "timeout": 10}
            data = api_get(token, "getUpdates", params)
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message") or {}
                text = (message.get("text") or "").strip()
                chat_id = (message.get("chat") or {}).get("id")
                if chat_id is None or not text:
                    continue
                if text == "/start":
                    send_text(token, chat_id, START)
                    log(f"start | chat={chat_id}")
                elif text.startswith("/"):
                    send_text(token, chat_id, REJECT)
                    log(f"rejected command | chat={chat_id}")
                else:
                    send_text(token, chat_id, "Working on your deck…")
                    run_agent(text, chat_id, token)
        except KeyboardInterrupt:
            log("stopped")
            return 0
        except Exception as exc:
            log(f"poll error: {type(exc).__name__}")
            time.sleep(8)


if __name__ == "__main__":
    raise SystemExit(main())
