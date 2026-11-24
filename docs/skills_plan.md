# Skill stack for presentation-agent

Scope: decide which Hermes skills belong in the slide-production pipeline of this
free, private, MIT-licensed Telegram-driven presentation agent.

Decision rule, applied throughout: a skill earns a slot only if it measurably
improves **slide beauty** (visual design, layout, copy quality) or **slide
correctness** (verified structure, sourced claims, working export). Discovery,
meta-tooling, and general dev convenience do not qualify. Ceremony is not a
benefit.

Verified against `hermes skills list --enabled-only`: every skill in the
recommended stack below is already installed and enabled in this profile.
Nothing needs installing to start.

## Recommended stack

| Skill | Status | What it contributes | When in the pipeline |
|---|---|---|---|
| `deck-design` | installed (local) | The visual contract: dark-navy 16:9 slides, accent bars, highlight/side boxes, pricing tables, slide numbers, light-on-dark typography, explicit "not the plain 32KB default" rule, and an approval gate. This is the main beauty lever. | Load once at **design setup**, before any slide is built; keep its spec as the acceptance criteria for every generator (Canva MCP or PPTX fallback). Re-check at final review. |
| `powerpoint` | installed (builtin) | The offline fallback engine plus the correctness tooling: `pptx_create.py` / `pptx_edit.py` to build, `pptx_read.py --outline` to verify slide count/text/tables, `pptx_render.py` to rasterize for visual review. Directly implements README stage 4. | Invoke at **build + verify**, only when Canva MCP is unavailable or when an editable `.pptx` is requested. Never ship a deck without the outline check. |
| `grounded-citations` | installed (builtin) | Ledger-based `url → [n]` mapping, inline citations, rendered `Sources:` block and `verify` gate. Directly implements README stage 4's sources/credits slide and stops invented URLs or unsourced statistics reaching slides. | **After research/retrieval, before slide copy is written**: reset ledger, register sources as they arrive, cite while drafting, render the credits slide, run `verify` before delivery. |
| `humanizer` | installed (builtin) | Strips AI tells from on-slide text (the 34-pattern pass, plus a real-voice rewrite). Flabby, generic slide copy reads as bad design even on a perfect layout, so this is a beauty contribution. It is also the reason `unslop` is skipped. | **Copy pass**, after the brief is drafted and before layout: run over titles, bullets, and speaker notes. Skip for pure data/table slides. |
| `pdf` | installed (builtin) | Final-artifact verification and PDF export when explicitly requested (`pdf_read.py --meta`, `pdf_page_image.py` for review). Not a design tool. | **Delivery stage**, conditional on the user asking for a PDF or on reviewing an exported PDF. The primary slide-to-PDF path is still LibreOffice via `pptx_render.py`. |

### Important adaptation for `deck-design`

`deck-design` is a local skill authored for a different delivery workflow. Its
visual spec and layout patterns are worth adopting; its **delivery/approval
section is not**. It hard-codes a WhatsApp `hermes send` step and a personal
contact address, and it assumes a single fixed user taste.

- Fork the design spec into this repo as a project-owned design contract rather
  than depending on a personal local skill at runtime.
- Remove the WhatsApp channel step and all personal contact details; the
  approval gate becomes "send the preview back through the project's Telegram
  bridge and wait for confirmation".
- Treat the dark-navy palette as the default theme, not an immutable law: the
  agent should still accept an explicit theme from the brief.
- Do not copy any credentials, tokens, or personal addresses from that skill
  into project files.

### Pipeline view

1. **Brief in (Telegram)** — no skill; parse the request.
2. **Research** — `grounded-citations`: reset ledger, register sources.
3. **Copy** — `humanizer` on drafted text; `grounded-citations` verifies claims.
4. **Design** — `deck-design` supplies theme, layouts, and acceptance criteria.
5. **Build** — Canva MCP (a tool/MCP server, not a skill) when available;
   otherwise `powerpoint`.
6. **Verify** — `grounded-citations verify`, `pptx_read.py --outline`, then
   `pptx_render.py` + visual review. This is the correctness gate; no skill
   may bypass it.
7. **Deliver** — `pdf` only if a PDF is requested; send via Telegram and wait
   for approval.

Canva MCP cannot be installed with `hermes skills install`: it is an MCP
server, not a skill. Skills shape the design decisions and verification around
it; they do not replace it.

## Install / availability commands

```bash
# Confirm the whole recommended stack is enabled (no installs expected)
hermes skills list --enabled-only | grep -E 'deck-design|powerpoint|grounded-citations|humanizer|pdf'

# Confirm the PPTX dependency before enabling the fallback engine
python -c "import pptx; print(pptx.__version__)"
```

All five are present here: `deck-design` is a local skill in this profile;
`powerpoint`, `grounded-citations`, `humanizer`, and `pdf` ship as Hermes
builtins. Builtins are restored with the Hermes installation, not by a hub
identifier, so there is no install command to run for them. If the local
`deck-design` skill is lost, restore it from the profile's skills directory or
re-author it with `skill_manage` rather than inventing a hub install id.

## Skipped, with reasons

| Skill / candidate | Decision | Why |
|---|---|---|
| `unslop` (skills.sh community variants, e.g. `skills-sh/cursor/plugins/unslop`) | **Skip — do not install.** | Inspection shows the indexed `unslop` SKILL.md is an anti-AI-writing text editor ("Cut AI tells from any writing"), not a slide/Canva skill and not a UI-code design skill either. It is fully redundant with the installed `humanizer`, which is more thorough (34 patterns, voice calibration, worked rewrites). It is also community-tier with eight near-identical clones, so trust and maintenance are poor. Install command exists (`hermes skills install skills-sh/cursor/plugins/unslop -y`) but should not be run. If a genuine UI-code unslop variant is wanted later, it still would not touch PPTX/Canva slide output. |
| `find-skills` | Keep installed, **never invoke in the slide pipeline**. | It is a capability-discovery/meta skill for the operator: search registries, install, verify. Useful when extending the agent, but it contributes zero to slide beauty or correctness and its "install without asking" reflex is actively wrong for a private, allowlist-only bot. Developer-time only. |
| `hermes-agent` | Setup-time only, not in pipeline. | Relevant to README stages 1–2 (creating the private Telegram bot, profiles, channels, gateway). It does not affect deck output; invoke once during bootstrap and stop. |
| `architecture-diagram` | Optional, docs-time only. | Produces a dark-themed SVG/HTML diagram. Fits README stage 5's architecture diagram, but it is a documentation artifact, not a slide. Does not improve the presentation itself. |
| `baoyu-infographic` | Conditional; off by default. | The 21 layout × 21 style library could genuinely improve data-heavy slides, but it emits raster PNGs via `image_generate` (not editable) and requires an interactive `clarify` step, which breaks an unattended Telegram-driven flow. Enable only for an explicitly requested infographic slide, with a human in the loop. |
| `popular-web-designs`, `claude-design` | Skip for now. | HTML/CSS web-page design systems. They style browser pages, not PPTX or Canva slides. Reconsider only if the project pivots to HTML-based slide rendering, at which point their tokens could inform a theme. |
| `design-md` | Skip. | Produces a formal DESIGN.md token spec file. No consumer for that file in this project; pure ceremony. |
| `docx`, `xlsx`, `microsoft-office`, `google-workspace`, `notion`, `obsidian`, `pdf` form/OCR features | Skip as pipeline skills. | Office/document and note tooling unrelated to slide output. `pdf` is retained only for the narrow export/review role listed above. |
| `competitor-news-monitor`, `arxiv`, `youtube-content`, `video-consumption`, and other research skills | Skip as pipeline skills. | The pipeline needs source retrieval plus `grounded-citations`, not a zoo of retrieval front-ends. Add one only for a specific, repeated brief type that proves necessary. |
| `code-review`, `simplify-code`, `test-driven-development`, `systematic-debugging`, and other dev skills | Not part of this document's scope. | They improve the codebase, not the slides. Use them when developing the agent, never as a presentation stage. |

## Bottom line

Four skills carry the product: `deck-design` for beauty, `powerpoint` for the
editable fallback and verification, `grounded-citations` for sourced claims,
and `humanizer` for clean copy. `pdf` is a narrow delivery helper. `find-skills`
stays on the shelf, `unslop` is left uninstalled, and every other candidate is
either tooling for building the agent or design vocabulary for a medium this
project does not use.
