# Beautiful Deck Agent — Telegram pipeline

This repo is the agent. When a message arrives from Telegram, follow these rules.

## When to build a deck

Build a presentation if the message asks for a presentation, deck, slides, PPT,
PPTX, or asks you to turn a topic into slides. A plain test message such as
`ping`, `hi`, or `test` is NOT a deck request — reply normally.

## Exact motion (no questions, no confirmation)

1. If the `beautiful-deck` skill is available, load it before acting.
2. Try Canva MCP first, in this order. Do not skip steps and do not guess IDs:
   - `connectors__canva_mcp__GENERATE_DESIGN`
   - `connectors__canva_mcp__CREATE_DESIGN_FROM_CANDIDATE`
   - `connectors__canva_mcp__GET_EXPORT_FORMATS`
   - `connectors__canva_mcp__EXPORT_DESIGN`
   Download the export to `C:\Users\Ali\presentation-agent\output\telegram\`
   as a `.pptx` or `.pdf`. Use only free-plan assets and standard quality.
3. If ANY Canva step fails or a tool is missing, fall back immediately — do not
   ask the user, do not explain the failure, just run:
   `python C:\Users\Ali\presentation-agent\scripts\deck_from_text.py "<the user's topic>"`
   It prints one line: `DECK:<absolute path>`.
4. Deliver the file immediately by running:
   `python C:\Users\Ali\presentation-agent\scripts\send_to_telegram.py --caption "Your deck is ready." "<absolute deck path>"`
   It prints `SENT:<path>`. This is the primary delivery path and works
   regardless of model behaviour. Only if that script fails, put
   `MEDIA:<absolute path>` as the VERY LAST line as a backup.
   Once the file exists on disk, stop calling tools and deliver — do not spend
   turns re-verifying it.
5. Keep the whole reply under 200 characters. Do not include bullet lists,
   caveats, credential talk, chat IDs, emails, or questions.

## Safety

Never print, echo, store, or mention bot tokens, API keys, emails, or chat IDs.
Never commit `.env`, `telegram_qr.png`, or files under `output/`.
