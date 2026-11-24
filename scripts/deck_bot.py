"""Deck-only Telegram bot.

Listens on a dedicated bot token, accepts only presentation topics, and ignores
or rejects everything else. Each topic runs a headless Hermes turn in the
isolated `deckbot` profile, then the finished file is delivered to Telegram.

The token is read from C:\\Users\\Ali\\.deckbot\\token.txt and is never printed.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = Path(r"C:\Users\Ali\presentation-agent")
TOKEN_FILE = Path(r"C:\Users\Ali\.deckbot\token.txt")
API = "https://api.telegram.org"
FALLBACK_IP = "149.154.167.99"
REJECT = "Deck bot only — send a topic."
START = "Send a topic and I will make a 7-slide deck and send it back."
GREETINGS = {"hi", "hey", "hello", "ping", "test", "how are you", "how r u"}


def log(message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def load_token() -> str:
    if not TOKEN_FILE.is_file():
        return ""
    return TOKEN_FILE.read_text(encoding="utf-8", errors="ignore").strip()


def _call(token: str, method: str, *, post: bool, payload: dict, files: dict | None = None) -> dict:
    """Call Telegram API, retrying via a known IP if DNS/route fails."""
    endpoints = [
        f"{API}/bot{token}/{method}",
        f"https://{FALLBACK_IP}/bot{token}/{method}",
    ]
    last_error: Exception | None = None
    for index, url in enumerate(endpoints):
        kwargs: dict = {"timeout": 90 if files else 20}
        if index == 1:
            kwargs["headers"] = {"Host": "api.telegram.org"}
            kwargs["verify"] = False
        if files:
            for value in files.values():
                handle = value[1] if isinstance(value, tuple) else value
                if hasattr(handle, "seek"):
                    handle.seek(0)
            kwargs.update({"data": payload, "files": files})
        elif post:
            kwargs["json"] = payload
        else:
            kwargs["params"] = payload
        try:
            response = requests.post(url, **kwargs) if post or files else requests.get(url, **kwargs)
            data = response.json()
            if data.get("ok"):
                return data
            log(f"telegram {method} error: {data.get('error_code')} {str(data.get('description'))[:120]}")
            return data
        except Exception as exc:
            last_error = exc
            continue
    log(f"telegram call failed: {type(last_error).__name__}")
    return {"ok": False}


def api_get(token: str, method: str, params: dict) -> dict:
    return _call(token, method, post=False, payload=params)


def api_post(token: str, method: str, data: dict, files: dict | None = None) -> dict:
    return _call(token, method, post=True, payload=data, files=files)


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


def _labelled_path(output: str, label: str) -> Path | None:
    line = next((line for line in output.splitlines() if line.startswith(label)), "")
    return Path(line[len(label):].strip()) if line else None


def _build_pptxgen(topic: str) -> Path | None:
    """Build with the PptxGenJS pipeline. Returns the deck path, or None."""
    plan_result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "topic_to_plan.py"), topic],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="ignore", timeout=60,
    )
    plan = _labelled_path((plan_result.stdout or "") + "\n" + (plan_result.stderr or ""), "PLAN:")
    if plan is None or not plan.is_file():
        log(f"pptxgen plan failed rc={plan_result.returncode}")
        return None

    digest = plan.stem.rsplit("-", 1)[-1]
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:42] or "topic"
    deck = ROOT / "output" / "telegram" / f"{slug}-{digest}" / "deck.pptx"
    deck.parent.mkdir(parents=True, exist_ok=True)
    build = subprocess.run(
        ["node", str(ROOT / "pptxgen" / "scripts" / "build_deck.js"), str(plan), str(deck)],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="ignore", timeout=90,
    )
    built = _labelled_path((build.stdout or "") + "\n" + (build.stderr or ""), "PPTX:")
    if built is None or not built.is_file():
        log(f"pptxgen build failed rc={build.returncode}")
        return None
    log("pptxgen build ok")
    return built


def _build_legacy(topic: str) -> Path | None:
    """Old deterministic python-pptx builder, kept only as a safety fallback."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "deck_from_text.py"), topic],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="ignore", timeout=150,
    )
    return _labelled_path((result.stdout or "") + "\n" + (result.stderr or ""), "DECK:")


def run_agent(topic: str, chat_id: int | str, token: str) -> None:
    """Build the deck with PptxGenJS, deliver it, keep the old builder as fallback."""
    log(f"build start | chat={chat_id} | topic={topic[:60]!r}")
    deck: Path | None = None
    try:
        deck = _build_pptxgen(topic)
        if deck is None:
            log("falling back to legacy builder")
            deck = _build_legacy(topic)
    except subprocess.TimeoutExpired:
        log("build timed out")
        send_text(token, chat_id, "That topic took too long. Try a shorter one.")
        return

    if deck is None or not deck.is_file():
        log("build failed")
        send_text(token, chat_id, "Could not build that deck. Please try a simpler topic.")
        return

    log(f"build ok | {deck.name}")
    for attempt in range(2):
        if send_file(token, chat_id, deck, "Your deck is ready."):
            log("delivery succeeded")
            return
        log(f"delivery attempt {attempt + 1} failed")
        time.sleep(3)
    send_text(token, chat_id, "Deck built, but delivery failed. Please try again.")


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
                elif text.startswith("/") or text.lower().strip("!.") in GREETINGS or text.lower().startswith("how are you"):
                    send_text(token, chat_id, REJECT)
                    log(f"rejected | chat={chat_id} | {text[:40]!r}")
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
