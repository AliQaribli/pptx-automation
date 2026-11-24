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
| Working end-to-end pipeline | **PASS** | Telegram topic → isolated deck-only bot → model planner (deterministic fallback) → PptxGenJS editable PPTX → Telegram file. User confirmed deck messages arrived. |
| 2+ tools used in one pipeline | **PASS** | Deck-only Telegram listener, Hermes one-shot model planner, `topic_to_plan.py` fallback, Node/PptxGenJS renderer, PowerPoint COM visual QA, direct Telegram document sender, Hermes operator chat. Canva MCP was used earlier and is now removed. |
| Real, reusable skill | **PASS** | `skills/beautiful-deck/SKILL.md` + `references/brief_to_contract.md`; copied into both the operator and deck-only Hermes profiles. |
| Beautiful, informative deck | **PASS** | Editable 16:9 decks with 8 layout types, real native charts/shapes, visual QA on every rendered slide. Canva designs were created earlier; current decks are built locally with PptxGenJS. |
| Free by default | **PASS** | Default planner tier is a `:free` SKU; PptxGenJS is MIT-licensed and local; no Canva spend. |
| Model switching | **PASS (operator chat only)** | `/model` picker; aliases `free`, `mid`, `frontier` configured and `free` tested. The bot's planner tier is read from `DECK_PLAN_MODEL` (default `free`); `mid` and `frontier` currently return OpenRouter 402 here. |
| Top-quality GitHub repo | **PASS** | Pushed to `https://github.com/AliQaribli/pptx-automation.git`, branch `main`, latest commit matches `origin/main`; README, architecture, limitations, demo, tests, MIT license, no secrets. |
| Privacy / no leaked secrets | **PASS** | Secret-pattern scan clean; `.env`, QR image, and `output/` ignored; bot token and chat ID only in the local Hermes profile. |
| Demo then admin self-test | **PASS** | `TEST_PIPELINE.bat` (one click) + `scripts/demo.py`; admins can also send a topic in Telegram. |
| Individual work | **PASS** | Single-author repo, MIT license. |

## Tool chain actually exercised (current steady state)

1. **Deck-only Telegram listener** — `scripts/deck_bot.py`; accepts only topics, rejects everything else with one fixed line.
2. **Model planner** — `scripts/llm_topic_to_plan.py` writes topic-specific content in the user's language and merges it into the fixed safe schema. Falls back to `scripts/topic_to_plan.py` (deterministic, offline, no external facts) if the model call fails.
3. **PptxGenJS renderer** — `pptxgen/scripts/build_deck.js` turns the plan into an editable PPTX using native text, shapes and charts.
4. **PowerPoint COM visual QA** — `pptxgen/scripts/render_deck.ps1` exports every slide to PNG for inspection; LibreOffice is not installed, so this is the verified local substitute.
5. **Telegram document sender** — direct multipart upload with a known-IP fallback that rewinds the file handle.
6. **Hermes operator chat** — where model/config changes are made; never on the deck bot.

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

**Canva is now out of the critical path.** On 2026-11-24 the user asked for Canva to be removed and the local PptxGenJS tool to be plugged into the Telegram pipeline. `scripts/deck_bot.py` now calls `llm_topic_to_plan.py` → `build_deck.js` for every topic, with `topic_to_plan.py` as the deterministic fallback. The older `deck_from_text.py` remains only as a last-resort safety fallback. Canva MCP is no longer called by the bot, and no Canva account or plan is needed to generate a deck.

**Historical limitation:** at 15:47 on 2026-11-24 `GENERATE_DESIGN` began returning `User has exceeded their credit quota`. Decks delivered after that point and before the PptxGenJS switch used the older local engine. At 17:38 the connector was switched to the user's own Canva account (active label `canva_mcp_batty-unknow`) and a fresh 5-slide generation test returned `Design generation is not enabled in your team`. Neither connected account could generate designs through Canva MCP. No premium-only export settings were reachable. None of this blocks the current pipeline.

## Model switching: how performance changes

The operator chat and the bot's content planner both use Hermes model tiers. Switching models in the operator chat changes the reasoning/tool-calling “brain” there; the deck bot's planner tier is set by `DECK_PLAN_MODEL` (default `free`). Rendering, visual QA and delivery stay deterministic, so a slow or wandering model can never break file delivery.

- **`/model`** opens Telegram’s inline picker.
- **`/model free`** → `meituan/longcat-2.5:free` (current default; no cost).
- **`/model mid`** → `openrouter/google/gemini-2.5-flash` (faster, stronger tool use; may cost).
- **`/model frontier`** → `openrouter/anthropic/claude-opus-4.7` (best reasoning; real spend).
- **`/model reset`** returns to the free default.

Performance notes:
- Free models can be slower and occasionally wander; the strict JSON planner schema, fallback and deterministic sender scripts keep the output stable even if reasoning varies.
- A mid-session switch resets the prompt cache; the next turn re-reads the conversation at full input price.
- Switches are session-scoped unless `--global` is used. New sessions start on the configured free default.
- `mid`/`frontier` require that provider to be authenticated and can incur real charges; keep `free` for normal operation.

## Remaining gaps / risks

1. **GitHub push — DONE** — repository is live at `https://github.com/AliQaribli/pptx-automation.git`, branch `main`. No token was pasted in chat. The latest commit is the one currently at `origin/main`.
2. **Exact rubric** — share the competition text if you want a line-by-line score prediction.
3. **Canva account visibility** — historical only; no longer affects deck generation because the bot does not call Canva.
4. **Topic-only content** — the bot's plan generator adds no outside facts, so decks are structurally strong but not research-heavy. For a researched deck, use the operator chat pipeline.
5. **Frontier cost** — opt-in only; default stays free.

## Evidence commands

```bash
python scripts/demo.py                         # PASS (0 errors, 0 warnings)
python -m pytest tests/test_telegram_bot.py -q # 19 passed
python scripts/telegram_bot.py --self-test     # SELF-TEST PASSED
python scripts/deck_from_text.py "space exploration"           # DECK:<absolute path> (fallback)
python scripts/topic_to_plan.py "space exploration"            # PLAN:<absolute path>
node pptxgen/scripts/build_deck.js <plan.json> <deck.pptx>     # PPTX:<absolute path>
python scripts/send_to_telegram.py --caption "test" <deck.pptx> # SENT:<path>
hermes -p testad config get model --json                       # aliases configured
```

Git history includes: `8f37ddc`, `03a7755`, `8261101`, `327b238`, `da8290b`,
`b1fd6dc`, `c19400a`, `1a6b789`, and `74045c9`.
