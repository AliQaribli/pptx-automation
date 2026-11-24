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
| Working end-to-end pipeline | **PASS** | Telegram topic → agent → Canva MCP → finished deck → Telegram file. Verified live rehearsal on 2026-11-24 (“solar energy”, 5 slides, 2m14s). |
| 2+ tools used in one pipeline | **PASS** | Hermes agent/gateway, Canva MCP (generate/create/export), local `python-pptx` fallback engine, direct Telegram document sender, optional Openverse/Wikimedia image sourcing. |
| Real, reusable skill | **PASS** | `skills/beautiful-deck/SKILL.md` + `references/brief_to_contract.md`; copied into the active Hermes profile and enabled. |
| Beautiful, informative deck | **PASS** | Canva designs with 5 slides, 16:9, real templates and images. Local fallback produces QA-PASS decks with labelled image slots when Canva is unavailable. |
| Free by default | **PASS** | Default model is a `:free` SKU; Canva free-plan assets; local engine uses only stdlib + `python-pptx`, no API key. |
| Model switching | **PASS (after fix)** | `/model` inline picker; aliases `free`, `mid`, `frontier` configured. Broken default `poolside/laguna-s-2.1:free` replaced with working `meituan/longcat-2.5:free`. Alias `free` tested with an actual reply. |
| Top-quality GitHub repo | **PARTIAL** | Local repo has 7 commits, README, architecture, limitations, demo, tests, MIT license, no secrets. Push blocked only because no GitHub remote URL was provided. |
| Privacy / no leaked secrets | **PASS** | Secret-pattern scan clean; `.env`, QR image, and `output/` ignored; bot token and chat ID only in the local Hermes profile. |
| Demo then admin self-test | **PASS** | `TEST_PIPELINE.bat` (one click) + `scripts/demo.py`; admins can also send a topic in Telegram. |
| Individual work | **PASS** | Single-author repo, MIT license. |

## Tool chain actually exercised

1. **Hermes Telegram gateway** — receives the topic and starts the agent turn.
2. **Canva MCP** — `GENERATE_DESIGN` → `CREATE_DESIGN_FROM_CANDIDATE` → `GET_EXPORT_FORMATS` → `EXPORT_DESIGN`.
3. **Local PPTX engine** — fallback via `scripts/deck_from_text.py` when Canva is unavailable or rate-limited.
4. **Telegram document sender** — `scripts/send_to_telegram.py`, deterministic multipart upload through the Bot API.
5. **Optional free image sourcing** — Openverse → Wikimedia Commons → Pollinations, with credits.

## Canva verification (answers “did it really use Canva?”)

Yes. A live Canva `SEARCH_DESIGNS` query returned the generated presentations in the **connected Canva connector account**, label `canva_mcp_ogor-backet`:

| Generated title | Pages | Created (Unix) |
|---|---:|---:|
| Presentation - The Renewable Energy Shift | 5 | 1795515966 |
| Presentation - Water Conservation: Every Drop Counts | 5 | 1795516541 |
| Presentation - Electric Vehicles: The Road Ahead | 5 | 1795516672 |
| Presentation - Solar Potential | 5 | 1795516935 |

The exported `.pptx` files were also opened with `python-pptx`: 5 slides, 16:9 (`18288000 x 10287000` EMU). Nothing was fabricated: the deck images, titles, and slide count came from Canva designs.

If you log into Canva with a **different account**, these designs will not appear. Check which account is active, or ask me to reconnect the Canva connector to your preferred account.

## Model switching: how performance changes

The pipeline scripts are model-independent. Switching models changes only the reasoning/tool-calling “brain”:

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

1. **GitHub push** — provide the remote URL (e.g. `https://github.com/<user>/<repo>.git`) and I will push; no token needs to be pasted in chat.
2. **Exact rubric** — share the competition text if you want a line-by-line score prediction.
3. **Canva account visibility** — designs live in the connector account, not necessarily the one in your browser.
4. **Canva rate limits/license prompts** — handled by automatic local fallback; the user still receives a file.
5. **Frontier cost** — opt-in only; default stays free.

## Evidence commands

```bash
python scripts/demo.py                         # PASS (0 errors, 0 warnings)
python -m pytest tests/test_telegram_bot.py -q # 19 passed
python scripts/telegram_bot.py --self-test     # SELF-TEST PASSED
python scripts/send_to_telegram.py --caption "test" <deck.pptx>  # SENT:<path>
hermes -p testad config get model --json       # aliases configured
```

Git history includes: `8f37ddc`, `03a7755`, `8261101`, `327b238`, `da8290b` and later wiring commits.
