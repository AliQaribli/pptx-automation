"""Unit tests for scripts/telegram_bot.py.

Run with either:
    python -m pytest tests/test_telegram_bot.py -q
    python -m unittest tests.test_telegram_bot -v

Only the standard library (unittest + unittest.mock) is used.
"""

from __future__ import annotations

import io
import json
import signal
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import telegram_bot as bot  # noqa: E402

TOKEN = "123456:ABCdefGHI-token-value"
URL = "https://api.telegram.org/bot{token}/getUpdates".format(token=TOKEN)


def _response(body: bytes, headers=None):
    return bot._Response(body, headers or {})


def _http_error(status: int, headers=None, reason="error"):
    return urllib.error.HTTPError(URL, status, reason, headers or {}, None)


class ConfigAndRedactionTests(unittest.TestCase):
    def test_load_env_parses_values_and_skips_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "sample.env"
            env_file.write_text(
                "# a comment\n"
                "TELEGRAM_BOT_TOKEN=abc123\n"
                'TELEGRAM_PROXY="http://127.0.0.1:8899"\n'
                "BROKEN_LINE\n"
                "\n",
                encoding="utf-8",
            )
            values = bot.load_env(env_file)
        self.assertEqual(values["TELEGRAM_BOT_TOKEN"], "abc123")
        self.assertEqual(values["TELEGRAM_PROXY"], "http://127.0.0.1:8899")
        self.assertEqual(len(values), 2)

    def test_load_config_uses_env_over_files(self):
        with patch.dict(
            "os.environ",
            {"TELEGRAM_BOT_TOKEN": "env-token", "TELEGRAM_PROXY": "http://env-proxy"},
            clear=False,
        ), patch.object(
            bot, "load_env", return_value={"TELEGRAM_BOT_TOKEN": "file-token"}
        ):
            token, proxy = bot.load_config()
        self.assertEqual(token, "env-token")
        self.assertEqual(proxy, "http://env-proxy")

    def test_redact_never_leaks_token_or_bot_url(self):
        message = "failed GET " + URL + " (token=" + TOKEN + ")"
        cleaned = bot.redact(message, TOKEN)
        self.assertNotIn(TOKEN, cleaned)
        self.assertNotIn(URL, cleaned)
        self.assertIn("<redacted-token>", cleaned)

    def test_redact_handles_encoded_token(self):
        cleaned = bot.redact("url " + urllib.parse.quote(TOKEN, safe=""), TOKEN)
        self.assertNotIn(TOKEN, cleaned)
        self.assertNotIn(urllib.parse.quote(TOKEN, safe=""), cleaned)


class ProxyAndRetryTests(unittest.TestCase):
    def test_build_opener_uses_telegram_proxy(self):
        proxy = "http://127.0.0.1:8899"
        with patch.object(urllib.request, "build_opener") as build:
            bot.build_opener(proxy)
        handler = build.call_args[0][0]
        self.assertIsInstance(handler, urllib.request.ProxyHandler)
        self.assertEqual(handler.proxies, {"http": proxy, "https": proxy})

    def test_429_honors_retry_after(self):
        opener = Mock()
        opener.open.side_effect = [
            _http_error(429, {"Retry-After": "2"}),
            _response(b'{"ok":true}'),
        ]
        sleep = Mock()
        body = bot.request_bytes(
            opener, URL, token=TOKEN, attempts=3, sleep=sleep
        )
        self.assertEqual(body, b'{"ok":true}')
        self.assertEqual(opener.open.call_count, 2)
        sleep.assert_called_once_with(2.0)

    def test_429_without_header_uses_exponential_backoff(self):
        opener = Mock()
        opener.open.side_effect = [
            _http_error(429),
            _http_error(429),
            _response(b"ok"),
        ]
        sleep = Mock()
        bot.request_bytes(opener, URL, token=TOKEN, attempts=4, sleep=sleep)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1.0, 2.0])

    def test_429_exhaustion_raises_redacted_error(self):
        opener = Mock()
        opener.open.side_effect = [_http_error(429)] * 3
        with self.assertRaises(bot.TelegramError) as ctx:
            bot.request_bytes(
                opener, URL, token=TOKEN, attempts=3, sleep=Mock()
            )
        self.assertNotIn(TOKEN, str(ctx.exception))
        self.assertEqual(opener.open.call_count, 3)

    def test_network_error_is_redacted(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.URLError("refused " + TOKEN)
        with self.assertRaises(bot.TelegramError) as ctx:
            bot.request_bytes(opener, URL, token=TOKEN, attempts=1, sleep=Mock())
        self.assertNotIn(TOKEN, str(ctx.exception))


class ClientProtocolTests(unittest.TestCase):
    def test_client_call_posts_json(self):
        client = bot.TelegramClient(TOKEN, opener=Mock())
        with patch.object(bot, "request_bytes", return_value=b'{"ok":true}') as req:
            result = client.call("getUpdates", {"offset": 7})
        self.assertTrue(result["ok"])
        kwargs = req.call_args.kwargs
        self.assertEqual(json.loads(kwargs["data"].decode("utf-8")), {"offset": 7})
        self.assertTrue(req.call_args.args[1].endswith("/getUpdates"))
        self.assertIn(TOKEN, req.call_args.args[1])  # internal only, never printed

    def test_send_document_builds_multipart_with_file(self):
        client = bot.TelegramClient(TOKEN, opener=Mock())
        with tempfile.TemporaryDirectory() as tmp:
            deck = Path(tmp) / "brief.pptx"
            deck.write_bytes(b"FAKE-PPTX-CONTENT")
            with patch.object(
                bot, "request_bytes", return_value=b'{"ok":true}'
            ) as req:
                client.send_document(99, deck, caption="ready")
        body = req.call_args.kwargs["data"]
        self.assertIn(b'name="chat_id"', body)
        self.assertIn(b"99", body)
        self.assertIn(b'name="caption"', body)
        self.assertIn(b'name="document"', body)
        self.assertIn(b'filename="brief.pptx"', body)
        self.assertIn(b"FAKE-PPTX-CONTENT", body)


class PipelineTests(unittest.TestCase):
    def test_iter_text_messages_extracts_only_text(self):
        client = Mock()
        client.redact.side_effect = lambda text: text
        client.call.return_value = {
            "ok": True,
            "result": [
                {"update_id": 10, "message": {"chat": {"id": 7}, "text": "hello"}},
                {"update_id": 11, "message": {"chat": {"id": 7}, "photo": []}},
                {"update_id": 12, "edited_message": {"chat": {"id": 7}, "text": "x"}},
            ],
        }
        stop = threading.Event()
        stream = bot.iter_text_messages(client, stop)
        self.assertEqual(next(stream), (7, "hello"))
        stop.set()
        with self.assertRaises(StopIteration):
            next(stream)
        payload = client.call.call_args.args[1]
        self.assertEqual(payload["offset"], 0)
        self.assertEqual(payload["allowed_updates"], ["message"])

    def test_generate_deck_writes_valid_pptx(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = bot.generate_deck("A brief about solar power", output_dir=tmp)
            self.assertEqual(path.suffix, ".pptx")
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
            self.assertIn("ppt/presentation.xml", names)
            self.assertIn("ppt/slides/slide1.xml", names)
            self.assertIn("[Content_Types].xml", names)
            self.assertIn("solar", path.name)

    def test_generate_deck_uses_presentation_cli_when_available(self):
        def fake_runner(command, **kwargs):
            output = Path(command[command.index("--output") + 1])
            output.write_bytes(b"CLI-PPTX")
            return SimpleNamespace(returncode=0)

        runner = Mock(side_effect=fake_runner)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "presentation").mkdir()
            (root / "presentation" / "cli.py").write_text("# stub", encoding="utf-8")
            path = bot.generate_deck(
                "CLI brief", output_dir=Path(tmp) / "out", runner=runner, root=root
            )
            runner.assert_called_once()
            self.assertIn("presentation.cli", runner.call_args.args[0])
            self.assertEqual(path.read_bytes(), b"CLI-PPTX")

    def test_run_bot_sends_generated_deck_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            stop = threading.Event()
            fake = bot.FakeTelegramAPI(
                [(555, "Please build a deck")], stop_event=stop
            )
            with redirect_stdout(io.StringIO()):
                rc = bot.run_bot(fake, stop_event=stop, output_dir=tmp)
            self.assertEqual(rc, 0)
            self.assertEqual(len(fake.sent_documents), 1)
            record = fake.sent_documents[0]
            self.assertEqual(record["chat_id"], 555)
            self.assertTrue(record["exists"])
            self.assertEqual(Path(record["path"]).suffix, ".pptx")
            self.assertTrue(Path(record["path"]).is_file())

    def test_sigint_sets_stop_event(self):
        stop = threading.Event()
        previous = bot._install_sigint_handler(stop)
        try:
            signal.raise_signal(signal.SIGINT)
            self.assertTrue(stop.is_set())
        finally:
            bot._restore_sigint_handler(previous)

    def test_fake_api_records_send_document(self):
        fake = bot.FakeTelegramAPI([(1, "hi")])
        fake.call("getUpdates", {"offset": 0})
        fake.call("getUpdates", {"offset": 1})
        self.assertEqual([m for m, _ in fake.calls], ["getUpdates", "getUpdates"])
        with patch.object(Path, "is_file", return_value=True):
            fake.send_document(1, "deck.pptx")
        self.assertEqual(fake.sent_documents[0]["path"], "deck.pptx")


class SelfTestModeTests(unittest.TestCase):
    def test_self_test_reports_all_three_proofs(self):
        output = io.StringIO()
        with redirect_stdout(output):
            rc = bot.self_test()
        text = output.getvalue()
        self.assertEqual(rc, 0, text)
        self.assertIn("text message received", text)
        self.assertIn("deck produced", text)
        self.assertIn("sendDocument called with the produced deck path", text)
        self.assertIn("SELF-TEST PASSED", text)

    def test_main_self_test_flag(self):
        output = io.StringIO()
        with redirect_stdout(output):
            rc = bot.main(["--self-test"])
        self.assertEqual(rc, 0)
        self.assertIn("SELF-TEST PASSED", output.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
