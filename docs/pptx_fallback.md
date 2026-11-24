# Local PPTX fallback engine — design note

Status: proposed. This document is the contract for the deterministic, offline
fallback that produces the deck when Canva MCP is unavailable or unsafe to use
(`license_required` premium elements, rate limits, async generation delays).
No network, no account, no paid assets are required to render.

Goals, in priority order:

1. Always produce a clean, editable, on-brand deck from a plain data object.
2. Deterministic: same input -> same `pptx` bytes (modulo ZIP timestamps).
3. Free & private: `python-pptx` + the Python stdlib only; no cloud calls.
4. Small enough to send over Telegram (< 50 MB document limit).

PPTX is the primary deliverable. PDF is a secondary, optional artifact produced
locally (LibreOffice headless) and only sent when the requester asks for it.

---

## 1. Design rules the renderer enforces

These are not suggestions; they are invariants checked by `qa.py`.

| Rule | Value / enforcement |
|---|---|
| Aspect ratio | 16:9 — `13.333 x 7.5 in` (`12192000 x 6858000` EMU) |
| Slide count | 5–10 inclusive |
| One idea per slide | Each slide object carries exactly one `title` and one primary message |
| Titles | Conclusion-style declarative statements ("Adoption doubled in Q3"), not labels ("Adoption") |
| Palette | 2 topic colours + neutral dark + white, plus neutral grey for secondary text |
| Grid | 6 columns x 8 rows over the safe area; every shape snaps to a cell edge |
| Accent bar | One short bar in topic colour at the top-left of content slides |
| Slide numbers | Bottom-right of every slide except the title slide |
| Fonts | At most 2 families: one heading, one body |
| Text density | Body text occupies < 40% of the safe area (checked by estimated glyph area) |
| Imagery | At least one hero image or labelled image placeholder |
| Sources | Final slide lists sources/credits (even if "None — original analysis") |

### Grid geometry

- Slide: `13.333 x 7.5 in`.
- Safe-area margin: `0.6 in` on all sides -> safe area `12.133 x 6.3 in`.
- 6 columns, 8 rows. Column width `= safe_w / 6`, row height `= safe_h / 8`.
- Gutter: `0.12 in`, subtracted from each cell. A shape spanning `c` columns
  and `r` rows is placed at the cell's top-left and sized to cover the span
  minus the trailing gutter.
- Confirmed helper: `grid(x0, y0, cols, rows) -> (left, top, width, height)`
  in `theme.py`. All layout goes through it; no hard-coded inches elsewhere.

### Palette (example defaults, overridable per deck via the theme block)

| Token | Default | Use |
|---|---|---|
| `color_primary` | `#1F6FEB` | Accent bar, headings emphasis, key figure |
| `color_secondary` | `#F2A900` | Secondary highlight, alternate column |
| `neutral_dark` | `#12141A` | Background of title/closing slides, body text on light |
| `white` | `#FFFFFF` | Text on dark, light slide background |
| `grey` | `#6B7280` | Captions, source lines, slide numbers |

Two topic colours + neutral dark + white; grey is a neutral for legibility, not
a third topic colour.

---

## 2. Module layout

Proposed package (new files only; nothing outside `docs/` is created by this
task):

```
presentation-agent/
├── docs/
│   └── pptx_fallback.md          # this design note
├── scripts/
│   └── telegram_smoke_test.py    # existing Telegram bridge check
├── presentation/                 # new package — the fallback engine
│   ├── __init__.py               # public API: render(contract, out_dir) -> Path
│   ├── contract.py               # dataclasses + validate(); parses contract JSON
│   ├── theme.py                  # palette, grid(), font sizes, EMU helpers
│   ├── render_pptx.py            # python-pptx renderer (core engine)
│   ├── images.py                 # resolve/normalize/placeholder images
│   ├── qa.py                     # static + post-render checks
│   └── cli.py                    # `python -m presentation.cli contract.json`
├── output/                       # generated artifacts (gitignored)
│   └── <job-id>/
│       ├── deck.pptx
│       ├── deck.pdf                # optional
│       └── qa_report.json
└── README.md
```

Responsibilities are kept narrow: the agent (LLM) only ever emits a **contract
JSON** (section 3). It never writes python-pptx code. `render_pptx.py` is a pure
function of that contract, which is what makes the output deterministic and
cheap to QA.

---

## 3. Data contract (agent -> renderer)

The agent produces one UTF-8 JSON object. `contract.py` parses it into typed
dataclasses and **fails closed**: any validation error aborts rendering with an
actionable message rather than emitting a broken deck.

```jsonc
{
  "version": 1,
  "meta": {
    "title": "Q3 Review",                 // short, used in filename/metadata
    "subtitle": "Growth, retention, and what changed",
    "language": "en",                     // BCP-47 tag, for font fallback
    "theme": {                            // optional; defaults shown if omitted
      "color_primary": "#1F6FEB",
      "color_secondary": "#F2A900",
      "neutral_dark": "#12141A",
      "white": "#FFFFFF",
      "font_heading": "Aptos Display",    // heading family
      "font_body": "Aptos"                // body family (2 fonts max)
    }
  },
  "slides": [
    {
      "kind": "title",                    // see allowed kinds below
      "title": "Growth accelerated in Q3",// conclusion-style, declarative
      "kicker": "Q3 2026 review",         // optional eyebrow above title
      "body": ["Short supporting line."], // <= 3 items; each <= ~90 chars
      "notes": "Speaker notes (optional)",
      "image": { "path": "assets/hero.png", "credit": "Original", "layout": "right" }
    },
    {
      "kind": "bullets",
      "title": "Three levers drove the result",
      "body": ["Price test lifted ARPU 12%", "Churn fell after onboarding revamp", "Referrals doubled reach"],
      "notes": "..."
    },
    {
      "kind": "metrics",
      "title": "Revenue grew 34% while costs held flat",
      "metrics": [
        { "value": "34%", "label": "Revenue growth" },
        { "value": "+1.2M", "label": "New users" },
        { "value": "0.9x", "label": "Cost ratio" }
      ]
    },
    {
      "kind": "two_column",
      "title": "Keep the wins, fix the leaks",
      "columns": [
        { "heading": "Worked", "body": ["...", "..."] },
        { "heading": "Fix next", "body": ["...", "..."] }
      ]
    },
    {
      "kind": "image_hero",
      "title": "Usage clustered in three markets",
      "image": { "path": "assets/map.png", "credit": "Internal data", "layout": "full" },
      "caption": "Share of sessions by market"
    },
    {
      "kind": "closing",
      "title": "Double down on retention in Q4",
      "body": ["One next step, one owner, one date."]
    },
    {
      "kind": "sources",
      "title": "Sources and credits",
      "sources": [
        { "label": "Internal analytics export", "url": "" },
        { "label": "Market size report", "url": "https://example.org/report" }
      ]
    }
  ]
}
```

### Allowed `kind` values

`title`, `statement`, `bullets`, `metrics`, `two_column`, `image_hero`,
`closing`, `sources`. Unknown kinds are a validation error.

### Field rules

- `version` MUST be `1`. Unknown versions are rejected.
- `slides` length MUST be 5–10; the last slide MUST be `kind: "sources"`.
- Every slide MUST have a non-empty `title`; titles MUST be declarative
  statements (heuristic: no trailing colon, not a single noun phrase, >= 4
  words) — flagged in QA rather than hard-failed, so the agent can revise.
- Per slide: `body` <= 3 items, each <= 90 characters; `notes` is free text.
- `theme` colours MUST be `#RRGGBB`; fonts MUST come from a small allowlist
  installed locally (e.g. Aptos, Calibri, DejaVu Sans) so rendering is stable.
- No field may contain credentials, tokens, personal data, or absolute paths
  outside the job directory. `contract.py` scrubs obvious `KEY=VALUE` secrets
  and rejects paths containing `..`.
- Image `path` is relative to the job directory; remote URLs are NOT accepted
  in the contract (see section 5).

---

## 4. Minimal code sketch (python-pptx)

Illustrative core only; the full renderer adds the layout helpers and QA hooks.
Uses only `python-pptx` and the stdlib.

```python
# presentation/render_pptx.py  (minimal sketch)
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

from .contract import Contract, Slide
from . import theme

SW, SH = Inches(13.333), Inches(7.5)   # 16:9


def _rgb(hex_color: str) -> RGBColor:
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _textbox(slide, text, left, top, width, height, *, size=24,
             color="12141A", font="Aptos", bold=False, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = font
    run.font.color.rgb = _rgb(color)
    return box


def _accent_bar(slide, color):
    # Top-left accent bar snapped to grid cell (0,0)-(1,~0.5 row)
    left, top, width, height = theme.grid(0, 0, 1, 0.5)
    bar = slide.shapes.add_shape(1, left, top, width, height)  # 1 = rectangle
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(color)
    bar.line.fill.background()


def _slide_number(slide, number, color):
    left, top, width, height = theme.grid(5, 7, 1, 1)
    _textbox(slide, f"{number:02d}", left, top, width, height,
             size=11, color=color, align=PP_ALIGN.RIGHT)


def _render_content_slide(prs, slide_spec: Slide, number: int, c: Contract):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    t = c.meta.theme

    _accent_bar(slide, t.color_primary)
    _slide_number(slide, number, t.grey)

    # Kicker + conclusion-style title in the top third
    if slide_spec.kicker:
        left, top, w, h = theme.grid(0, 1, 6, 0.6)
        _textbox(slide, slide_spec.kicker.upper(), left, top, w, h,
                 size=12, color=t.color_primary, font=t.font_body, bold=True)
    left, top, w, h = theme.grid(0, 1.6, 6, 1.6)
    _textbox(slide, slide_spec.title, left, top, w, h,
             size=34, color=t.neutral_dark, font=t.font_heading, bold=True)

    # Body block: one idea, < 40% area, snapped to the lower grid
    if slide_spec.body:
        left, top, w, h = theme.grid(0, 3.4, 6, 3.0)
        tb = slide.shapes.add_textbox(left, top, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        for i, item in enumerate(slide_spec.body[:3]):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = "•  " + item
            p.font.size = Pt(18)
            p.font.name = t.font_body
            p.font.color.rgb = _rgb(t.neutral_dark)

    if slide_spec.notes:
        slide.notes_slide.notes_text_frame.text = slide_spec.notes
    return slide


def render(contract: Contract, out_dir: Path) -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = SW, SH
    for i, spec in enumerate(contract.slides, start=1):
        if spec.kind in {"title", "closing"}:
            # dark background, white title (helper omitted for brevity)
            _render_content_slide(prs, spec, i, contract)
        elif spec.kind == "sources":
            _render_content_slide(prs, spec, i, contract)  # + source list
        else:
            _render_content_slide(prs, spec, i, contract)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "deck.pptx"
    prs.save(str(path))
    return path
```

`__init__.py` exposes `render(contract, out_dir) -> Path`; `cli.py` wraps
`Contract.from_json(path)` -> `render()` -> `qa.check()` and writes
`qa_report.json` next to the deck.

---

## 5. Image handling

Policy: **local files only** in the contract. The agent never embeds URLs.

1. **Resolve.** `images.py` accepts a job-relative path under `output/<job-id>/`
   or a curated `assets/` folder. Reject absolute paths and `..` traversal.
2. **Normalize.** Open with Pillow (optional dependency; if absent, copy
   bytes through), strip EXIF (privacy), convert to PNG or JPEG, cap the
   longest edge at 1920 px. Skip re-encoding if already within budget.
3. **Fit, don't distort.** Compute crop to the destination cell's aspect ratio;
   `add_picture(path, left, top, width=..., height=...)` with a centred crop.
4. **Placeholder fallback.** If an image is missing, unreadable, or clearly
   unlicensed, draw a neutral panel: grey fill, a simple line-art icon, and the
   caption text plus `credit` from the contract. The deck still passes QA —
   a labelled placeholder is an allowed "image" state.
5. **Credits.** Every real image carries `credit` in the contract and is
   listed on the sources slide. If no credit is supplied, treat as placeholder.
6. **Budget.** Hard cap total embedded image bytes at ~40 MB so the final PPTX
   stays under the 50 MB Telegram limit. If exceeded, downscale progressively
   or downgrade to placeholders, then re-check.

Remote images, if ever enabled later, must be fetched by a separate,
user-consented step with an HTTPS allowlist — never implicitly by the renderer.

---

## 6. QA checks

`qa.py` runs twice: **pre-render** on the contract (cheap, actionable) and
**post-render** on the file. Results go to `qa_report.json`; any `error` fails
the job, `warning` is reported for the agent to revise.

Pre-render (contract):
- [ ] `version == 1`; 5 <= len(slides) <= 10.
- [ ] Last slide is `sources`; sources is a non-empty list (may say "None").
- [ ] Every slide has a non-empty, declarative conclusion-style title.
- [ ] `body` <= 3 items and each <= 90 chars.
- [ ] Exactly <= 2 font families; colours match `#RRGGBB`.
- [ ] Image paths are job-relative and exist (or are flagged as placeholders).
- [ ] Secret/PII scrub: no `TOKEN=`, no absolute home paths, no email addresses.

Post-render (file):
- [ ] Opens with `Presentation(path)` without exception; slide count matches.
- [ ] `slide_width/slide_height == 16:9` within 1 EMU.
- [ ] Each content slide has exactly one accent bar and (except title) a slide
      number text box.
- [ ] All shape bounds lie inside slide bounds; positions snapped to grid.
- [ ] Estimated text glyph area < 40% of the safe area per slide.
- [ ] At least one image or labelled placeholder exists.
- [ ] Fonts used are within the 2-family allowlist.
- [ ] `path.stat().st_size < 50 * 1024 * 1024` (Telegram limit) — **error**.
- [ ] If PDF produced, it exists and has the same page count as slides.

---

## 7. File-delivery constraints

- **Primary artifact:** `deck.pptx` (editable, preferred). Sent as a Telegram
  document so layout is preserved.
- **Secondary artifact:** `deck.pdf`, generated locally with LibreOffice
  headless (`soffice --headless --convert-to pdf --outdir ... deck.pptx`) only
  on request or when PPTX cannot be delivered; page count must match.
- **Size limit:** Telegram caps documents at **50 MB**. Enforce in QA; keep the
  deck well under it (recommended < 20 MB) via image budgets. If over, shrink
  images or replace with placeholders and re-render — never silently truncate.
- **Output location:** all generated files live under `output/<job-id>/`, which
  is gitignored. No generated deck is committed.
- **Naming:** `<job-id>/deck.pptx` internally; on delivery, a friendly name
  derived from `meta.title` (sanitized: ASCII-safe, no path separators).
- **Privacy:** contracts and output contain no credentials or personal data;
  `.env` values are never read by the renderer. Allowlist/Telegram IDs are the
  bot bridge's concern, not the deck engine's.
- **Idempotence:** re-running the same job overwrites its own `output/<job-id>/`
  files only; it never touches other jobs or project source files.
