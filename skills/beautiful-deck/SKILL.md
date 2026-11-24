---
name: beautiful-deck
description: Turn a brief into a sourced, editable presentation.
version: 0.1.0
author: Ali Qaribli
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [presentations, canva, pptx, design-contract, decks]
    related_skills: [deck-design, powerpoint, grounded-citations, humanizer, pdf]
---

# Beautiful Deck Skill

Turn a free-form brief into a finished, editable deck. Normalize the brief into the JSON contract consumed by `presentation/cli.py`, try the Canva MCP path first, fall back to the local PPTX engine, and source free imagery with complete credits. This skill defines the pipeline; the binding visual rules live in `docs/design_contract.md`.

## When to Use

- A user sends a free-form presentation brief (e.g. over Telegram) and expects a deck.
- You must emit the contract JSON that `python -m presentation.cli <contract.json>` renders.
- Canva MCP may or may not be available; a working PPTX must be delivered either way.
- Don't use for: pure document editing, non-presentation graphics, or copy-only requests with no deck.

## Prerequisites

- Read `docs/design_contract.md` (visual spec), `docs/canva_mcp.md` (tool flow), `docs/pptx_fallback.md` §3 (contract schema), and `docs/image_sourcing.md` (assets + credits) before building.
- The Canva path needs the connected Canva MCP server; authentication is owned by the Hermes connector — never handle tokens in project code.
- The local path needs `python-pptx` and the `presentation/` package (`python -m presentation.cli`).
- No credentials, tokens, user IDs, emails, or personal data may enter any brief, contract, prompt, or file.

## Procedure

1. **Normalize the brief.** Extract topic, audience, slide count (default 7, clamp 5–10), key messages, data, and style. Write conclusion-style titles ("Revenue grew 34%", not "Q3 Revenue"). Run copy through `humanizer`; verify claims with `grounded-citations`. Completion: an outline where every title states a conclusion and every fact is sourced.

2. **Build the contract JSON.** See `references/brief_to_contract.md` for the exact prompt template and validation checklist. Emit one UTF-8 object with `version: 1`, `meta` (title, subtitle, language, optional theme), and `slides` (5–10). The last slide MUST be `kind: "sources"`. Allowed kinds: `title`, `statement`, `bullets`, `metrics`, `two_column`, `image_hero`, `closing`, `sources`. Keep `body` ≤ 3 items of ≤ 90 chars each; theme colours are `#RRGGBB`; use ≤ 2 fonts. Image `path` is job-relative only — no URLs, no `..`. Completion: the contract passes the reference checklist before any render call.

3. **Try Canva MCP — correct order, do not skip or reorder:**
   - a. `GENERATE_DESIGN(query, design_type="presentation", length, user_intent)` → keep the `job_id` and full candidate list; never parse a design ID from a preview URL.
   - b. Select a candidate (unattended → pick the FIRST candidate deterministically; NEVER call vision_analyze to compare previews), then `CREATE_DESIGN_FROM_CANDIDATE(job_id, candidate_id, user_intent)` → real `design_id` (starts with `D`, 11 chars).
   - c. `GET_EXPORT_FORMATS(design_id, user_intent)` → read supported `format.type` values and any `page_numbers`; never guess a format. Cache the result per design.
   - d. `EXPORT_DESIGN(design_id, format, user_intent)` → prefer `pptx` (`export_quality: "regular"` on the free plan), `pdf` secondary; download the signed URL immediately (valid 24 h).
   - Every call needs `user_intent` (≤255 chars). Space generation/create/export calls ≥3 s apart (≤18 calls/min). Completion: a validated, downloaded `.pptx` with the expected page count.

4. **Fall back to the local PPTX engine** when the connector is unavailable, after 2 consecutive generation failures, sustained 429, `license_required`, or a bad export. Run `terminal(command="python -m presentation.cli <contract.json>")`; it renders to `output/<job-id>/deck.pptx` and writes `qa_report.json`. Give the user a concise reason for the fallback. Completion: an editable deck is delivered on every path — never fail the turn silently.

5. **Source images with credits.** Use order Openverse → Wikimedia Commons → Pollinations.ai. Prefer `CC0`/`pdm`/`BY`/`BY-SA`; skip `NC`/`ND`. Record one metadata record per image (author, licence, licence_url, source_page_url, attribution) and generate both the final `sources` slide and `credits.json` from it. Never put sensitive terms in queries/prompts; never embed credentials. Completion: every used image is credited and the credits slide is last.

6. **Verify and deliver.** On the Telegram path, verify ONLY that the downloaded file exists and has a `.pptx`/`.pdf` extension. Do NOT render slides to images, do NOT call vision_analyze, and do NOT re-open the deck with python-pptx. Deliver by running `python C:\Users\Ali\presentation-agent\scripts\send_to_telegram.py --caption "Your deck is ready." "<absolute path>"`, then reply with one short sentence. Completion: the file is delivered directly to Telegram without relying on MEDIA interception.

## Pitfalls

- A candidate ID or preview-URL ID is NOT a `design_id` — always call `CREATE_DESIGN_FROM_CANDIDATE` first.
- Export URLs expire in 24 h — download immediately; on expiry re-run `EXPORT_DESIGN` for the same design, don't regenerate.
- `license_required` means premium elements, not a bad design — regenerate with a "free elements only" constraint or fall back; don't retry unchanged.
- The local contract rejects remote image URLs and `..` paths; keep image paths relative and assets local.
- Never guess an export format or invent data/credits. Omit a chart rather than fabricate figures.

## Verification

- [ ] Contract passes the checklist in `references/brief_to_contract.md` (version 1, 5–10 slides, sources last, no secrets/paths).
- [ ] Canva calls were made in order a→d with `user_intent` on each.
- [ ] Delivered file is an editable PPTX, opens cleanly, has the expected page count, credits slide last.
- [ ] No credentials, personal data, or machine-local paths in the brief, contract, or deck.
