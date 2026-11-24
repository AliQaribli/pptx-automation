# Brief → Contract: Prompt Template & Validation Checklist

Use the prompt template in §1 to convert a free-form brief into the single JSON object consumed by `presentation/cli.py`. Validate with §3 before any render call. §2 reproduces the verbatim query template used only for the Canva `GENERATE_DESIGN` call.

## 1. Brief-to-contract prompt template (copy, fill, emit JSON only)

```text
SYSTEM
You are a slide planner. Convert the BRIEF into ONE UTF-8 JSON object that is a
valid presentation contract. Emit only the JSON object — no prose, no code fence,
no [TBD]/[insert] placeholders. Label unknowns as "example values". Never include
credentials, tokens, user IDs, emails, personal data, or absolute paths.

HARD RULES
- "version" MUST be 1.
- "slides" length 5–10 (default 7). The LAST slide MUST be kind "sources".
- Every slide has a non-empty, conclusion-style "title": a declarative statement
  of at least 4 words, no trailing colon, not a bare noun phrase/topic label.
- One idea per slide. "body" <= 3 items, each <= 90 chars; "notes" is free text.
- Allowed "kind" values ONLY: title, statement, bullets, metrics, two_column,
  image_hero, closing, sources.
- "theme" colours are #RRGGBB; at most two font families (font_heading, font_body).
- Image "path" is job-relative (e.g. "assets/hero.png"): no URLs, no "..".
- Every used image carries a "credit" and is listed in the final "sources" slide.

MAP THE BRIEF TO THIS SKELETON
{
  "version": 1,
  "meta": {
    "title": "<short working title; used in filename/metadata>",
    "subtitle": "<one-line standfirst>",
    "language": "<BCP-47 tag, e.g. en>",
    "theme": {
      "color_primary": "<#RRGGBB, topic-derived>",
      "color_secondary": "<#RRGGBB, harmonious distinct hue>",
      "neutral_dark": "<#RRGGBB, near-black>",
      "white": "#FFFFFF",
      "font_heading": "<heading family from local allowlist>",
      "font_body": "<body family from local allowlist>"
    }
  },
  "slides": [
    { "kind": "title", "title": "<conclusion>",
      "kicker": "<optional eyebrow>", "body": ["<supporting line>"],
      "notes": "<speaker notes>",
      "image": { "path": "<job-relative>", "credit": "<credit>", "layout": "<right|full>" } },
    { "kind": "statement", "title": "<conclusion>", "body": ["<line>"] },
    { "kind": "bullets", "title": "<conclusion>", "body": ["<point>", "<point>"] },
    { "kind": "metrics", "title": "<conclusion>", "metrics": [
        { "value": "<e.g. 34%>", "label": "<label>" } ] },
    { "kind": "two_column", "title": "<conclusion>", "columns": [
        { "heading": "<left>", "body": ["<point>"] },
        { "heading": "<right>", "body": ["<point>"] } ] },
    { "kind": "image_hero", "title": "<conclusion>",
      "image": { "path": "<job-relative>", "credit": "<credit>", "layout": "full" },
      "caption": "<short caption>" },
    { "kind": "closing", "title": "<the ask / takeaway>", "body": ["<next step>"] },
    { "kind": "sources", "title": "Sources and credits", "sources": [
        { "label": "<source name>", "url": "<URL or empty>" } ] }
  ]
}

BRIEF
<PASTE FREE-FORM BRIEF HERE>
```

Fill every `<...>` field or omit the optional key entirely; do not leave angle-bracket placeholders in the output. Choose only the slide kinds the narrative needs (always ending with `sources`), and derive the palette from the topic rather than defaulting to generic blues.

## 2. Canva query template (verbatim — for `GENERATE_DESIGN` only)

Use these headers verbatim, in this order; Canva generation quality depends on it.

```text
**Presentation Brief**
Title: <working title>
Topic / Scope: <1–2 lines>
Key Messages: <3–5 crisp takeaways>
Constraints & Assumptions: <timebox, brand, data limits, languages>
Style Guide: <tone, palette, typography, imagery style>

**Narrative Arc**
<one paragraph: Hook → Problem → Insight → Solution → Proof → Plan → CTA>

**Slide Plan**
Slide 1 — "<Exact Title>"
Goal: <one sentence>
Bullets (3–6): <short, parallel, specific>
Visuals: <named chart/diagram + variables + timeframe>
Data/Inputs: <concrete values or clearly labelled example values>
Speaker Notes: <2–4 sentences>
Asset Hint: <optional, e.g. "Asset #2: logo_dark.svg">
Transition: <one sentence into the next slide>
... repeat for each slide ...
```

Before calling `GENERATE_DESIGN`: unique titles ≤65 chars, 3–6 bullets per slide, concrete visuals, no placeholders, explicit transitions, headers in exact order. Set `design_type="presentation"` and `length="short"` unless more was requested.

## 3. Validation checklist

### Contract (pre-render — any failure aborts)
- [ ] Parses as one UTF-8 JSON object; `version == 1`.
- [ ] 5 ≤ `len(slides)` ≤ 10; last slide is `kind: "sources"` with a non-empty list.
- [ ] Every slide has a non-empty, declarative conclusion-style `title` (≥4 words, no trailing colon).
- [ ] Per slide `body` ≤ 3 items, each ≤ 90 chars; `notes` is plain text.
- [ ] Every `kind` is in the allowed set; no unknown kinds.
- [ ] Theme colours match `#RRGGBB`; ≤ 2 font families from the local allowlist.
- [ ] Image `path` is job-relative, exists or is an explicit placeholder, no `..`.
- [ ] Every used image has a `credit` and appears in the `sources` slide.
- [ ] No credentials, `TOKEN=...`, emails, personal data, or absolute home paths.

### Visual spec (`docs/design_contract.md`)
- [ ] 16:9 (13.333 × 7.5 in); one idea per slide; credits slide is last.
- [ ] Exactly 4 colours (C1, C2, DARK, WHITE, plus allowed tints); contrast ≥4.5:1.
- [ ] One accent bar per slide, same treatment; no gradients/glow/emoji/clip art.
- [ ] Objects snap to the 8×6 grid, uniform margins; ≤ two fonts; ≤ ~40 words/slide.
- [ ] No text block longer than 3 lines; footer line + slide number on all but title/credits.

### Canva call order
- [ ] `GENERATE_DESIGN` → `CREATE_DESIGN_FROM_CANDIDATE` → `GET_EXPORT_FORMATS` → `EXPORT_DESIGN`, in that order.
- [ ] `design_id` came from `CREATE_DESIGN_FROM_CANDIDATE` (starts with `D`, 11 chars), not a candidate/URL ID.
- [ ] Every call carried `user_intent` (≤255 chars); export format came from `GET_EXPORT_FORMATS`.
- [ ] Free plan used `export_quality: "regular"`; the signed URL was downloaded immediately.

### Images & credits (`docs/image_sourcing.md`)
- [ ] Source order Openverse → Wikimedia Commons → Pollinations.ai; licence verified from the API.
- [ ] Only `CC0`/`pdm`/`BY`/`BY-SA` unless the use case explicitly allows more (`NC`/`ND` skipped).
- [ ] Author HTML stripped; licence name, version, and URL present; no sensitive terms in any query/prompt.
- [ ] Credits slide and `credits.json` generated from the same metadata records.

### Delivery
- [ ] `grounded-citations verify` passed; QA report clean; slides inspected for overflow.
- [ ] Editable PPTX opens with the expected page count; PDF produced only if requested.
