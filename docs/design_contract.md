# Beautiful Presentation — Design Contract & Slide Recipe Book

This is the binding visual spec for every deck the agent produces. It is written
for an agent to execute without further design questions. Follow it literally;
deviate only when the brief explicitly overrides a rule.

Deliverable: an editable **PPTX** is the default output. A **PDF** is acceptable
only when requested or when PPTX generation is impossible. No other formats.

---

## 0. Non-negotiables

1. **Aspect ratio 16:9** — slide size exactly `13.333 × 7.5 in`. Never 4:3.
2. **Length 5–10 slides.** Default 7. Never fewer than 5, never more than 10.
3. **One idea per slide.** If a slide needs "and" to connect two ideas, split it.
4. **The headline is the conclusion, not the topic.** Write "Revenue grew 34% in
   Q3," not "Q3 Revenue." A reader who skims only titles must get the whole story.
5. **Palette = exactly 4 colours:** two topic-derived colours (`C1`, `C2`), one
   neutral dark (`DARK`), and white (`#FFFFFF`). No other fills or text colours.
6. **Forbidden:** purple gradients, glow/outer-shadow effects, neumorphism,
   emoji-as-icons, clip-art, stock-photo watermarks, licensed Canva Pro elements.
   Icons are simple geometric shapes or free Canva line icons only.
7. **Grid:** all objects snap to an 8-column × 6-row grid (the "6×8 grid":
   6 rows, 8 columns) with uniform margins. See §2.
8. **One accent bar per slide** — no more, no less. See §3.3.
9. **Slide number bottom-right + thin footer line** on every slide except the
   title slide. See §3.4.
10. **Max two fonts** across the whole deck (one heading, one body is ideal).
11. **Text ≤ ~40% of the slide area** (proxy: ≤ 40 on-slide words; aim ≤ 30).
12. **Imagery:** one hero image + 2–3 supporting images per deck. No slide with
    more than one dominant image. See §5.
13. **Sources/credits slide is last.** Every deck ends with it. See recipe §7.8.
14. **Free Canva elements only.** If an asset requires Canva Pro or returns
    `license_required`, substitute a free element or a vector shape — never pay,
    never ship a licensed watermark, never silently drop the credit.

---

## 1. Colour system

Derive colours from the topic before layout; do not pick generic blues.

- `C1` — **primary accent**, the dominant topic colour. Use for the accent bar,
  key numbers, and the most important callout. Target ~15% of slide area.
- `C2` — **secondary accent**, a harmonious but clearly different hue from C1.
  Use for supporting marks, chart series #2, comparison "other" side. ~10%.
- `DARK` — **neutral dark** for body text on light backgrounds and for full-
 bleed overlay backgrounds. Use `#12161F` unless the topic demands another
  near-black; keep contrast ≥ 7:1 against white.
- `WHITE` — `#FFFFFF`, text on `DARK` and negative space on light slides.

Rules:
- Backgrounds are **either** `WHITE` (light slide) **or** `DARK` (dark slide).
  Never a mid-tone, never a gradient fill.
- A light slide uses `DARK` text; a dark slide uses `WHITE` text. `C1`/`C2` are
  used for emphasis only, never as large body-text colour.
- Tints (e.g., C1 at 10–15% opacity) are allowed **only** as table row shading or
  image overlays. They do not count as new colours.
- Contrast check: `C1` and `C2` must each be readable on the chosen background
  (≥ 4.5:1 for text/numbers). If not, deepen them before proceeding.

---

## 2. Grid & spacing (numbers are in inches)

- Canvas: `13.333 × 7.5 in`.
- **Margin: 0.60 in on all four edges.** Safe area = `12.13 × 6.30 in`,
  origin at `(0.60, 0.60)`.
- **Grid: 8 columns × 6 rows**, gutter `0.15 in`.
  - Column width ≈ `1.39 in`; row height ≈ `0.93 in`.
  - Column x-positions: `0.60, 2.14, 3.68, 5.22, 6.76, 8.30, 9.84, 11.38`.
  - Row y-positions: `0.60, 1.68, 2.76, 3.84, 4.92, 6.00`.
- Align every text box, image, bar, and shape to a grid line or span an exact
  number of columns/rows. No arbitrary placements.
- Standard content blocks:
  - **Full-width title band:** cols 1–8, rows 1–2 (y `0.60–1.53`).
  - **Body zone:** cols 1–8, rows 3–5 (y `2.76–4.92`).
  - **Footer zone:** row 6 (y `6.00–6.93`).
- Whitespace ≥ `0.30 in` between any two text blocks. Crowding is a fail.

---

## 3. Repeating elements

### 3.1 Slide title
- Position: cols 1–8, top of safe area. Baseline at y ≈ `1.15 in`.
- States the conclusion (§0.4). One or two lines maximum.
- Font: heading, `32–38 pt`, bold. Left-aligned.
- Optional kicker/eyebrow above title: `11 pt`, `C1`, uppercase, letter-spaced —
  used on section slides only.

### 3.2 Subtitle / deck or section label
- `16–20 pt`, regular, `DARK`/`WHITE` at 70% opacity. Sits directly under title.

### 3.3 Accent bar (exactly one per slide)
- Dimensions: `0.10 in` thick; length `1.6–2.4 in` (≈ 1.5 columns).
- Colour: `C1` (or `C2` on the "other" side of a comparison slide).
- Placement: directly under the title, left-aligned to the title's left edge,
  OR full-bleed at the very top edge of the slide. Pick one treatment and keep
  it identical on every slide of the deck.

### 3.4 Footer line + slide number
- Footer line: `0.5 pt` hairline, `DARK`/`WHITE` at 25% opacity, spanning
  cols 1–8 at y = `6.90 in`.
- Slide number: bottom-right, `10–11 pt`, same muted colour, right-aligned to
  the right margin at y ≈ `7.02 in`. Format `03 / 08` (current / total).
- Omit both on the title slide and credits slide only.

---

## 4. Typography

- **Max two fonts.** Recommended pair: a geometric sans for headings
  (e.g., Aptos Display / Montserrat) + a neutral sans for body
  (e.g., Aptos / Inter / Calibri). If only one font is reliably installed, use
  one family with two weights — this is preferred over a broken fallback.
- Size scale (pt):

  | Role | Size | Weight | Line spacing |
  |---|---|---|---|
  | Slide title | 32–38 | Bold | 1.05 |
  | Section kicker | 11 | Semibold, uppercase | 1.0 |
  | Subtitle / standfirst | 16–20 | Regular | 1.25 |
  | Body | 16–18 | Regular | 1.20 |
  | Big number / KPI | 48–64 | Bold | 1.0 |
  | Label / caption / axis | 11–13 | Regular | 1.15 |
  | Slide number | 10–11 | Regular | 1.0 |

- Body copy: never more than **3 lines per block**, never a paragraph wall.
- Sentence case everywhere except the optional one-word kicker.
- Numbers in charts and KPIs use tabular figures; no thousands-separator
  ambiguity (e.g., `1.2M`, `34%`).
- Text colour: solid `DARK` or `WHITE` only (plus the 70% muted variant for
  subtitles). Never coloured body text, never pure-black `#000000`.

---

## 5. Imagery & icons

- **Per deck:** exactly **one hero image** (the visual anchor, used on the title
  or problem slide) and **2–3 supporting images** (used on data/comparison/
  closing slides). Count them before shipping.
- **Treatment — pick one and hold it constant:**
  - **Full-bleed overlay:** image covers the entire slide; place a `DARK` tint
    at 55–70% opacity over it; all text is `WHITE`. Or
  - **Consistent crop:** every image uses the same aspect ratio (16:9 or 4:3),
    same corner radius (0 or 0.10 in — no mixed), and sits inside a grid-aligned
    frame.
- Crop focal point intentionally (faces/subject off-centre, never decapitated).
- Images must be high-resolution (≥ 1600 px on the long edge), unlicensed-free
  or with a free Canva/source credit recorded for the credits slide.
- **Icons = free Canva line icons or primitives** (circle, square, arrow, bar).
  No emoji. No glyph-as-icon. Keep icon stroke `1.5–2 pt`, colour `C1` or `DARK`.
- Every external image, font, and Canva element is listed on the credits slide
  with author + source URL.

---

## 6. Charts, bars & numbers

- Prefer simple **horizontal bars** over pie/donut/3D charts. No chart junk.
- Bars: solid `C1`, height `0.35–0.45 in`, gap `0.20 in`, rounded corners 0.
  Comparison second series uses `C2`. No shadows, no gradients.
- Axes: hide gridlines except baseline; labels `11–13 pt`; show units.
- Every chart gets a **one-line takeaway** above it, written as a conclusion
  (e.g., "C1 costs 3× less per install").
- KPI blocks: big number `48–64 pt` in `C1`, label `12 pt` beneath in muted
  text. One KPI per grid cell pair; max 3 KPIs per slide.
- Data must be real. If a figure is unavailable, omit the chart rather than
  inventing numbers.

---

## 7. Slide recipes

Each recipe names grid spans (cols / rows), text roles, and imagery.

### 7.1 Title slide
- Layout: full-bleed overlay hero **or** light slide with hero image in cols 5–8.
- Title (conclusion-style): cols 1–8, rows 2–3, `36–38 pt`.
- Subtitle: one line under title, `18 pt`.
- Accent bar under title. No slide number / footer.
- Small kicker (speaker, date, series) optional, `11 pt`, muted.
- One hero image only.

### 7.2 Agenda slide
- Title: "What we'll cover" is acceptable here (it is a map, not an argument).
- 3–5 numbered items stacked in cols 2–7, one per row, `18–20 pt`.
- Number each `01, 02, 03…` in `C1`, `24 pt`, set in a narrow col-1 slot.
- Thin `DARK`/`WHITE` 25% divider between rows. No images.

### 7.3 Problem slide
- Title states the pain as a conclusion: "Manual handoffs cost teams 6 hrs/wk."
- Left half (cols 1–4): 2–3 short symptom lines, `16–18 pt`, each with a
  `C1` square bullet.
- Right half (cols 5–8): supporting image or one striking KPI in `C1`.
- Emphasise the single most important number at `48–64 pt`.

### 7.4 Data slide
- Title states the finding, not "Results."
- Takeaway line `18 pt` at top of body zone.
- Chart occupies cols 1–6, rows 3–5; callout/KPI block in cols 7–8.
- Supporting image only if it adds evidence; otherwise text + chart only.
- Source note `11 pt` in footer zone above the hairline.

### 7.5 Comparison slide
- Title states the verdict: "Option A wins on cost and speed."
- Two equal panels: cols 1–4 (`C1` accent bar) vs cols 5–8 (`C2` accent bar).
- Panel headers `20 pt` bold; 3–4 comparison rows, `16 pt`, aligned baselines.
- Highlight the winning row with a 10% `C1` tint. Avoid "vs" clip art.

### 7.6 Roadmap / timeline slide
- Title states the endpoint: "Ship v1 in three 2-week phases."
- Horizontal timeline across cols 1–8, row 4, baseline `2 pt` `DARK` 25%.
- 3–5 milestones as `C1` circles (`0.18 in`) with `12 pt` date labels above,
  `14 pt` description below. Alternate labels above/below to prevent collision.
- Current phase filled `C1`, future phases outlined `C1` at 50%.

### 7.7 Closing slide
- Title states the ask or the singular takeaway (call-to-action), `32–38 pt`.
- One supporting image in cols 5–8 (consistent crop) OR a single big `C1` KPI.
- Optional CTA line + contact handle `16–18 pt`, `C1`.
- Accent bar present. Footer/slide number present.

### 7.8 Credits / sources slide (always last)
- Title: "Sources & credits", `28–32 pt`.
- Two-column list, `11–12 pt`: left = content sources (author, title, URL);
  right = image/font/Canva-element credits (creator, source, licence).
- Small note: "Built with free assets only." `11 pt`, muted.
- Footer line present; slide number present (`08 / 08`).

---

## 8. Visual QA checklist

Run this before delivery. Any "no" → fix and re-check.

**Structure**
- [ ] Slide size is 13.333 × 7.5 in (16:9); 5–10 slides.
- [ ] Exactly one idea per slide; every title states a conclusion (except
      agenda/credits).
- [ ] Credits slide is the final slide; all sources credited.

**Colour & style**
- [ ] Only 4 colours present: C1, C2, DARK, WHITE (plus allowed tints).
- [ ] Colours derived from topic; contrast ≥ 4.5:1 on the chosen background.
- [ ] No purple gradients, no glow/shadow, no emoji icons, no clip art.
- [ ] Accent bar: exactly one per slide, same treatment throughout.

**Grid & type**
- [ ] All objects snap to the 8×6 grid; margins 0.60 in uniform.
- [ ] Max two fonts; sizes match the scale in §4; no text under 10 pt.
- [ ] Text occupies ≤ ~40% of slide area (≤ 40 words; ideally ≤ 30).
- [ ] No text block longer than 3 lines; no orphaned single words.

**Images & charts**
- [ ] One hero + 2–3 supporting images; all high-res and consistently treated.
- [ ] No cropped-off faces/subjects; overlays keep text readable.
- [ ] Charts are simple bars, no chart junk; every chart has a takeaway line.
- [ ] Only free Canva elements used; no `license_required` assets; credits listed.

**Finishing**
- [ ] Footer hairline + slide number bottom-right on all but title/credits.
- [ ] Numbers and units are correct and consistent across slides.
- [ ] PPTX opens in PowerPoint and is editable; PDF requested only if asked.
- [ ] Render/inspect every slide (or at minimum read the deck outline) and
      confirm nothing overflows, overlaps, or is invisible on the background.
