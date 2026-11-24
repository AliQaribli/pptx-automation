# Image sourcing and credits

This document defines how the presentation agent finds free, reusable imagery and how it records
attribution. Goal: decks with **real visuals**, produced **free-first**, with **no sensitive
information ever published**, and with licence terms that stay valid when a deck is shared.

> Scope: this file covers sourcing only. It contains no credentials, account identifiers, tokens,
> or contact addresses. Keep it that way: never commit a key, user ID, or email into this doc,
> the deck, or the credits file.

## Principles

1. **Free-first, no key required.** Default to keyless public APIs. Paid/keyed tiers are an
   escalation path, not a prerequisite.
2. **Licence before looks.** Prefer `CC0` / public-domain, then `CC BY`, then `CC BY-SA`.
   Avoid `NC` (non-commercial) and `ND` (no-derivatives) for decks that will be distributed,
   edited, or used in a commercial context.
3. **Attribution travels with the image.** Every downloaded asset must be stored together with
   the metadata needed to credit it. If an image lacks a verifiable licence, skip it.
4. **Privacy by default.** URLs, prompts, filenames, and logs are treated as potentially public.
   No client names, confidential figures, personal data, contact addresses, account IDs, or
   secrets may enter a prompt, a query, or a published slide.
5. **Verify, don't assume.** Licences are read from the source API at fetch time and re-checked
   before the deck is finalized.

## Quick comparison

| Provider | Key needed | Cost | Best for | Reliability | Attribution burden |
|---|---|---|---|---|---|
| Openverse | No (anonymous) | Free | Broad CC / public-domain search across many sources | High — stable, documented, rate-limited | Low — API returns a ready-made `attribution` string |
| Wikimedia Commons | No | Free | Recognizable topics, diagrams, historical/encyclopedic images | Very high — Wikimedia infra, stable Action API | Medium — must parse `extmetadata` and strip HTML |
| Pollinations.ai | No (anonymous classic API) | Free tier, rate-limited | On-demand AI illustrations when no stock image fits | Low / best-effort — verify before relying | Low — no author, but terms are less clear; label as AI-generated |

Decision order: **Openverse → Wikimedia Commons → Pollinations.ai (optional last resort).**

---

## 1. Openverse (primary, keyless)

Aggregates openly licensed images from Flickr, Wikimedia, Smithsonian, and others. Search and
detail endpoints work with no key; anonymous access is enough for normal use.

### Endpoint examples

Search images (no `Authorization` header):

```http
GET https://api.openverse.org/v1/images/?q=mountain%20sunset&license=cc0,pdm,by,by-sa&license_type=commercial&page_size=20&mature=false
```

Fetch one record by its Openverse `id` (use this to re-confirm licence just before export):

```http
GET https://api.openverse.org/v1/images/{identifier}/
```

Notes on parameters:
- `license` is a comma-separated list of codes: `cc0`, `pdm`, `by`, `by-sa`, `by-nc`, `by-nc-sa`,
  `by-nd`, `by-nc-nd`, etc. For freely shareable decks prefer `cc0,pdm,by,by-sa`.
- `license_type=commercial` filters for commercially usable results; `attribution` and
  `no_rights_reserved` are also supported values.
- `page_size` — keep modest (20 or fewer) for anonymous calls; `page` paginates.
- `mature=false` helps avoid sensitive results; `filter_dead=true` drops dead links.
- `q` is URL-encoded free text. **Never put sensitive terms in `q`.**

### Licensing and attribution

- Every result carries `license`, `license_version`, `license_url`, and a plain-text
  `attribution` string that is already legally valid — use it verbatim in speaker notes or the
  appendix, and condense it for the on-slide credit.
- Respect the source platform's terms and always credit CC-licensed works. Openverse's Terms of
  Service prohibit scraping; use the API and stay within its limits.
- Treat `pdm` (public-domain mark) and `cc0` as "no attribution legally required", but still
  credit them in the deck's sources for good practice and traceability.

### Reliability

- High and stable; the public Openverse website itself runs on anonymous API calls.
- All endpoints are rate-limited. Exceeding the limit returns `429 Too Many Requests`.
- **Read the `X-RateLimit-*` response headers** for permitted/remaining usage; do not guess
  limits. Back off on `429` using the returned headers.
- Anonymous pagination is depth-limited (roughly the top 10,000 results per query) and page size
  is capped; this is intentional, not a bug. Do not attempt exhaustive/bulk harvesting.

### Metadata to capture

Store all of these per image at fetch time:

`id`, `title`, `url` (direct image URL actually downloaded), `thumbnail`, `foreign_landing_url`,
`creator`, `creator_url`, `license`, `license_version`, `license_url`, `attribution`, `provider`,
`source`, `detail_url`, `width`, `height`, `filetype`, plus `fetched_at`.

---

## 2. Wikimedia Commons (keyless, high coverage)

Use the MediaWiki **Action API**. Namespace `6` is the File/Image namespace. Always request
`extmetadata` when licence verification is needed.

### Endpoint examples

Search by description (namespace 6 restricts to files):

```http
GET https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch=mountain%20sunset&gsrnamespace=6&gsrlimit=20&prop=imageinfo&iiprop=url%7Cextmetadata%7Csize&iiurlwidth=1200&format=json&origin=*
```

Fetch metadata for known file titles:

```http
GET https://commons.wikimedia.org/w/api.php?action=query&titles=File%3AExample.jpg&prop=imageinfo&iiprop=url%7Cextmetadata%7Csize%7Cmime&iiurlwidth=1200&format=json&origin=*
```

- `gsrnamespace=6` — files only. `gsrlimit` — results per page; follow `continue.gsrcontinue` for
  more pages.
- `iiprop=url|extmetadata|size` (URL-encode the pipes as `%7C`) returns the original URL, a
  thumbnail URL of width `iiurlwidth`, dimensions, and licence metadata.
- `origin=*` enables CORS for browser clients. Send a descriptive `User-Agent` on server calls.
- Human file page: `https://commons.wikimedia.org/wiki/File:Example.jpg`
- CORS-friendly direct image: `https://commons.wikimedia.org/wiki/Special:FilePath/Example.jpg?width=1200`

### Licensing and attribution

Read these from `extmetadata` (`*.value`):
- `LicenseShortName` (e.g. `CC BY-SA 4.0`) and `LicenseUrl` — the licence to display and link.
- `Artist` — author name, often HTML (e.g. `<a href="...">Name</a>`). **Strip HTML tags** and
  decode entities before display; it may contain multiple authors.
- `Credit` — source statement. `Attribution` — a custom attribution that, if present, should
  replace `Artist` + `Credit`.
- `AttributionRequired` — indicates whether attribution is legally required. `UsageTerms` —
  human-readable terms. `ImageDescription`, `DateTimeOriginal` — optional context.
- If `Copyrighted` is true with no acceptable licence, or if a file is multi-licensed and the
  values look unreliable, **skip the image** or verify the file page manually.

### Reliability

- Very high uptime and a long-stable API. There is no published strict key requirement for reads.
- Metadata quality is the weak point: tags can be missing, inconsistent, or HTML-laden;
  multi-licensed files are explicitly unreliable. Always validate before use.
- Be polite: identify your client with a `User-Agent`, cache results, and avoid hammering the API.

### Metadata to capture

`title` (Commons file title), `url` (original or `thumburl` actually used), `descriptionurl`
(file page), `author` (HTML-stripped `Artist`/`Attribution`), `credit`, `license`
(`LicenseShortName`), `license_url` (`LicenseUrl`), `attribution_required`, `usage_terms`,
`width`, `height`, `mime`, `description`, plus `fetched_at`.

---

## 3. Pollinations.ai (optional, AI-generated — verify before relying on)

A keyless "classic" image endpoint that returns a JPEG from a plain GET. Use only when stock
imagery cannot supply what the deck needs. It is **best-effort, rate-limited, and its terms are
less clear than CC licences** — treat output as experimental.

### Endpoint example

```http
GET https://image.pollinations.ai/prompt/a%20mountain%20sunset%20at%20dawn?width=1024&height=1024&seed=42&model=flux&safe=true
```

- Path segment is the **URL-encoded prompt**. `seed` (default `42`) makes output reproducible:
  the same prompt + seed + URL returns the **same cached image**. Change `seed` for a variant.
- `model=flux` is the documented always-free image model. `safe=true` applies stricter content
  filtering. The classic free tier adds a small Pollinations logo to images.
- **No keys in URLs.** Do not append tokens or account identifiers to the request.

### Licensing and attribution / privacy

- There is no per-image CC-style licence grant and no human author. Credit as
  `AI-generated via Pollinations.ai (flux, seed 42)`, and link the endpoint or the service home.
- Use is subject to the provider's Terms of Service and Privacy Policy; **commercial-use and
  data-training terms are not clearly established**. Do not use AI-generated images for decks
  containing sensitive, confidential, or legally constrained material.
- **Critical privacy rule:** the prompt is embedded in a URL, and results are cached and
  accessible to anyone who has the URL. Therefore prompts must contain **only generic visual
  descriptions** — never a client name, project codename, confidential number, personal data,
  contact address, account ID, or secret. Store sanitized prompt text only; if a prompt might be
  sensitive, record just `AI-generated image` and omit the prompt from credits entirely.

### Reliability — verify before relying

- Free requests are anonymous and counted **per IP**: one image at a time, at least **45 seconds
  apart**. Exceeding the limit returns `402 Payment Required` with a `Retry-After` header; a
  `HEAD` request past the limit returns `429`.
- No uptime guarantee; limits, models, and behaviour can change without notice.
- **Preflight check before first real use:** issue a `HEAD`/GET to the endpoint with a harmless
  generic prompt, confirm an `image/*` response rather than `402`/`429`, and re-run this check
  after any long gap. If it fails, fall back to Openverse/Wikimedia.
- Respect `Retry-After`; implement backoff rather than retry loops.

### Metadata to capture

`url` (full generation URL used to fetch), `prompt` (sanitized/omitted if sensitive), `seed`,
`model`, `size`, `generated_at`/`fetched_at`, `content_type`, `credit_string`. No author or
licence URL exists; label as AI-generated.

---

## Common metadata record (per image)

Normalize every provider into one record so the credits slide and machine-readable file come
from a single source of truth:

```json
{
  "local_id": "img-01",
  "provider": "openverse",
  "title": "Short image label",
  "author": "Author or Creator (HTML stripped)",
  "author_url": "https://...",
  "license": "CC BY 2.0",
  "license_version": "2.0",
  "license_url": "https://creativecommons.org/licenses/by/2.0/",
  "attribution_required": true,
  "attribution_text": "verbatim ready-made attribution when provided",
  "source_url": "https://... direct image URL downloaded ...",
  "source_page_url": "https://... landing / file page ...",
  "fetched_at": "ISO-8601 timestamp"
}
```

For Pollinations, set `provider: "pollinations"`, `license: "AI-generated"`, add `seed`/`model`,
and store only a sanitized or omitted `prompt`. Keep the full record in a machine-readable
companion file (for example `credits.json` next to the deck) and **generate the slide from it** —
never hand-maintain credits separately.

Validation before export: each used image must have a non-empty `source_page_url`, `author`
(or `AI-generated`), `license`, and `license_url` (except AI/public-domain rows), and must not
contain any credential, account identifier, or contact address.

## Credits / sources slide format

A dedicated final slide titled **"Image credits"** (or "Sources"). Keep it compact but complete:
record **source URL, author, and licence** for every image used.

### Layout (preferred: compact table)

- Title: `Image credits` — 28–32 pt.
- One table, columns: `#` | `Image (short label)` | `Author` | `Licence` | `Source`.
  Body text 10–12 pt; 6–10 rows per slide. Split into "Image credits (1/2)", "(2/2)" if longer.
- `Licence`: short name + version (e.g. `CC BY-SA 4.0`), hyperlinked to `license_url`.
- `Source`: short readable label hyperlinked to `source_page_url` (e.g. `Wikimedia Commons`),
  not a raw long URL. Keep the **full URL** in speaker notes, alt text, or the companion file.
- `Author`: HTML-stripped name; if there are multiple authors, use the first plus `et al.`.
- Order rows by first appearance of each image in the deck; repeat an image only once.
- For AI images use `AI-generated · Pollinations.ai (flux, seed 42)` in the Author/Licence cells.

Slide-ready text template:

```text
IMAGE CREDITS
#  Image            Author              Licence            Source
1  Mountain ridge   A. Photographer     CC BY-SA 4.0       Wikimedia Commons
2  Forest canopy    Openverse user      CC0 1.0            Openverse
3  Abstract cover   AI-generated        Pollinations.ai    Pollinations (flux, seed 42)

Full source URLs and verbatim attribution text: see speaker notes / credits.json.
```

### Alternative (thumbnail grid)

For image-heavy decks, a two-column grid of small thumbnails with a 2-line caption under each:
`Short label — Author. Licence (link). Source (short link).` This costs more space; use the table
when there are more than ~6 images.

### Speaker notes / appendix

Put the verbatim `attribution_text` (Openverse) or stripped `Artist` + `Credit` (Commons) and the
full `source_page_url` and `license_url` in speaker notes or a backup appendix slide. This keeps
the visible slide readable while preserving legally complete attribution.

## Operational checklist

- [ ] Source chosen in order Openverse → Commons → Pollinations; licence verified from the API.
- [ ] Only `CC0`/`pdm`/`BY`/`BY-SA` used unless the deck's use case explicitly allows more.
- [ ] Direct image URL downloaded and cached locally; metadata record saved with it.
- [ ] Author HTML stripped; licence name, version, and URL present.
- [ ] No sensitive info in any query, prompt, filename, log, or slide; no credentials/IDs/emails.
- [ ] Rate limits respected (`X-RateLimit-*` for Openverse; `Retry-After` for Pollinations).
- [ ] Pollinations preflight passed and fallback available.
- [ ] Credits slide and `credits.json` generated from the same metadata records.
