# PptxGenJS presentation pipeline

Minimal end-to-end implementation of the project brief: topic → researched slide plan → editable PPTX → rendered slides → visual inspection → correction → final file.

## Install

From `C:\Users\Ali\presentation-agent`:

```bash
npm install
```

`pptxgenjs` is pinned in `package.json`. Node and npm are required.

## Files

- `plans/renewable_energy.json` — structured slide plan (the LLM-authored design/research output).
- `scripts/build_deck.js` — PptxGenJS renderer; reads a plan and writes an editable `.pptx`.
- `scripts/render_deck.ps1` — renders every slide to PNG via installed Microsoft PowerPoint COM automation.
- `scripts/run_pipeline.py` — one-command build + render + contact sheet.
- `output/renewable_energy/deck.pptx` — final editable deck.
- `output/renewable_energy/render/` — slide images and `contact_sheet.png`.
- `output/renewable_energy/qa_report.md` — citation verification report.

## Run

```bash
python pptxgen/scripts/run_pipeline.py pptxgen/plans/renewable_energy.json pptxgen/output/renewable_energy/deck.pptx
```

Then inspect `contact_sheet.png` with a vision-capable model, fix the affected slide(s) in the plan or in `build_deck.js`, and rerun. Limit corrections to 2–3 rounds.

## Telegram wiring

`scripts/deck_bot.py` now builds every Telegram deck through this pipeline:

1. `python scripts/llm_topic_to_plan.py "<topic>" <plan.json>` → `PLAN:<path>` (model writes topic-specific content in the user's language; safe schema + deterministic base).
2. If step 1 fails, `python scripts/topic_to_plan.py "<topic>"` → `PLAN:<path>` (offline fallback).
3. `node pptxgen/scripts/build_deck.js <plan> <deck.pptx>` → `PPTX:<path>`
4. Existing Telegram `sendDocument` delivery.

`llm_topic_to_plan.py` uses the Hermes CLI with the `free` tier by default (`DECK_PLAN_MODEL` overrides it) and writes no external facts. `topic_to_plan.py` is deterministic and offline. The older `deck_from_text.py` remains only as a last-resort safety fallback. Canva is not called anywhere in this path.

## Renderer note

The brief asks for LibreOffice. LibreOffice is **not installed** on this PC (verified). Microsoft PowerPoint **is** installed, and `render_deck.ps1` uses its COM automation to export PNGs. This is the verified local substitute. No new global tool was installed.

## Layout library implemented

`cover`, `statement`, `chart`, `compare`, `process`, `quote`, `summary`, `sources`. These cover hero, key statistic, data chart, comparison, system/process, quotation, conclusion, and references.

## Design rules applied

One message per slide; 13.333×7.5 in 16:9 canvas; 0.7 in margins; restrained navy/teal/gold palette for this topic; strong typographic hierarchy; native editable text, shapes and chart; sources on the final slide and source lines on factual slides; speaker notes on content slides.

## Verified result

- 8 slides, 13.333×7.5 in, 170 KB.
- Rendered to 8 PNGs at 960×540.
- Visual inspection: no clipping, overlap, poor contrast, overcrowding, misleading charts or missing sources after one correction round.
- `python-pptx` reopened the file: all 8 slides and speaker notes present.
- Citation check: 6 factual sentences, 5 cited, 83% provenance, `citations OK`.
