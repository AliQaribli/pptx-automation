"""Standalone, long-polling Telegram request bot with an offline self-test.

The bot reads its token (and optional proxy) from the environment or an env
file, long-polls ``getUpdates`` using only the standard library, turns each
incoming text message into a PPTX deck and replies with ``sendDocument``.

Security notes:
  * The token is never printed, and every outgoing error string is redacted
    through :func:`redact` before it reaches stdout.
  * ``--self-test`` replaces the whole HTTP layer with an in-memory fake, so it
    is completely offline and needs no token or network access.

Usage:
    python scripts/telegram_bot.py --self-test
    python scripts/telegram_bot.py
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENV = ROOT / ".env"
PROFILE_ENV = Path(
    os.environ.get(
        "HERMES_ENV_FILE",
        str(
            Path.home()
            / "AppData"
            / "Local"
            / "hermes"
            / "profiles"
            / "testad"
            / ".env"
        ),
    )
)
API_TEMPLATE = "https://api.telegram.org/bot{token}/{method}"
MAX_ATTEMPTS = 5
POLL_TIMEOUT = 10  # Telegram long-poll seconds
HTTP_TIMEOUT = POLL_TIMEOUT + 8  # must exceed the server-side long poll
PLACEHOLDERS = ("paste_", "here", "your_bot_token", "changeme")


class TelegramError(Exception):
    """A redacted, user-safe error raised by the HTTP layer."""


class StopRequested(Exception):
    """Internal signal that the bot should stop looping."""


# --------------------------------------------------------------------------- #
# Configuration + redaction
# --------------------------------------------------------------------------- #
def load_env(path: Path | str) -> dict[str, str]:
    """Parse a simple KEY=VALUE env file (same pattern as telegram_smoke_test)."""
    path = Path(path)
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


def load_config(env_file: Path | str | None = None) -> tuple[str, str]:
    """Return ``(token, proxy)`` from env vars and env files.

    Precedence: process environment > explicit/profile env file > project .env.
    """
    merged = load_env(LOCAL_ENV)
    merged.update(load_env(env_file if env_file is not None else PROFILE_ENV))
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or merged.get(
        "TELEGRAM_BOT_TOKEN", ""
    )
    proxy = os.environ.get("TELEGRAM_PROXY") or merged.get("TELEGRAM_PROXY", "")
    return token.strip(), proxy.strip()


def redact(text: str, token: str) -> str:
    """Remove the token from any string before it is printed or stored."""
    text = str(text)
    if token:
        text = text.replace(token, "<redacted-token>")
    # Defensive: catch a token that appears URL-encoded in an exception.
    if token and ":" in token:
        text = text.replace(urllib.parse.quote(token, safe=""), "<redacted-token>")
    # Never leak a bot endpoint even if a different/partial token was used.
    text = re.sub(r"(api\.telegram\.org/bot)[^/\s]+", r"\1<redacted-token>", text)
    return text


def build_opener(proxy: str | None = None):
    """Build a urllib opener, honouring ``TELEGRAM_PROXY`` when supplied."""
    if proxy:
        proxies = {"http": proxy, "https": proxy}
        return urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
    return urllib.request.build_opener()


# --------------------------------------------------------------------------- #
# HTTP layer (stdlib urllib) with 429 retry/backoff
# --------------------------------------------------------------------------- #
def retry_delay(headers, attempt: int, max_delay: float = 60.0) -> float:
    """Honour Retry-After (seconds) when present, else exponential backoff."""
    value = None
    try:
        value = headers.get("Retry-After") if headers is not None else None
    except Exception:
        value = None
    if value is not None:
        try:
            return max(0.0, min(float(value), max_delay))
        except (TypeError, ValueError):
            pass
    return float(min(2**attempt, max_delay))


class _Response:
    """Tiny context-manager wrapper used by tests and by urlopen results."""

    def __init__(self, body: bytes, headers=None):
        self._buffer = io.BytesIO(body)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self._buffer.close()
        return False

    def read(self) -> bytes:
        return self._buffer.read()


def request_bytes(
    opener,
    url: str,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    token: str = "",
    attempts: int = MAX_ATTEMPTS,
    sleep=time.sleep,
    timeout: int = HTTP_TIMEOUT,
) -> bytes:
    """Perform one API request, retrying 429s with Retry-After/backoff.

    All raised errors are redacted so they never carry the token or a full
    bot URL into the logs.
    """
    last_error = "unknown error"
    for attempt in range(max(1, attempts)):
        try:
            request = urllib.request.Request(url, data=data, headers=headers or {})
            with opener.open(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            code = getattr(exc, "code", None)
            if code == 429 and attempt < attempts - 1:
                sleep(retry_delay(getattr(exc, "headers", None), attempt))
                continue
            last_error = f"HTTP {code}: {getattr(exc, 'reason', 'error')}"
            break
        except urllib.error.URLError as exc:
            last_error = f"network error: {getattr(exc, 'reason', exc)}"
            break
        except Exception as exc:  # noqa: BLE001 - always redact before logging
            last_error = f"request error: {exc}"
            break
    raise TelegramError(redact(last_error, token))


class TelegramClient:
    """Real Telegram API client backed by :func:`request_bytes`."""

    def __init__(
        self,
        token: str,
        opener=None,
        proxy: str | None = None,
        sleep=time.sleep,
        attempts: int = MAX_ATTEMPTS,
        timeout: int = HTTP_TIMEOUT,
    ):
        self.token = token
        self.opener = opener if opener is not None else build_opener(proxy)
        self.sleep = sleep
        self.attempts = attempts
        self.timeout = timeout

    def redact(self, text: str) -> str:
        return redact(text, self.token)

    def _url(self, method: str) -> str:
        return API_TEMPLATE.format(token=self.token, method=method)

    def call(self, method: str, payload: dict | None = None) -> dict:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        body = request_bytes(
            self.opener,
            self._url(method),
            data=data,
            headers=headers,
            token=self.token,
            attempts=self.attempts,
            sleep=self.sleep,
            timeout=self.timeout,
        )
        try:
            return json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise TelegramError(self.redact(f"invalid API response: {exc}")) from None

    def send_document(
        self, chat_id, path: Path | str, caption: str | None = None
    ) -> dict:
        path = Path(path)
        boundary = uuid.uuid4().hex
        fields: list[tuple[str, str]] = [("chat_id", str(chat_id))]
        if caption:
            fields.append(("caption", caption))

        chunks: list[bytes] = []
        for name, value in fields:
            chunks.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n".encode("utf-8")
            )
        content = path.read_bytes()
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="document"; '
                f'filename="{path.name}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode("utf-8")
        )
        chunks.append(content)
        chunks.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(sum(len(c) for c in chunks)),
        }
        body = request_bytes(
            self.opener,
            self._url("sendDocument"),
            data=b"".join(chunks),
            headers=headers,
            token=self.token,
            attempts=self.attempts,
            sleep=self.sleep,
            timeout=self.timeout,
        )
        try:
            return json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise TelegramError(self.redact(f"invalid API response: {exc}")) from None


class FakeTelegramAPI:
    """In-memory Telegram stand-in used by ``--self-test`` and unit tests.

    Implements the same small interface as :class:`TelegramClient`:
    ``call``, ``send_document`` and ``redact``.
    """

    def __init__(self, messages=None, stop_event: threading.Event | None = None):
        self.updates = []
        for index, (chat_id, text) in enumerate(messages or [], start=1):
            self.updates.append(
                {
                    "update_id": index,
                    "message": {
                        "message_id": index,
                        "chat": {"id": chat_id},
                        "text": text,
                    },
                }
            )
        self.stop_event = stop_event
        self.sent_documents: list[dict] = []
        self.calls: list[tuple[str, dict | None]] = []

    def redact(self, text: str) -> str:
        return text

    def call(self, method: str, payload: dict | None = None) -> dict:
        self.calls.append((method, payload))
        if method == "getUpdates":
            offset = (payload or {}).get("offset", 0) or 0
            return {
                "ok": True,
                "result": [u for u in self.updates if u["update_id"] >= offset],
            }
        return {"ok": True, "result": {}}

    def send_document(
        self, chat_id, path: Path | str, caption: str | None = None
    ) -> dict:
        self.sent_documents.append(
            {
                "chat_id": chat_id,
                "path": str(path),
                "caption": caption,
                "exists": Path(path).exists(),
            }
        )
        if self.stop_event is not None:
            self.stop_event.set()
        return {"ok": True, "result": {"message_id": len(self.sent_documents)}}


# --------------------------------------------------------------------------- #
# Deck generation
# --------------------------------------------------------------------------- #
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _content_types() -> str:
    overrides = {
        "/ppt/presentation.xml": "presentationml.presentation.main+xml",
        "/ppt/slides/slide1.xml": "presentationml.slide+xml",
        "/ppt/slideMasters/slideMaster1.xml": "presentationml.slideMaster+xml",
        "/ppt/slideLayouts/slideLayout1.xml": "presentationml.slideLayout+xml",
        "/ppt/theme/theme1.xml": "theme+xml",
    }
    parts = "".join(
        f'<Override PartName="{name}" ContentType="application/vnd.'
        f'openxmlformats-officedocument.{ctype}"/>'
        for name, ctype in overrides.items()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{_CT}">'
        '<Default Extension="rels" ContentType="application/vnd.'
        'openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f"{parts}</Types>"
    )


def _rels(target: str, rel_type: str, rid: str = "rId1") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_REL}">'
        f'<Relationship Id="{rid}" Type="{_R}/{rel_type}" Target="{target}"/>'
        "</Relationships>"
    )


def _empty_tree() -> str:
    return (
        "<a:nvGrpSpPr><a:cNvPr id=\"1\" name=\"\"/><a:cNvGrpSpPr/><a:nvPr/>"
        "</a:nvGrpSpPr><a:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/>"
        '<a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/>'
        '<a:chExt cx="0" cy="0"/></a:xfrm></a:grpSpPr>'
    )


def write_minimal_pptx(path: Path | str, text: str) -> Path:
    """Write a small but structurally valid PPTX using only the stdlib.

    Used as the fallback when ``presentation.cli`` is not present yet.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [line for line in text.splitlines()] or [text]
    paragraphs = "".join(
        f"<a:p><a:r><a:rPr lang=\"en-US\" sz=\"2800\"/>"
        f"<a:t>{xml_escape(line)}</a:t></a:r></a:p>"
        for line in lines
    )
    slide = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:sld xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}">'
        f"<a:cSld><a:spTree>{_empty_tree()}"
        '<a:sp><a:nvSpPr><a:cNvPr id="2" name="Brief"/>'
        '<a:cNvSpPr txBox="1"/><a:nvPr/></a:nvSpPr>'
        '<a:spPr><a:xfrm><a:off x="457200" y="457200"/>'
        '<a:ext cx="8229600" cy="5943600"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></a:spPr>'
        '<a:txBody><a:bodyPr wrap="square"/><a:lstStyle/>'
        f"{paragraphs}</a:txBody></a:sp>"
        f"</a:spTree></a:cSld><p:clrMapOvr><a:masterClrMapping/>"
        "</p:clrMapOvr></p:sld>"
    )
    presentation = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:presentation xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
        "</p:sldMasterIdLst>"
        '<p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst>'
        '<p:sldSz cx="9144000" cy="6858000" type="screen4x3"/>'
        '<p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    )
    master = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:sldMaster xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}">'
        f"<a:cSld><a:spTree>{_empty_tree()}</a:spTree></a:cSld>"
        '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" '
        'accent1="accent1" accent2="accent2" accent3="accent3" '
        'accent4="accent4" accent5="accent5" accent6="accent6" '
        'hlink="hlink" folHlink="folHlink"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/>'
        "</p:sldLayoutIdLst>"
        "<p:txStyles><p:titleStyle><a:lvl1pPr/></p:titleStyle>"
        "<p:bodyStyle><a:lvl1pPr/></p:bodyStyle>"
        "<p:otherStyle><a:lvl1pPr/></p:otherStyle></p:txStyles></p:sldMaster>"
    )
    layout = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:sldLayout xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}" '
        'type="blank" preserve="1">'
        f'<a:cSld name="Blank"><a:spTree>{_empty_tree()}</a:spTree></a:cSld>'
        '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'
    )
    theme = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<a:theme xmlns:a="{_A}" name="Office Theme"><a:themeElements>'
        '<a:clrScheme name="Office">'
        '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
        '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
        '<a:dk2><a:srgbClr val="44546A"/></a:dk2>'
        '<a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>'
        '<a:accent1><a:srgbClr val="5B9BD5"/></a:accent1>'
        '<a:accent2><a:srgbClr val="ED7D31"/></a:accent2>'
        '<a:accent3><a:srgbClr val="A5A5A5"/></a:accent3>'
        '<a:accent4><a:srgbClr val="FFC000"/></a:accent4>'
        '<a:accent5><a:srgbClr val="4472C4"/></a:accent5>'
        '<a:accent6><a:srgbClr val="70AD47"/></a:accent6>'
        '<a:hlink><a:srgbClr val="0563C1"/></a:hlink>'
        '<a:folHlink><a:srgbClr val="954F72"/></a:folHlink>'
        "</a:clrScheme>"
        '<a:fontScheme name="Office">'
        '<a:majorFont><a:latin typeface="Calibri Light"/><a:ea typeface=""/>'
        '<a:cs typeface=""/></a:majorFont>'
        '<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/>'
        '<a:cs typeface=""/></a:minorFont></a:fontScheme>'
        '<a:fmtScheme name="Office"><a:fillStyleLst>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        "</a:fillStyleLst><a:lnStyleLst>"
        '<a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
        '<a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
        '<a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
        "</a:lnStyleLst><a:effectStyleLst>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "</a:effectStyleLst><a:bgFillStyleLst>"
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        "</a:bgFillStyleLst></a:fmtScheme>"
        "</a:themeElements></a:theme>"
    )
    p_rels = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_REL}">'
        f'<Relationship Id="rId1" Type="{_R}/slideMaster" '
        'Target="slideMasters/slideMaster1.xml"/>'
        f'<Relationship Id="rId2" Type="{_R}/slide" Target="slides/slide1.xml"/>'
        f'<Relationship Id="rId3" Type="{_R}/theme" Target="theme/theme1.xml"/>'
        "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_REL}">'
        f'<Relationship Id="rId1" Type="{_R}/officeDocument" '
        'Target="ppt/presentation.xml"/></Relationships>'
    )
    parts = {
        "[Content_Types].xml": _content_types(),
        "_rels/.rels": root_rels,
        "ppt/presentation.xml": presentation,
        "ppt/_rels/presentation.xml.rels": p_rels,
        "ppt/slides/slide1.xml": slide,
        "ppt/slides/_rels/slide1.xml.rels": _rels("../slideLayouts/slideLayout1.xml", "slideLayout"),
        "ppt/slideMasters/slideMaster1.xml": master,
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_REL}">'
            f'<Relationship Id="rId1" Type="{_R}/slideLayout" '
            'Target="../slideLayouts/slideLayout1.xml"/>'
            f'<Relationship Id="rId2" Type="{_R}/theme" Target="../theme/theme1.xml"/>'
            "</Relationships>"
        ),
        "ppt/slideLayouts/slideLayout1.xml": layout,
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _rels("../slideMasters/slideMaster1.xml", "slideMaster"),
        "ppt/theme/theme1.xml": theme,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return path


def _deck_filename(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)[:6]
    stem = "-".join(words).lower()[:60] or "deck"
    digest = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:8]
    return f"{stem}-{digest}.pptx"


def generate_deck(
    text: str,
    output_dir: Path | str | None = None,
    runner=subprocess.run,
    root: Path | str = ROOT,
) -> Path:
    """Produce a PPTX from ``text`` and return its path.

    When ``presentation/cli.py`` exists it is invoked as a subprocess;
    otherwise a valid minimal PPTX is written with the stdlib so the bot and
    the self-test remain fully functional today.
    """
    output_dir = Path(output_dir) if output_dir is not None else ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / _deck_filename(text)
    cli = Path(root) / "presentation" / "cli.py"
    if cli.is_file():
        command = [
            sys.executable,
            "-m",
            "presentation.cli",
            "--text",
            text,
            "--output",
            str(path),
        ]
        result = runner(command, cwd=str(root), check=False, capture_output=True)
        if getattr(result, "returncode", 1) == 0 and path.is_file():
            return path
    return write_minimal_pptx(path, text)


# --------------------------------------------------------------------------- #
# Long-poll loop
# --------------------------------------------------------------------------- #
def _install_sigint_handler(stop_event: threading.Event):
    """Set ``stop_event`` on SIGINT; return the previous handler to restore."""
    if threading.current_thread() is not threading.main_thread():
        return None
    previous = signal.getsignal(signal.SIGINT)

    def _handler(signum, frame):
        stop_event.set()

    try:
        signal.signal(signal.SIGINT, _handler)
    except (ValueError, OSError):
        return None
    return previous


def _restore_sigint_handler(previous):
    if previous is None:
        return
    try:
        signal.signal(signal.SIGINT, previous)
    except (ValueError, OSError):
        pass


def iter_text_messages(client, stop_event: threading.Event, poll_timeout: int = POLL_TIMEOUT):
    """Yield ``(chat_id, text)`` for incoming text messages until stopped."""
    offset = 0
    idle_backoff = 1
    while not stop_event.is_set():
        try:
            response = client.call(
                "getUpdates",
                {
                    "offset": offset,
                    "timeout": poll_timeout,
                    "allowed_updates": ["message"],
                },
            )
        except TelegramError as exc:
            print(f"getUpdates failed: {client.redact(str(exc))}", flush=True)
            stop_event.wait(min(idle_backoff, 30))
            idle_backoff = min(idle_backoff * 2, 30)
            continue
        except KeyboardInterrupt:
            stop_event.set()
            return
        idle_backoff = 1
        if not isinstance(response, dict) or not response.get("ok"):
            description = (response or {}).get("description", "unknown error")
            print(f"Telegram error: {client.redact(str(description))}", flush=True)
            stop_event.wait(2)
            continue

        updates = response.get("result") or []
        for update in updates:
            if stop_event.is_set():
                return
            update_id = update.get("update_id")
            if isinstance(update_id, int) and update_id >= offset:
                offset = update_id + 1
            message = update.get("message") or update.get("edited_message") or {}
            text = message.get("text")
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            if not isinstance(text, str) or not text.strip() or chat_id is None:
                continue
            yield chat_id, text


def run_bot(
    client,
    stop_event: threading.Event | None = None,
    output_dir: Path | str | None = None,
    poll_timeout: int = POLL_TIMEOUT,
    generator=generate_deck,
) -> int:
    """Run the bot until ``stop_event`` is set or SIGINT is received."""
    owns_event = stop_event is None
    stop_event = stop_event or threading.Event()
    previous = _install_sigint_handler(stop_event)
    try:
        for chat_id, text in iter_text_messages(client, stop_event, poll_timeout):
            if stop_event.is_set():
                break
            print(
                f"Received text message from chat {chat_id} ({len(text)} chars).",
                flush=True,
            )
            try:
                deck_path = generator(text, output_dir=output_dir)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"Deck generation failed: {client.redact(str(exc))}",
                    flush=True,
                )
                continue
            deck_path = Path(deck_path)
            print(f"Deck produced: {deck_path.name}", flush=True)
            try:
                sent = client.send_document(
                    chat_id, deck_path, caption="Your deck is ready."
                )
            except TelegramError as exc:
                print(f"sendDocument failed: {client.redact(str(exc))}", flush=True)
                continue
            if isinstance(sent, dict) and sent.get("ok"):
                print("Deck sent.", flush=True)
            else:
                description = (sent or {}).get("description", "unknown error")
                print(
                    f"sendDocument rejected: {client.redact(str(description))}",
                    flush=True,
                )
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        if owns_event:
            _restore_sigint_handler(previous)
    print("Stopped cleanly.", flush=True)
    return 0


# --------------------------------------------------------------------------- #
# Offline self-test
# --------------------------------------------------------------------------- #
def self_test() -> int:
    """Prove the receive -> generate -> sendDocument pipeline without network."""
    import tempfile

    stop_event = threading.Event()
    chat_id = 424242
    brief = "Build a short deck about renewable energy"
    fake = FakeTelegramAPI([(chat_id, brief)], stop_event=stop_event)

    print("SELF-TEST: starting offline fake Telegram API", flush=True)
    with tempfile.TemporaryDirectory(prefix="telegram_bot_selftest_") as tmp:
        rc = run_bot(fake, stop_event=stop_event, output_dir=tmp)

        received = [
            (method, payload)
            for method, payload in fake.calls
            if method == "getUpdates"
        ]
        if not received:
            print("SELF-TEST FAILED: no getUpdates call was made", flush=True)
            return 1
        print(f"SELF-TEST: text message received from chat {chat_id}", flush=True)

        if len(fake.sent_documents) != 1:
            print(
                "SELF-TEST FAILED: sendDocument was not called exactly once",
                flush=True,
            )
            return 1

        record = fake.sent_documents[0]
        deck_path = Path(record["path"])
        if deck_path.suffix.lower() != ".pptx" or not deck_path.is_file():
            print("SELF-TEST FAILED: no PPTX deck path was produced", flush=True)
            return 1
        print(f"SELF-TEST: deck produced: {deck_path.name}", flush=True)

        if record["chat_id"] != chat_id or record["path"] != str(deck_path):
            print("SELF-TEST FAILED: sendDocument got the wrong path/chat", flush=True)
            return 1
        print("SELF-TEST: sendDocument called with the produced deck path", flush=True)

    if rc != 0:
        print("SELF-TEST FAILED: bot loop returned an error", flush=True)
        return 1
    print("SELF-TEST PASSED", flush=True)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Telegram deck request bot")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run the offline in-memory pipeline check (no token/network)",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="path to an extra env file with TELEGRAM_BOT_TOKEN/TELEGRAM_PROXY",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    token, proxy = load_config(args.env_file)
    if not token or any(marker in token.lower() for marker in PLACEHOLDERS):
        print("Bot token is not set yet. Put TELEGRAM_BOT_TOKEN in the env file.")
        return 2

    client = TelegramClient(token, opener=build_opener(proxy))
    return run_bot(client)


if __name__ == "__main__":
    sys.exit(main())
