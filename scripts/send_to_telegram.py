"""Send a finished deck to the configured Telegram chat, directly and quietly.

Reads credentials only from the local Hermes profile .env. Never prints them.
Stdlib only. Prints SENT:<path> on success.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PROFILE_ENV = Path(r"C:\Users\Ali\AppData\Local\hermes\profiles\testad\.env")
API = "https://api.telegram.org"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def multipart(chat_id: str, caption: str, file_path: Path) -> tuple[bytes, str]:
    boundary = "----BeautifulDeck" + uuid.uuid4().hex
    lines = [
        f"--{boundary}\r\n",
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n',
        f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n',
        f'Content-Disposition: form-data; name="document"; filename="{file_path.name}"\r\n',
        "Content-Type: application/octet-stream\r\n\r\n",
    ]
    head = "".join(lines).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + file_path.read_bytes() + tail, boundary


def post(token: str, chat_id: str, caption: str, file_path: Path) -> bool:
    """Send via requests when available (correct multipart), else stdlib fallback."""
    url = f"{API}/bot{token}/sendDocument"
    data = {"chat_id": chat_id, "caption": caption}
    for attempt in range(3):
        try:
            try:
                import requests

                with file_path.open("rb") as handle:
                    response = requests.post(
                        url, data=data, files={"document": (file_path.name, handle)},
                        timeout=90,
                    )
                body = response.json()
                if response.status_code == 429:
                    wait = int(body.get("parameters", {}).get("retry_after", 5))
                    time.sleep(min(wait + 2, 60))
                    continue
                if response.status_code != 200:
                    print(f"Telegram HTTP {response.status_code}: {str(body)[:200]}", file=sys.stderr)
                    return False
                return bool(body.get("ok"))
            except ImportError:
                payload, boundary = multipart(chat_id, caption, file_path)
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=90) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    return bool(body.get("ok"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 429:
                try:
                    wait = int(json.loads(raw).get("parameters", {}).get("retry_after", 5))
                except Exception:
                    wait = 5
                time.sleep(min(wait + 2, 60))
                continue
            print(f"Telegram HTTP {exc.code}: {raw[:200]}", file=sys.stderr)
            return False
        except Exception as exc:
            if attempt == 2:
                print(f"Telegram delivery failed: {type(exc).__name__}", file=sys.stderr)
                return False
            time.sleep(3 * (attempt + 1))
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", help="absolute path to .pptx or .pdf")
    parser.add_argument("--caption", default="Your deck is ready.")
    args = parser.parse_args()

    path = Path(args.deck).resolve()
    if not path.is_file() or path.suffix.lower() not in (".pptx", ".pdf"):
        print("ERROR: deck file not found or wrong type", file=sys.stderr)
        return 2

    values = load_env(PROFILE_ENV)
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or values.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_DELIVERY_CHAT_ID") or values.get("TELEGRAM_DELIVERY_CHAT_ID", "")
    if not token or not chat_id:
        print("ERROR: local Telegram delivery config missing", file=sys.stderr)
        return 3

    if not post(token, chat_id, args.caption, path):
        return 4
    print(f"SENT:{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
