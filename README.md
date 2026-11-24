# Beautiful Deck Agent

Turn one short Telegram message into a beautiful, editable presentation — delivered back into the same chat.

`Beautiful Deck Agent` is a Hermes agent that reads a plain-text brief, plans the slides, builds the deck through **Canva MCP** (or a deterministic, offline **local PPTX engine** when Canva is unavailable), and sends the finished file to the requester. It is built for a phone-first workflow: send a brief from Telegram, get an editable deck back, no laptop required.

> **Status:** the local PPTX engine and the Telegram bridge are verified — a Telegram `ping` produced a reply on 2026-11-24. Canva MCP delivery is documented but not live-tested here — see [limitations](docs/limitations.md).

## What it does

- Accepts a one-line brief in a Telegram DM (topic, audience, slide count, tone).
- Applies a strict design contract — 16:9, 5–10 slides, conclusion-style titles, a fixed palette and grid, and a sources/credits slide — so output is consistent and editable ([design contract](docs/design_contract.md)).
- Builds the deck with **Tool 1: Canva MCP** (generate → materialize → export), or falls back to **Tool 2: local PPTX engine** (`python-pptx`, offline, deterministic) when Canva is blocked, rate-limited, or returns `license_required` ([Canva MCP](docs/canva_mcp.md), [PPTX fallback](docs/pptx_fallback.md)).
- Sources free, properly credited imagery and records attribution on a credits slide ([image sourcing](docs/image_sourcing.md)).
- Delivers the `.pptx` back into the same chat as an editable document, plus a short, honest note if a fallback was used ([architecture](docs/architecture.md)).
- Lets you change the driving model from Telegram with a single slash command, with a free-by-default setup ([model switching](docs/model_switching.md)).

## The 90-second demo

One happy path, from a phone:

| Time | Beat | What happens |
|------|------|--------------|
| 0:00 | Hook | "I'll make a presentation from my phone by sending one message." |
| 0:08 | Send brief | Type: *"5 slides introducing urban gardening to new tenants, clean and modern."* |
| 0:18 | Bridge | The bot acknowledges the brief (the smoke-test "Pong" path if showing setup). |
| 0:28 | Agent | The log shows the brief parsed, slides planned, tool chosen. |
| 0:40 | Tool 1 | The Canva MCP call produces the design. |
| 0:55 | Tool 2 | "If Canva isn't available, the agent falls back to a local PPTX" — an editable file with a credits slide is generated. |
| 1:10 | Delivery | The `.pptx` appears in the chat; tap to open. |
| 1:20 | Proof | Flip through two slides and tap a text box to show it's editable. |
| 1:28 | Close | One honest limitation line, then stop. |

Keep the brief generic and the chat area redacted — no real names, IDs, or private messages on screen. Have a pre-generated local deck ready as a backup in case the live tool call is slow.

For the full script with demo-hygiene checks, see [§4 of the repo blueprint](docs/repo_blueprint.md).

## Setup (no secrets in this repo)

Nothing in this repository contains a real token, chat ID, or personal data. Real values stay in your local, git-ignored `.env` and Hermes config.

```bash
# 1. Local secrets file — placeholders only, never commit it
cp .env.example .env
#    For the standalone bot, add TELEGRAM_BOT_TOKEN here.
#    For the Hermes gateway path, use dashboard QR pairing; it stores the
#    token in the local Hermes profile .env, never in this repo.

# 2. Install the one real dependency (stdlib covers the rest)
pip install python-pptx

# 3. Prove the local engine works (offline, no secrets, no network)
python scripts/demo.py

# 4. Prove the Telegram bridge logic offline (no network, no secrets needed)
python scripts/telegram_bot.py --self-test

# 5. Prove the Telegram bridge (needs the token from step 1)
python scripts/telegram_smoke_test.py

# 6. Start the Hermes messaging gateway to receive briefs in Telegram
hermes gateway restart
```

## Verification

These commands were run on the finished repo:

```
$ python scripts/demo.py
Deck:     output\brief\deck.pptx
QA report:output\brief\qa_report.json
Slides:   7
Status:   PASS (0 errors, 0 warnings)

$ python -m pytest tests/test_telegram_bot.py -q
19 passed in 0.89s

$ python scripts/telegram_bot.py --self-test
SELF-TEST PASSED
```

- `.env` is listed in `.gitignore` — **never commit it**, and never paste its values into a brief, a slide, a log, or this README.
- Create the bot with @BotFather or the desktop app's Messaging → Telegram → "Create with QR" button. Keep the QR/pairing image local and redacted ([limitations](docs/limitations.md)).
- All model credentials are owned by the Hermes connector; project code never handles them.

## Changing the model from Telegram

Model changes are made from the bot DM — **no code edits needed** for day-to-day switching:

| Command | Effect |
|---------|--------|
| `/model` | Opens the inline picker of available providers/models. |
| `/model free` / `/model mid` / `/model frontier` | Switch this session to a tier alias. |
| `/model frontier --once` | Use a frontier model for one message, then revert. |
| `/model free --global` | Make a tier the persistent default. |
| `/model reset` | Clear the override and return to the configured default. |
| `/status` | Show the current model and provider. |

One-time setup (run locally): use `hermes model` to authenticate a provider, then define the `free` / `mid` / `frontier` aliases in your profile config. See [model switching](docs/model_switching.md) for the exact commands and flags.

## Free vs paid model flexibility

The agent is **free by default** and **opt-in for paid tiers**. The three tiers are user-defined **aliases** that each point at a provider/model pair you choose — for example a `:free` SKU for `free`, a flash/mini model for `mid`, and a top-tier model for `frontier`. A fresh DM starts on `free`; you escalate for a single hard question with `/model frontier --once` or for a session with `/model mid`, and switch back with `/model free`. Aliases resolve to explicit providers, so a tier switch cannot leak one vendor's credentials to another, and `mid`/`frontier` can incur real spend — use them deliberately. Details and the recommended free-by-default config are in [model switching](docs/model_switching.md).

## Documentation

- [Architecture](docs/architecture.md) — flowchart and component table.
- [Design contract](docs/design_contract.md) — the binding visual spec and slide recipes.
- [Canva MCP](docs/canva_mcp.md) — exact tool calls, candidate selection, errors, rate limits.
- [PPTX fallback](docs/pptx_fallback.md) — the offline engine contract and design rules.
- [Image sourcing](docs/image_sourcing.md) — free-first imagery and credits.
- [Model switching](docs/model_switching.md) — `/model` from Telegram and alias setup.
- [Limitations](docs/limitations.md) — honest constraints and workarounds.
- [Repo blueprint](docs/repo_blueprint.md) — structure, full demo script, safety checklist.

## License

MIT — see [LICENSE](LICENSE).
