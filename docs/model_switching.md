# Switching AI models from Telegram

This agent is driven by Hermes. Model changes are made with Hermes slash
commands sent to the bot in a Telegram DM — **no code edits are needed to
switch models day to day**. A one-time setup step adds the model providers and
defines the three tier aliases (`free`, `mid`, `frontier`); after that you
change tiers entirely from Telegram.

All commands below are verified against the installed Hermes source and docs
(`hermes_cli/model_switch.py`, `gateway/slash_commands_model.py`,
`plugins/platforms/telegram/adapter.py`, and the "Configuring Models" guide).

## Exact commands (from a Telegram DM)

| Command | Effect |
|---|---|
| `/model` (no arguments) | Opens the **inline picker** (tappable buttons) listing authenticated providers and their curated models. Telegrams renders it as an inline keyboard; platforms without picker support get a numbered text list instead. |
| `/model free` | Switch this session to the `free` alias. |
| `/model mid` | Switch this session to the `mid` alias. |
| `/model frontier` | Switch this session to the `frontier` alias. |
| `/model free --global` | Same switch, but also persist it as the profile default in `config.yaml`. |
| `/model <alias> --session` | Explicitly session-only (the default for a normal `/model <alias>` on an already-configured profile). |
| `/model <alias> --once` | Switch for the **next turn only**, then automatically restore the previous model. |
| `/model reset` | Clear this session's override and return to the configured default. |
| `/status` | Show the session's current model, provider, and token/context info. |

Notes on flags from Telegram:

- `--global`, `--session`, `--once`, `--provider`, `--reasoning`, `--refresh`
  are all accepted from gateway chats. Telegram sometimes auto-converts `--`
  to an en/em dash; Hermes normalizes that back to `--` before parsing, so
  the flags work as written.
- `/model reset` takes no flags; combining it with a flag returns an error.
- `/model --once` requires a target (e.g. `/model frontier --once`).
- `--once` and `--global` cannot be combined.
- Built-in aliases also work (e.g. `/model sonnet`, `/model opus`,
  `/model gemini`, `/model deepseek`), plus full names such as
  `/model anthropic/claude-opus-4.7` and OpenRouter variants ending in `:free`.

## One-time setup commands (run locally, not from Telegram)

```bash
hermes model            # interactive provider + model picker: authenticate a
                        # provider once and choose its default model. Writes
                        # model.provider / model.default to config.yaml.
hermes config get model --json   # verify the resolved model config
hermes status                     # verify what Hermes will actually use
hermes gateway restart            # optional: force all sessions to pick up config changes
```

`hermes model` is the canonical way to add a provider: it walks you through
authentication (OAuth opens a browser; API-key providers prompt for the key)
and a curated model pick, then writes the choice to `~/.hermes/config.yaml`.
Credentials belong in the profile's environment / config, never in chat.

## How the `free` / `mid` / `frontier` aliases are configured

These three names are **user-defined aliases**, not built-ins. Hermes' built-in
short aliases are `sonnet`, `opus`, `haiku`, `claude`, `gpt5`, `gpt`, `codex`,
`o3`, `o4`, `gemini`, `deepseek`, `grok`, `llama`, `qwen`, `minimax`,
`nemotron`, `kimi`, `glm`, `step`, `mimo`, `trinity`. User aliases are checked
**before** the built-in table and can shadow those names.

Define the three tiers once in the profile's `config.yaml`
(`~/.hermes/config.yaml`, or the active profile's config file):

```yaml
# Canonical form — full control over provider and model.
model_aliases:
  free:
    model: nvidia/nemotron-3-ultra-550b-a55b:free
    provider: openrouter
  mid:
    model: google/gemini-2.5-flash
    provider: openrouter
  frontier:
    model: anthropic/claude-opus-4.7
    provider: openrouter
```

The model IDs above are illustrative — pick real ones from the `/model`
picker for your authenticated providers. `:free` on an OpenRouter SKU marks a
no-cost model.

Equivalent short string form (`provider/model`), convenient from the shell:

```bash
hermes config set model.aliases.free openrouter/nvidia/nemotron-3-ultra-550b-a55b:free
hermes config set model.aliases.mid openrouter/google/gemini-2.5-flash
hermes config set model.aliases.frontier openrouter/anthropic/claude-opus-4.7
```

Resolution rules worth knowing:

- Both forms feed the same loader; entries in `model_aliases:` win over
  `model.aliases:` entries with the same name.
- The short string form cannot carry a custom `base_url` or a separate
  credential. If an alias points at its own endpoint, use the canonical form
  and add `base_url:` with either `api_key:` (a literal or a `"${VAR}"`
  reference) or `key_env:` (the name of an environment variable); `api_key`
  wins if both are set.
- If an alias sets no endpoint/credential, the key is resolved from the
  provider/host already configured for that alias — it is **never** inherited
  from whichever provider happened to be active before the switch, so a tier
  switch cannot leak one vendor's secret to another vendor's host.
- Aliases are resolved by `hermes_cli/model_switch.py` and work identically in
  the CLI, TUI, gateway platforms, and `hermes chat --model <alias>`.

## What works from Telegram DM

- `/model` with no args → interactive inline picker (provider buttons → model
  buttons, paginated, with Back/Cancel). The picker's selection is committed to
  that session.
- Typed tier switches (`/model free|mid|frontier`) and all the flags listed
  above, subject to the allowlist/authorization rules of the bot.
- Picker buttons are authoritative to the person who opened them (or a chat
  admin where configured): someone else's tap cannot answer your `/model`
  card. The bot itself still only serves users admitted by its allowlist.
- Multi-step provider authentication (OAuth browser flow, API-key entry) does
  **not** happen in Telegram — do `hermes model` locally first. Once a provider
  is authenticated, tier switching from Telegram needs no further setup.
- In a private DM there is no group to administer; only the admitted user can
  issue the commands.

## Caveats

- **Plain `/model <alias>` is session-scoped** on a configured profile: the
  tier reverts to the default in a new session. Use `--global` to make a tier
  stick, or keep the configured default on `free` (recommended below) and use
  `/model mid`/`frontier` as one-session escalations.
- **Each target provider must already be authenticated.** `switch_model` fails
  with "no API key or login was found" if the alias points at a provider you
  never set up. Add it with `hermes model` first.
- **Mid-session switches reset the prompt cache.** The next message re-reads
  the whole conversation at full input-token price. On a long session that
  can cost more than the tier difference. Prefer switching early in a chat,
  or use `--once` for a single expensive question.
- **Large-context confirmation:** when the live session already holds more
  than ~100,000 tokens, a typed mid-session switch asks for confirmation
  before applying (tune/disable with `model.switch_context_confirm_tokens: 0`).
- **Config changes affect new sessions only.** An already-running session
  keeps its model until you issue `/model` inside it; `hermes gateway restart`
  forces all sessions to reload the config.
- **Cost:** `mid` and `frontier` can incur real spend; `:free` SKUs are the
  only guaranteed no-cost route. A free-by-default setup still lets a single
  `/model frontier --once` question bill your account — use it deliberately.
- **Aggregator resolution:** on an aggregator like OpenRouter, bare model
  names resolve *within* the aggregator first. A typed name may therefore
  stay on your OpenRouter auth instead of hopping to a native provider.
  User-defined aliases avoid ambiguity by pinning the provider explicitly.
- **Picker fallback:** if a platform adapter has no picker support, `/model`
  with no args prints a text list instead of buttons. Telegram supports the
  inline picker.

## Recommended setup that stays free by default

Goal: normal operation costs nothing; mid/frontier are opt-in per session from
Telegram, with no code or config edits after setup.

1. **Add one provider once.** Run `hermes model` locally and pick a provider
   that offers free models (e.g. OpenRouter and authenticate it; or the Nous
   free tier). Choose a `:free` model as the default. This write is the only
   setup that touches config; all later switching is from Telegram.
2. **Define the three tier aliases** in `config.yaml` (or with
   `hermes config set`, shown above), all on the same already-authenticated
   provider so no extra credentials are needed:
   - `free` → a `:free` SKU (the default).
   - `mid` → a cheap but capable model (e.g. a flash/mini tier).
   - `frontier` → a top-tier model (e.g. an Opus-class model).
3. **Keep the configured default on `free`.** Then a fresh Telegram DM always
   starts free. Verify with `hermes config get model --json`.
4. **Switch from Telegram as needed:**
   - `/model mid` — stronger model for this chat only.
   - `/model frontier --once` — one hard question on a frontier model, then
     auto-revert to free.
   - `/model free` or `/model reset` — back to the free default.
   - `/model` — open the picker to browse/choose any available model.
5. **Optionally restrict persistence:** leave `model.persist_switch_by_default`
   unset/false so plain switches do not silently become the new default; only
   an explicit `--global` changes what future sessions use.

This keeps the project free by default while giving you a one-line Telegram
command to escalate to mid or frontier and back.
