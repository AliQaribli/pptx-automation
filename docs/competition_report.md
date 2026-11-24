# Competition / assessment readiness report

Date: 2026-11-24
Repo: `C:\Users\Ali\presentation-agent` (local Git repo, MIT license)

> The exact rubric text was never supplied. This report maps the project to the
> criteria that were stated in the brief: a top-quality repo, a real skill, a
> pipeline using two or more tools, a working live demo, free operation, model
> flexibility, a clean GitHub repo, and privacy.

## Summary verdict

| Criterion | Status | Evidence |
|---|---|---|
| Working end-to-end pipeline | **PASS** | Telegram topic → isolated deck-only bot → deterministic local PPTX build → Telegram file. Verified live 2026-11-24; the user confirmed the deck messages arrived. |
| 2+ tools used in one pipeline | **PASS** | Deck-only Telegram listener, local `python-pptx` engine, direct Telegram document sender, Hermes agent/gateway, Canva MCP (earlier), optional Openverse/Wikimedia image sourcing. |
| Real, reusable skill | **PASS** | `skills/beautiful-deck/SKILL.md` + `references/brief_to_contract.md`; copied into both the operator and deck-only Hermes profiles. |
| Beautiful, informative deck | **PASS (with fallback)** | Editable 16:9 decks, QA-PASS, labelled image slots. Canva designs were created earlier; current decks use the local engine because Canva credit is exhausted. |
| Free by default | **PASS** | Default model is a `:free` SKU; local engine uses only stdlib + `python-pptx`, no API key; no Canva spend after quota exhaustion. |
| Model switching | **PASS (operator chat only)** | `/model` picker; aliases `free`, `mid`, `frontier` configured and `free` tested. The deck bot is intentionally model-independent so replies stay fast and reliable. |
| Top-quality GitHub repo | **PARTIAL** | Local repo has 7 commits, README, architecture, limitations, demo, tests, MIT license, no secrets. Push blocked only because no GitHub remote URL was provided. |
| Privacy / no leaked secrets | **PASS** | Secret-pattern scan clean; `.env`, QR image, and `output/` ignored; bot token and chat ID only in the local Hermes profile. |
| Demo then admin self-test | **PASS** | `TEST_PIPELINE.bat` (one click) + `scripts/demo.py`; admins can also send a topic in Telegram. |
| Individual work | **PASS** | Single-author repo, MIT license. |

## Tool chain actually exercised (current steady state)

1. **Deck-only Telegram listener** — `scripts/deck_bot.py`; accepts only topics, rejects everything else with one fixed line.
2. **Local PPTX engine** — `scripts/deck_from_text.py` builds a QA-PASS 16:9 deck deterministically, with no model and no network calls.
3. **Telegram document sender** — `scripts/send_to_telegram.py`; multipart upload, with a known-IP fallback that rewinds the file handle.
4. **Hermes operator chat** — where model/config changes are made; never on the deck bot.
5. **Canva MCP** — exercised successfully earlier (`GENERATE_DESIGN` → `CREATE_DESIGN_FROM_CANDIDATE` → `GET_EXPORT_FORMATS` → `EXPORT_DESIGN`), but currently blocked by exhausted credit.
6. **Optional free image sourcing** — Openverse → Wikimedia Commons → Pollinations, with credits.

## Canva verification (answers “did it really use Canva?”)

Yes — earlier. A live Canva `SEARCH_DESIGNS` query returned the generated presentations in the **connected Canva connector account**, label `canva_mcp_ogor-backet`:

| Generated title | Pages | Created (Unix) |
|---|---:|---:|
| Presentation - The Renewable Energy Shift | 5 | 1795515966 |
| Presentation - Water Conservation: Every Drop Counts | 5 | 1795516541 |
| Presentation - Electric Vehicles: The Road Ahead | 5 | 1795516672 |
| Presentation - Solar Potential | 5 | 1795516935 |

The exported `.pptx` files were also opened with `python-pptx`: 5 slides, 16:9 (`18288000 x 10287000` EMU). Nothing was fabricated: the deck images, titles, and slide count came from Canva designs.

If you log into Canva with a **different account**, these designs will not appear. Check which account is active, or ask me to reconnect the Canva connector to your preferred account.

**Important current limitation:** at 15:47 on 2026-11-24 `GENERATE_DESIGN` began returning `User has exceeded their credit quota`. From that point the deck bot uses the local PPTX engine for every topic. The decks delivered after that point were **not** Canva-generated; they are editable local PPTX files with labelled image slots. This is a deliberate, reliable fallback, not a claim of live Canva use.

At 17:38 the connector was switched to the user's own Canva account (active label `canva_mcp_batty-unknow`) and a fresh 5-slide generation test was run. Canva replied: `Design generation is not enabled in your team`. So neither connected account can currently generate designs through Canva MCP — one is out of credit, the other has the feature disabled at team level. No premium-only export settings were reachable.

## Model switching: how performance changes

The operator pipeline scripts are model-independent. Switching models changes only the reasoning/tool-calling “brain” in the **operator** chat. The deck-only bot deliberately does **not** call a model: it runs `deck_from_text.py` directly, so a slow or wandering model can never break delivery.

- **`/model`** opens Telegram’s inline picker.
- **`/model free`** → `meituan/longcat-2.5:free` (current default; no cost).
- **`/model mid`** → `openrouter/google/gemini-2.5-flash` (faster, stronger tool use; may cost).
- **`/model frontier`** → `openrouter/anthropic/claude-opus-4.7` (best reasoning; real spend).
- **`/model reset`** returns to the free default.

Performance notes:
- Free models can be slower and occasionally wander; the Canva call chain and the deterministic sender scripts keep the output stable even if reasoning varies.
- A mid-session switch resets the prompt cache; the next turn re-reads the conversation at full input price.
- Switches are session-scoped unless `--global` is used. New sessions start on the configured free default.
- `mid`/`frontier` require that provider to be authenticated and can incur real charges; keep `free` for normal operation.

## Remaining gaps / risks

1. **GitHub push — DONE** — repository is live at `https://github.com/AliQaribli/pptx-automation.git`, branch `main` at commit `7466a7c`. No token was pasted in chat.
2. **Exact rubric** — share the competition text if you want a line-by-line score prediction.
3. **Canva account visibility** — earlier designs live in the connector account, not necessarily the one in your browser.
4. **Canva credit exhausted** — the current deck bot uses the local PPTX engine; live Canva design will resume only after quota resets or a paid plan is connected.
5. **Frontier cost** — opt-in only; default stays free.

## Evidence commands

```bash
python scripts/demo.py                         # PASS (0 errors, 0 warnings)
python -m pytest tests/test_telegram_bot.py -q # 19 passed
python scripts/telegram_bot.py --self-test     # SELF-TEST PASSED
python scripts/deck_from_text.py "space exploration"           # DECK:<absolute path>
python scripts/send_to_telegram.py --caption "test" <deck.pptx> # SENT:<path>
hermes -p testad config get model --json                       # aliases configured
```

Git history includes: `8f37ddc`, `03a7755`, `8261101`, `327b238`, `da8290b`,
`b1fd6dc`, `c19400a`, `1a6b789`, and `74045c9`.
