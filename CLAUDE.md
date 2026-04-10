# CLAUDE.md — SamosaBot

> Discord bot (v1.2.0) with games, AI features, anonymous confessions, and a modular cog architecture.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.13.7 |
| Bot framework | discord.py (`discord`) |
| Database | AstraDB via `astrapy` |
| AI | OpenAI API (GPT-4o, DALL-E-3, gpt-4.1-nano) |
| Sentiment analysis | VADER (`vaderSentiment`) + NLTK |
| Image processing | Pillow |
| Keep-alive server | Flask (optional) |
| Deployment | Heroku (via `Procfile: web: python bot.py`) |

---

## Project Structure

```
discord/
├── bot.py                      # Entry point: intents, events, throttle, command sync
├── requirements.txt
├── Procfile                    # web: python bot.py
├── .python-version             # 3.13.7
│
├── configs/
│   ├── setup_logger.py         # Logging config
│   ├── version.py              # __version__ = "1.2.0"
│   ├── prompts.py              # All OpenAI prompt strings
│   └── ship_messages.py        # 5-tier ship compatibility messages (20+ per tier)
│
├── utils/
│   ├── db_connection.py        # AstraDB client singleton
│   ├── astra_db_ops.py         # All DB operations (~1100 lines, the data layer)
│   ├── openai_utils.py         # OpenAI text/image generation wrappers
│   ├── error_handler.py        # Standardized error handling (8 categories, 5 severities)
│   ├── sentiment_analyzer.py   # VADER sentiment for confessions
│   ├── throttle.py             # Per-user rate limiting
│   ├── keep_alive.py           # Flask server (port 8080) + /reload dev endpoint
│   ├── interaction_helpers.py  # Discord interaction utilities
│   ├── reload_extension.py     # Dev tool: hot-reload cogs via /reload endpoint
│   └── astra_create_collection.py  # One-time script: create DB collections
│
├── cogs/                       # One file per feature domain
│   ├── utils.py                # ping, help, samosa botstatus, listservers
│   ├── joke.py                 # dad/insult/general/dark/spooky jokes
│   ├── facts.py                # general & animal facts
│   ├── trivia.py               # trivia game (orchestrates games/trivia_game.py)
│   ├── truth_dare.py           # Truth/Dare/WYR/NHIE/Paranoia
│   ├── confession.py           # Anonymous confessions with sentiment moderation
│   ├── ask.py                  # AI ask + image generation
│   ├── qotd.py                 # Question of the Day (scheduled)
│   ├── verification.py         # Server verification system
│   ├── fun.py                  # pickup lines, compliments, fortunes
│   ├── ship.py                 # Compatibility/ship with image compositing
│   ├── roast.py                # AI roast generation
│   └── member_events.py        # on_member_remove: cleanup verification
│
├── games/
│   └── trivia_game.py          # Full trivia game logic (~600 lines)
│
└── tests/
    ├── verification_test.py
    └── clean_collection_data.py
```

---

## How to Run

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables (copy and fill in values)
cp old.env-bk .env   # WARNING: old.env-bk has exposed secrets — rotate all tokens first

# Run the bot
python bot.py
```

Set `ENABLE_FLASK=true` to start the keep-alive web server on port 8080.

---

## Environment Variables

### Required

| Variable | Purpose |
|---|---|
| `DISCORD_BOT_TOKEN` | Bot authentication token |
| `OPENAI_API_KEY` | OpenAI API key |
| `ASTRA_API_ENDPOINT` | AstraDB endpoint URL |
| `ASTRA_API_TOKEN` | AstraDB authentication token |
| `EXTENSIONS` | Comma-separated list of cog module paths to load (e.g. `cogs.joke,cogs.trivia,...`) |

### Optional / Feature Flags

| Variable | Default | Purpose |
|---|---|---|
| `BOT_PREFIX` | `!` | Prefix for traditional commands |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ENABLE_FLASK` | `false` | Start keep-alive Flask server |
| `ASTRA_NAMESPACE` | `default_keyspace` | AstraDB keyspace |
| `TEXT_GENERATION_MODEL` | `gpt-4o-mini` | Default text model |
| `IMAGE_GENERATION_MODEL` | `gpt-image-1-mini` | Image generation model |
| `INTENT_CHECK_MODEL` | `gpt-4.1-nano` | Intent/safety detection model |
| `VERIFICATION_MODEL` | `gpt-4.1-nano` | Verification question model |
| `RELOAD_SECRET` | — | Secret for `/reload` Flask endpoint |

### Throttling

| Variable | Default | Purpose |
|---|---|---|
| `EXEMPT_COMMANDS` | `trivia` | Comma-separated commands exempt from throttle |
| `DELAY_BETWEEN_COMMANDS` | `5` | Minimum seconds between commands per user |
| `MAX_ALLOWED_PER_MINUTE` | `10` | Max commands per user per minute |

### Trivia

| Variable | Default |
|---|---|
| `TRIVIA_QUESTION_COUNT` | `10` |
| `TRIVIA_START_DELAY` | `30` |
| `TRIVIA_ANSWER_TIME` | `30` |
| `TRIVIA_QUESTION_BREAK_TIME` | `15` |
| `FAST_TRIVIA_ANSWER_TIME` | `15` |
| `FAST_TRIVIA_START_DELAY` | `10` |

### Ask Command

| Variable | Default |
|---|---|
| `USER_DAILY_QUE_LIMIT` | `30` |

### Confessions

| Variable | Default | Purpose |
|---|---|---|
| `CONFESSION_AUTO_APPROVE_THRESHOLD` | `0.5` | Compound score above this → auto-approve |
| `CONFESSION_CONCERNING_THRESHOLD` | `-0.6` | Compound score below this → flag as concerning |
| `CONFESSION_NEG_SENTENCE_THRESHOLD` | `-0.2` | Per-sentence negativity threshold |

### External API URLs (all have defaults)

`ICANHAZDADJOKE_URL`, `EVILINSULT_URL`, `RIZZAPI_URL`, `JOKEAPI_URL`,
`TRUTH_DARE_API_URL`, `USELESS_FACTS_API_URL`, `CAT_FACTS_API_URL`,
`DOG_FACTS_API_URL`, `QOTD_API_URL`

---

## AstraDB Collections

All DB operations live in `utils/astra_db_ops.py`. Collections are created by `utils/astra_create_collection.py`.

| Collection | Purpose |
|---|---|
| `registered_servers` | Guild metadata, confession settings, status |
| `user_requests` | All confessions and ask-command logs |
| `daily_counters` | Per-user daily request tracking |
| `trivia_leaderboard` | User trivia scores |
| `truth_dare_questions` | Community-submitted T/D questions |
| `qotd_channels` | Channels configured for QOTD scheduling |
| `bot_status_channels` | Channels for periodic bot status updates |
| `verification_attempts` | Verification event logs |
| `guild_verification_settings` | Per-guild verification config |
| `active_verifications` | In-progress user verification sessions |

---

## Commands

Both prefix (`!`) and slash (`/`) versions exist for most commands.

### Games
- `trivia start <category> [fast|slow]` — Start trivia (18 categories)
- `trivia stop` — Stop active trivia session
- `trivia leaderboard` — Top 10 scores
- `mystats` — Personal trivia stats (prefix only)
- `tod` — Truth or Dare (Truth/Dare/WYR/NHIE/Paranoia, PG/PG13/R)
- `tod-submit` — Submit a T/D question

### Entertainment
- `joke <category>` — dad/insult/general/dark/spooky
- `joke-submit` — Submit a joke
- `fact [animals]` — Random fact
- `fact-submit` — Submit a fact
- `pickup` — Pickup line
- `roast [@user]` — AI roast
- `compliment [@user]` — AI compliment
- `fortune` — AI fortune
- `ship <user1> [user2]` — Compatibility with image

### Community
- `confession <message>` — Submit anonymous confession
- `confession-setup` — Configure confessions (admin, slash only)
- `confession-view <id>` — View confession by ID (admin, slash only)
- `confession-history` — Paginated confession list (admin, slash only)

### AI & Questions
- `asksamosa <question>` / `ask <question>` — Ask AI or generate image
- `qotd` — Question of the Day
- `setqotdchannel <channel>` — Set QOTD channel (admin, prefix only)
- `startqotd` — Start QOTD schedule (admin, prefix only)

### Utility
- `ping` — Latency
- `help` — All commands
- `samosa botstatus [channel]` — Configure status update channel

### Verification (slash only)
- `/verification` — Configure verification
- `/verification_status` — Check status
- `/setup_wizard` — Guided setup

---

## Key Architecture Patterns

### Cog Loading
Extensions are loaded from the `EXTENSIONS` env var (comma-separated module paths). Loaded in `on_ready()` with retry logic. All slash commands are synced **globally** (not per-guild) — new commands can take up to 1 hour to propagate to existing guilds after restart.

### Dual Command Surface
Every feature implements both prefix commands (`commands.command`) and slash commands (`app_commands.command`) in the same cog class.

### Content Sourcing (Multi-Source Fallback)
Jokes, facts, and T/D questions pull from: External API (75%) → Community DB (20%) → AI generation (5%). Sources are tried in order; failures fall through to the next.

### Persistent Buttons
Interactive buttons (trivia answers, T/D options) have no timeout and are registered as persistent views on startup. Button IDs encode enough state to function after bot restarts.

### Throttling
Dual enforcement in `utils/throttle.py`: minimum gap between commands + max per minute. Applied to both prefix commands (via `@bot.check`) and slash commands (via `on_interaction`). Exempt commands skip throttle entirely.

### Error Handling
`utils/error_handler.py` defines 8 error categories and 5 severity levels. All cog errors route through `handle_error()`. User-facing messages are generic; detailed context is logged.

### Sentiment Analysis (Confessions)
`utils/sentiment_analyzer.py` uses VADER with sentence-level scoring aggregation. Output: `positive` / `negative` / `concerning` / `neutral`. Concerning confessions always go to admin review regardless of auto-approve settings.

### Background Tasks
- Bot status updates: 30-minute interval (in `cogs/utils.py`)
- QOTD posting: 24-hour interval (in `cogs/qotd.py`)

---

## Security Notes

- `old.env-bk` is a local-only backup of credentials (Discord token, OpenAI key, AstraDB token, reload secret). This repo is not pushed to GitHub, so this file stays local.
- **Environment variables are managed via [Doppler](https://www.doppler.com/)** — no `.env` file is committed or expected in the repo.
- The `/reload` Flask endpoint is protected by `RELOAD_SECRET` but should not be exposed publicly.
- Admin commands check for guild permissions before executing.
- AI requests go through an intent/safety check before processing.

---

## Database Migration: AstraDB → MongoDB Atlas

**Status: COMPLETE. Both migration tool and bot dual-provider support are implemented.**

AstraDB free tier is being discontinued. The plan is to migrate to **MongoDB Atlas M0 (free forever, 512MB)** while keeping the AstraDB code path intact via a `DATABASE_PROVIDER` env var.

### Why MongoDB Atlas

- M0 free tier is permanent, not a trial
- AstraDB's Document API is MongoDB-compatible — every operator used (`$set`, `$inc`, `$push`, `$exists`, `$ne`, upsert, sort, limit, skip) is native MongoDB
- `pymongo` Collection API is nearly identical to `astrapy`'s, so `astra_db_ops.py` requires minimal changes
- Eliminates AstraDB workarounds: `get_truth_dare_message_metadata` currently fetches all docs and filters in Python because AstraDB lacks `$elemMatch` support — pymongo supports it natively

### Bot Dual-Provider Architecture (implemented)

**Key files:**

| File | Role |
|---|---|
| `utils/db_connection.py` | Factory — reads `DATABASE_PROVIDER`, delegates to correct module |
| `utils/db_connection_astra.py` | AstraDB connection via `astrapy` |
| `utils/db_connection_mongodb.py` | MongoDB connection via `pymongo` + `MongoCollectionAdapter` + `MongoDatabaseAdapter` |
| `utils/astra_db_ops.py` | All DB operations — provider-agnostic, unchanged except debug logs |

**Adapter pattern:** `MongoCollectionAdapter` in `db_connection_mongodb.py` absorbs all API differences between astrapy and pymongo:
- `find(sort=dict, limit=N, skip=N)` kwargs → cursor chaining
- `return_document="after"` string → `ReturnDocument.AFTER` constant
- All other methods pass through unchanged (identical signatures)

### Collections

| Collection | Purpose | Key query fields |
|---|---|---|
| `registered_servers` | Guild metadata + confession settings | `guild_id` |
| `user_requests` | Ask command logs + confessions | `user_id`, `guild_id`, `request_type`, `confession_id` |
| `daily_counters` | Per-user daily request tracking | `user_id`, `date`, `guild_id` |
| `trivia_leaderboard` | User trivia scores | `user_id`, sort by `total_correct` |
| `truth_dare_questions` | Community T/D questions | `type`, `rating`, `approved`, `_id` |
| `qotd_channels` | QOTD channel config per guild | `guild_id` |
| `bot_status_channels` | Status update channel per guild | `guild_id` |
| `verification_attempts` | Verification audit log | `user_id`, `guild_id` |
| `guild_verification_settings` | Per-guild verification config | `guild_id` |
| `active_verifications` | In-progress verification sessions | `user_id`, `guild_id` |

### Migration Tool (`tools/db_migrate.py`)

Standalone interactive script — does NOT depend on the bot's runtime `db_connection.py`.

```bash
cd /path/to/discord
python tools/db_migrate.py
```

**Actions:**
1. **Export** — dumps collections to `migration_export/<YYYY-MM-DD_HHMMSS>/` as JSON files + `_meta.json`
2. **Import** — loads from a local export directory into a target DB; prompts for conflict resolution (skip/overwrite/abort)
3. **Migrate** — export + schema creation + import in one flow
4. **Schema** — creates collections/indexes on target without moving data

**Provider extensibility:** `DatabaseProvider` ABC in `tools/db_migrate.py`. Add a new provider by subclassing it and adding one entry to the `PROVIDERS` dict.

**`_id` handling:** Preserved across export/import. AstraDB UUIDs stay as strings. MongoDB ObjectIds are serialized as hex strings on export and reconstructed as `ObjectId` on MongoDB import.

**Exports location:** `migration_export/` at project root (git-ignored).

**Env vars read by the tool:**
- AstraDB: `ASTRA_API_ENDPOINT`, `ASTRA_API_TOKEN`, `ASTRA_NAMESPACE`
- MongoDB: `MONGODB_URI`, `MONGODB_DB_NAME` (default: `samosabot`)
- If not set via Doppler/env, the tool prompts interactively.

**Env vars required (add to Doppler):**
```
DATABASE_PROVIDER=ASTRA          # or MONGODB
MONGODB_URI=mongodb+srv://...    # required when DATABASE_PROVIDER=MONGODB
MONGODB_DB_NAME=samosabot        # optional, default: samosabot
```

**Switching providers:** Change `DATABASE_PROVIDER` in Doppler and restart the bot. AstraDB credentials can remain set — they are ignored when `DATABASE_PROVIDER=MONGODB`.

**Optional future cleanup:** `get_truth_dare_message_metadata` in `astra_db_ops.py` fetches all docs with `message_metadata` and filters in Python (AstraDB lacks `$elemMatch`). When running on MongoDB this can be rewritten to use `$elemMatch` for better performance. Not urgent.
