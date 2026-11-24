# Canva MCP Integration Specification

Scope: turn a free-form presentation brief received over Telegram into a delivered, editable file using the connected Canva MCP server at `https://api.canva.com/connect/v1/mcp`. This document defines the exact tool calls, candidate selection, error/fallback policy, rate-limit handling, and a pipeline sketch. No credentials are stored in or passed through this project — authentication is owned entirely by the Hermes connector.

## 1. Tool surface actually used

The three connector tools named in the project brief are `GENERATE_DESIGN`, `GET_EXPORT_FORMATS`, and `EXPORT_DESIGN`. A complete brief-to-file flow needs one more tool that this profile also exposes: `CREATE_DESIGN_FROM_CANDIDATE`. Without it there is no valid `design_id` to export, because generation returns only candidate IDs and preview URLs — and the tool docs explicitly warn that IDs in candidate URLs are **not** design IDs.

| Step | Tool (connector-prefixed name) | Required inputs | Returns |
|------|--------------------------------|-----------------|---------|
| 1 | `connectors__canva_mcp__GENERATE_DESIGN` | `query`, `design_type` | async generation job: `job_id`, candidate list `{candidate_id, preview_url, thumbnails}` |
| 2 | `connectors__canva_mcp__CREATE_DESIGN_FROM_CANDIDATE` | `job_id`, `candidate_id` | design summary containing real `design_id` (`^D[a-zA-Z0-9_-]+$`, 11 chars) |
| 3 | `connectors__canva_mcp__GET_EXPORT_FORMATS` | `design_id` | supported `format.type` values + optional 1-indexed `page_numbers` per format |
| 4 | `connectors__canva_mcp__EXPORT_DESIGN` | `design_id`, `format` | async export job with a download URL (valid 24h) |

Optional pre-step: `LIST_BRAND_KITS` → `brand_kit_id` for on-brand generation. Only call after the user confirms they want a brand kit; pass the returned ID as `brand_kit_id` on step 1.

Every call must include a short `user_intent` string (≤255 chars) describing what the agent is doing; it is mandatory for LLM clients.

## 2. Exact call sequence: brief → delivered file

1. **Normalize the brief.** Map the Telegram message into the `query` string (template below). Set `design_type: "presentation"`. Set `length: "short"` (1–5 slides) unless the user explicitly asked for more. Construct `user_intent` (e.g. `"Generate presentation candidates from user brief"`).
2. **Generate.** Call `GENERATE_DESIGN(query, design_type, length, [brand_kit_id], [asset_ids], user_intent)`. It is asynchronous: retain the returned `job_id` and the full candidate list. Do **not** treat preview URLs as designs and do **not** parse candidate IDs out of URLs.
3. **Select.** Show the candidates (preview + thumbnails) to the user and ask which one to use, then record the chosen `candidate_id`. In fully unattended mode, apply the deterministic strategy in §3.
4. **Materialize.** Call `CREATE_DESIGN_FROM_CANDIDATE(job_id, candidate_id, user_intent)`. Extract `design_id` from the response. This is the only ID valid for steps 5–6.
5. **Discover formats.** Call `GET_EXPORT_FORMATS(design_id, user_intent)`. Read the supported `format.type` values and any `page_numbers`. Never guess a format, even if the user named one.
6. **Export.** Call `EXPORT_DESIGN(design_id, format, user_intent)`. Use `format.type: "pptx"` for the editable deliverable (Canva Presentations support PPTX), with `"pdf"` as the secondary/shareable artifact. On the free plan set `export_quality: "regular"` (never `pro`, lossless PNG, or transparent background). Respect `page_numbers` if present (export all pages only when the field is omitted). For image fallbacks use `"png"`/`"jpg"` with `width`/`height` and `quality` for JPG.
7. **Deliver.** Download the file from the returned URL **immediately** (signed URL expires in 24 h), verify the file opens and has the expected page count, add the sources/credits slide if required by the brief policy, then send the document to Telegram and display the download URL to the user. Do not cache the URL for later reuse.

**Query template for presentations** (use the headers verbatim, in this order — Canva's generation quality depends on it):

```
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

Self-check before sending: unique titles ≤65 chars, 3–6 bullets per slide, concrete visuals, no `[TBD]`/`[insert]` placeholders (label unknowns as "example values"), explicit transitions, all headers in the exact order.

## 3. Candidate selection strategy

- **Preferred (human-in-the-loop):** present all candidates with thumbnails/URLs and let the user pick. Canva's own tool docs instruct agents to show candidates rather than auto-select; this is the default for the Telegram flow (one extra round-trip is acceptable).
- **Unattended fallback:** pick deterministically and record the reason:
  1. Drop candidates with missing/blank preview or thumbnails, or that duplicate another candidate.
  2. Prefer candidates whose visible slide count matches the requested slide count.
  3. Prefer candidates whose palette/typography match the brief's `Style Guide`.
  4. Tie-break on thumbnail aspect/orientation matching the target format, then on lowest candidate index (stable/reproducible).
  5. Re-generation instead of forcing a bad pick if every candidate fails 1–2.
- **Once selected:** the choice is binding for the rest of the run. Store `(job_id, candidate_id, design_id)` together so a later export failure can reuse the same design instead of re-generating.

## 4. Error handling and fallback triggers

| Condition | Detection | Action |
|-----------|-----------|--------|
| `Common queries will not be generated` | `GENERATE_DESIGN` error text | Ask the user for the missing specifics (audience, topic, slide count, data), enrich `query`, retry once. Do not silently re-issue the same query. |
| Extra generation latency | 15 slides ≈ 3× the time of 5 | Keep `length: "short"`; only increase when explicitly requested, and tell the user to expect a longer wait. |
| Candidate/preview IDs used as design IDs | export/format call fails validation (`design_id` must start with `D`, 11 chars) | Never pass a candidate ID or URL ID downstream; call `CREATE_DESIGN_FROM_CANDIDATE` first. |
| Unsupported format / wrong page | `GET_EXPORT_FORMATS` omits the format or limits `page_numbers` | Choose a reported-supported format only. PPTX unavailable → PDF → PNG/JPG; then local fallback. Never guess a format. |
| `license_required` on export | `EXPORT_DESIGN` error | Premium elements in the design, **not** a missing design. Regenerate with an explicit "use only free elements/assets; no premium content" constraint (reuse the same brief), or go straight to the local PPTX engine if the user will not accept a redesign. Do not retry the same design unchanged. |
| Auth/scope failure (401/403, `Missing scopes: brandkit:read`) | gateway error envelope | Reconnect the connector in Hermes to refresh the token/scope; do not attempt to handle tokens in project code. |
| Export download URL expired / bad link | HTTP 4xx on download, or >24 h since export | Re-run `EXPORT_DESIGN` for the same `design_id` (formats already known); do not re-generate. |
| Connector unavailable, 2 consecutive generation failures, sustained 429, or export job failure | tool errors / repeated `RateLimited` | Fall back to the local PPTX engine (`python-pptx`) using the normalized brief, add a sources/credits slide, and deliver. Log the trigger; never fail the Telegram turn silently. |
| File validation failure | unreadable file or page count ≠ requested | Retry export once with corrected `pages`/format; if still bad, local PPTX fallback. |

General rules: retry only transient/idempotent operations; never retry a call that failed due to a malformed query or unsupported format without changing its inputs. Surface a concise, user-facing explanation on every fallback (e.g. "Canva export was blocked by premium-element licensing — delivered an editable local PPTX instead"). Keep all error details out of user-facing text beyond the actionable next step.

## 5. Rate-limit handling

Per-tool Canva limits (requests/minute): `generate-design` **20**, `create-design-from-candidate` **20**, `export-design` **20**, `get-export-formats` **100**; brand-kit/other reads are 100. The gateway connection is also commonly budgeted at ~20 req/min overall — treat that as the effective ceiling for API calls in one window.

- **Budget:** at most ~18 calls/min to the 20/min tools; space generation/creation/export calls ≥3 s apart. Do not issue parallel `GENERATE_DESIGN` calls.
- **Minimize calls:** one generation job per revision, one `GET_EXPORT_FORMATS` per design (cache result for the run), one export per requested format.
- **429 response:** honor `Retry-After`. Hermes' connector gateway already auto-retries a 429 once when the server names a short wait (≤10 s) and also retries 502/503/504 once under the same idempotency key; longer waits are surfaced to the agent as a `RateLimited` error with `retry_after` seconds. On that error: wait the stated interval (plus small jitter), retry the identical call once, then queue the job for the next window. Do not hammer the tool in a tight loop.
- **Backoff:** two consecutive 429s → exponential backoff (e.g. 5 s, 10 s, 20 s, capped); ≥3 consecutive 429s → stop and trigger the local-PPTX fallback.
- **Free-plan constraints:** standard/regular quality only; do not request `export_quality: "pro"`, `lossless: true`, or `transparent_background: true`.

## 6. Pseudocode pipeline

```python
def brief_to_file(telegram_message):
    brief = normalize_brief(telegram_message)          # structured query text
    if user_wants_brand:
        kits = list_brand_kits()
        brief.brand_kit_id = ask_user_to_choose(kits)   # optional

    rate_limiter.gate("generate-design")               # >=3s spacing, <=18/min
    job = generate_design(query=brief.query,
                          design_type="presentation",
                          length=brief.length,          # "short" by default
                          brand_kit_id=brief.brand_kit_id,
                          user_intent="Generate presentation candidates from brief")

    candidates = await job                              # job_id + [{candidate_id, preview, thumbs}]
    chosen = user_pick(candidates) if interactive else select_unattended(candidates, brief)
    if chosen is None:
        return local_pptx_fallback(brief, reason="no viable candidate")

    rate_limiter.gate("create-design-from-candidate")
    design = create_design_from_candidate(job.job_id, chosen.candidate_id)
    design_id = design.design_id                        # starts with 'D'

    formats = get_export_formats(design_id)             # cache for the run
    if "pptx" not in formats.supported:
        fmt = pick_from(["pdf", "png", "jpg"], formats) or local_pptx_fallback(...)
    else:
        fmt = {"type": "pptx", "export_quality": "regular"}

    try:
        rate_limiter.gate("export-design")
        export = export_design(design_id, fmt, user_intent="Export chosen presentation")
        file = download_now(export.download_url)        # valid 24h — download immediately
        assert opens(file) and page_count(file) == expected
    except LicenseRequired:
        return regenerate_free_or_local_pptx(brief, design_id)
    except UnsupportedFormat:
        return try_next_supported_format_or_local_pptx(design_id, formats)
    except RateLimited as e:
        wait(e.retry_after + jitter); retry_once_or_queue()
    except ExportFailure:
        return local_pptx_fallback(brief, reason="export failed")

    file = add_sources_and_credits_slide(file, brief.sources)
    send_to_telegram(file)                              # also show the download URL to the user
    return file
```

## 7. Non-negotiable rules

- Never put API keys, bot tokens, user IDs, emails, or any credentials in a brief, query, log, or this repository; the connector owns authentication.
- Never guess an export format or reuse a candidate/URL ID as a `design_id`.
- Always download export artifacts immediately and display the download URL to the user.
- Deliver a working file on every path: Canva export or the local PPTX fallback.
