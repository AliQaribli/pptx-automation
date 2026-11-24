# Limitations

An honest list of what this agent cannot do today, why, and what was done instead. Name the gap plainly; do not hide failures behind vague "everything works" claims.

## What I couldn't do

- **The Telegram API is currently unreachable from this PC.** Live `getMe`/`getUpdates`/`sendDocument` calls fail from this machine, so the end-to-end "brief in, deck out" chat flow could not be exercised here. A local CONNECT relay (`scripts/telegram_relay.py`) and the smoke test (`scripts/telegram_smoke_test.py`) were written to diagnose/work around it; the offline deck path is verified independently with `scripts/demo.py`. The Telegram bridge logic is in place but its live round-trip remains unverified in this environment.
- **Canva MCP is constrained on a free plan.** Exports must use standard/regular quality — no `export_quality: "pro"`, no lossless PNG, no transparent background. Premium elements return `license_required`, so designs must be regenerated with free-only assets or handed to the local PPTX engine. Export URLs expire after 24 h and must be downloaded immediately; generation/export calls are also rate-limited (~20 req/min). See [Canva MCP](canva_mcp.md).
- **Telegram caps documents at 50 MB.** The delivered `.pptx` (and any PDF) must stay under this limit. The local engine keeps decks small by rendering text and shapes with `python-pptx` and avoiding embedded full-resolution assets; image handling is deliberately conservative to stay within the cap.
- **Model swapping is alias-based, not free-form.** Day-to-day switching works only through the predefined `free` / `mid` / `frontier` aliases, which must be configured once in the Hermes profile config, and each target provider must already be authenticated locally (`hermes model`). Out of the box, a plain `/model <alias>` is session-scoped; `--global` is needed to persist. `mid`/`frontier` can incur real spend. See [model switching](model_switching.md).
- **QR / pairing artifacts must never be committed.** `telegram_qr.png`, bot-invite images, and any screenshots can expose chat IDs, usernames, or private messages. They are covered by the `*.png` rule in `.gitignore`, but must be redacted and deliberately excluded before any commit. The README/example briefs use placeholders only; nothing in this repo contains a real token, user ID, or chat ID.

## What gave me a hard time

- **Reaching Telegram:** network/DNS resolution for `api.telegram.org` failed here. The workaround was a loopback CONNECT relay plus a token-free smoke test to isolate bridge correctness from network reachability; the honest result is that live delivery is still unproven on this machine.
- **Canva's two-step identity:** generation returns candidate/preview IDs that are *not* valid design IDs. Materializing through `CREATE_DESIGN_FROM_CANDIDATE` first was required; guessing an ID from a URL fails export. Candidate selection is human-in-the-loop by default.
- **A guaranteed deliverable:** to make sure a working file always lands, the local PPTX engine was built as a deterministic, offline fallback driven by a strict contract JSON, with a sources/credits slide and QA checks — trading fully bespoke layout for reliability.

## What's next

- Prove the live Telegram round-trip from a network where the API is reachable, and pin the relay fix if it is environment-specific.
- Add automatic, licensed image sourcing into the fallback so decks are illustration-rich without breaching the 50 MB cap.
- Make the free/mid/frontier setup a one-command profile bootstrap so a reviewer can reproduce tier switching without manual config edits.
