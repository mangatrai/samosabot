# SamosaBot — Administrator Runbook

> Version 1.2.0 — covers first-time install, Heroku deployment, local dev, maintenance, database operations, and troubleshooting.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Create the Discord Bot Application](#2-create-the-discord-bot-application)
3. [Set Up the Database](#3-set-up-the-database)
4. [Configure Environment Variables (Doppler)](#4-configure-environment-variables-doppler)
5. [Local Setup and Running](#5-local-setup-and-running)
6. [Heroku Deployment](#6-heroku-deployment)
7. [Verifying the Bot is Operational](#7-verifying-the-bot-is-operational)
8. [Updating the Bot](#8-updating-the-bot)
9. [Database Operations](#9-database-operations)
10. [Troubleshooting](#10-troubleshooting)
11. [Environment Variable Reference](#11-environment-variable-reference)

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.13+ | Managed via `.python-version` file |
| `uv` (package manager) | Venv lives at `/Users/mrai/.uv/venvs/discord/` |
| Discord account + Developer access | [discord.com/developers](https://discord.com/developers) |
| OpenAI API account | For AI commands (ask, roast, fortune, etc.) |
| Database account | AstraDB **or** MongoDB Atlas (see §3) |
| Doppler account | For secrets management |
| Heroku account | For production hosting (Procfile already configured) |

---

## 2. Create the Discord Bot Application

### 2.1 Create the application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → name it (e.g. "SamosaBot")
3. Go to the **Bot** tab → click **Add Bot**
4. Under **Token** → click **Reset Token** → copy and save it (this becomes `DISCORD_BOT_TOKEN`)

### 2.2 Enable privileged intents

On the **Bot** tab, scroll to **Privileged Gateway Intents** and enable **all three**:

- **Server Members Intent** — required: `intents.members = True` in `bot.py`
- **Message Content Intent** — required: `intents.message_content = True` in `bot.py`
- **Presence Intent** — enable for completeness (not strictly required but avoids warnings)

> **If either privileged intent is missing the bot will start but behave incorrectly** — prefix commands may not fire and member-based features will fail silently.

### 2.3 Generate an invite URL

Go to **OAuth2 → URL Generator**. Select:

**Scopes:** `bot`, `applications.commands`

**Bot Permissions:**

| Permission | Why |
|---|---|
| Send Messages | Respond to commands |
| Send Messages in Threads | Confession discussion threads |
| Create Public Threads | Confession threads |
| Embed Links | Formatted responses |
| Add Reactions | Interactive elements |
| Read Message History | Track reactions and responses |
| Use Slash Commands | Modern command interface |
| Manage Channels | Verification: creates/deletes temp channels |
| Manage Roles | Verification: assigns guest/verified roles |
| View Channels | General visibility |

Copy the generated URL, open it in a browser, and invite the bot to your server.

> Slash commands are synced **globally** (not per-guild). After the first bot start, commands may take **up to 1 hour** to appear in existing guilds. They appear instantly in new guilds added after that.

---

## 3. Set Up the Database

The bot supports **AstraDB** (original) and **MongoDB Atlas** (recommended replacement — free tier is permanent). Pick one.

### Option A: MongoDB Atlas (recommended)

1. Sign up at [cloud.mongodb.com](https://cloud.mongodb.com)
2. Create a **Free (M0)** cluster — choose any region
3. Under **Database Access** → Add a database user with **read/write** permissions → note username/password
4. Under **Network Access** → Add IP `0.0.0.0/0` (allow all) for Heroku, or your specific IP for local
5. Under **Connect** → **Connect your application** → copy the connection string:
   ```
   mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
   ```
   This becomes `MONGODB_URI`
6. Set `MONGODB_DB_NAME=samosabot` (or any name you choose)
7. Set `DATABASE_PROVIDER=MONGODB` in Doppler

**Create collections and indexes** (one-time, after env vars are configured):
```bash
source /Users/mrai/.uv/venvs/discord/bin/activate
python tools/db_migrate.py
# Choose: 4 (Schema — create collections / indexes only)
# Choose: 2 (MongoDB Atlas)
# Choose: 1 (All collections)
```

### Option B: AstraDB

1. Sign up at [astra.datastax.com](https://astra.datastax.com)
2. Create a **Serverless (Vector)** database — choose any cloud/region
3. Under **Connect** → copy the **API Endpoint** (becomes `ASTRA_API_ENDPOINT`)
4. Generate an **Application Token** with `Database Administrator` role → copy token (becomes `ASTRA_API_TOKEN`)
5. Note the keyspace name (default: `default_keyspace`) → becomes `ASTRA_NAMESPACE`
6. Set `DATABASE_PROVIDER=ASTRA` in Doppler

**Create collections** (one-time):
```bash
source /Users/mrai/.uv/venvs/discord/bin/activate
cd utils
python astra_create_collection.py
```

---

## 4. Configure Environment Variables (Doppler)

All secrets are managed in **Doppler**. There is no `.env` file in the repo.

### 4.1 Install and configure Doppler CLI

```bash
brew install dopplerhq/cli/doppler   # macOS
doppler login
doppler setup   # Run from the project root — links the project to the Doppler config
```

### 4.2 Required variables

| Variable | Description | Example |
|---|---|---|
| `DISCORD_BOT_TOKEN` | Bot token from §2.1 | `MTI3...` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `EXTENSIONS` | Comma-separated cog paths to load | see §4.3 |
| `DATABASE_PROVIDER` | `ASTRA` or `MONGODB` | `MONGODB` |

**If DATABASE_PROVIDER=MONGODB:**

| Variable | Description |
|---|---|
| `MONGODB_URI` | Full connection string from Atlas |
| `MONGODB_DB_NAME` | Database name (default: `samosabot`) |

**If DATABASE_PROVIDER=ASTRA:**

| Variable | Description |
|---|---|
| `ASTRA_API_ENDPOINT` | AstraDB endpoint URL |
| `ASTRA_API_TOKEN` | AstraDB application token |
| `ASTRA_NAMESPACE` | Keyspace name (default: `default_keyspace`) |

### 4.3 EXTENSIONS value

The full set of cogs — paste this as the `EXTENSIONS` value:

```
cogs.utils,cogs.joke,cogs.facts,cogs.trivia,cogs.truth_dare,cogs.confession,cogs.ask,cogs.qotd,cogs.verification,cogs.fun,cogs.ship,cogs.roast,cogs.member_events
```

To disable a feature, remove its entry from this list. The bot will start without it.

### 4.4 Optional variables (set if needed)

| Variable | Default | Notes |
|---|---|---|
| `BOT_PREFIX` | `!` | Prefix for text commands |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose output |
| `ENABLE_FLASK` | `false` | Set `true` on Heroku (keep-alive server) |
| `RELOAD_SECRET` | — | Random secret string; enables `/reload` endpoint |
| `RELOAD_URL` | `http://localhost:8080` | Used by `utils/reload_extension.py` |
| `USER_DAILY_QUE_LIMIT` | `30` | Max `/ask` requests per user per day |
| `DELAY_BETWEEN_COMMANDS` | `5` | Seconds between commands (throttle) |
| `MAX_ALLOWED_PER_MINUTE` | `10` | Max commands/user/minute |
| `EXEMPT_COMMANDS` | `trivia` | Comma-separated commands exempt from throttle |
| `TEXT_GENERATION_MODEL` | `gpt-4o-mini` | Model for text generation |
| `IMAGE_GENERATION_MODEL` | `gpt-image-1-mini` | Model for image generation |
| `INTENT_CHECK_MODEL` | `gpt-4.1-nano` | Model for intent/safety checks |
| `VERIFICATION_MODEL` | `gpt-4.1-nano` | Model for verification questions |

---

## 5. Local Setup and Running

### 5.1 Install dependencies

```bash
cd /Users/mrai/datastax/codesample/discord
source /Users/mrai/.uv/venvs/discord/bin/activate
uv pip install -r requirements.txt
```

### 5.2 Run locally with Doppler

```bash
doppler run -- python bot.py
```

This injects all Doppler secrets as environment variables before starting the bot.

### 5.3 Run locally without Doppler (fallback)

Create a `.env` file in the project root (never commit it — it is gitignored):

```
DISCORD_BOT_TOKEN=...
OPENAI_API_KEY=...
DATABASE_PROVIDER=MONGODB
MONGODB_URI=...
MONGODB_DB_NAME=samosabot
EXTENSIONS=cogs.utils,cogs.joke,...
```

Then:

```bash
python bot.py
```

### 5.4 Expected startup log output

A healthy start looks like:

```
INFO  SamosaBot Version: 1.2.0
INFO  Logged in as SamosaBot#1234
INFO  [SUCCESS] Loaded extension: cogs.utils
INFO  [SUCCESS] Loaded extension: cogs.joke
... (one line per cog)
INFO  [SUCCESS] Synced 25 commands to Discord (registered: 25)
INFO  [SUCCESS] Registered guild metadata for MyServer (123456789)
```

**Red flags in startup logs:**

| Log message | What it means |
|---|---|
| `[ERROR] Failed to load extension 'cogs.X'` | Cog has a syntax error or missing import |
| `[ERROR] Failed to sync commands globally` | Discord API rate limit or token issue — will retry |
| `Missing required AstraDB/MongoDB configuration` | Env vars not set; check Doppler |
| `[WARNING] X commands registered but not synced` | Some cogs loaded after sync — harmless, retry next restart |

### 5.5 Stop the bot

`Ctrl+C` in the terminal. The bot disconnects cleanly.

---

## 6. Heroku Deployment

The `Procfile` is already configured: `web: python bot.py`

### 6.1 First-time Heroku deploy

```bash
heroku create your-app-name
git push heroku main
```

### 6.2 Set Doppler to sync to Heroku

The cleanest approach is to use Doppler's Heroku sync integration — secrets automatically push to Heroku config vars when you update Doppler.

In Doppler: **Integrations → Heroku → Connect** → select your app → enable sync.

Alternatively, set manually:

```bash
heroku config:set DISCORD_BOT_TOKEN=... OPENAI_API_KEY=... ENABLE_FLASK=true \
  DATABASE_PROVIDER=MONGODB MONGODB_URI=... MONGODB_DB_NAME=samosabot \
  EXTENSIONS=cogs.utils,cogs.joke,...
```

> Always set `ENABLE_FLASK=true` on Heroku. The Flask server on port 8080 is what Heroku's web dyno expects to receive its health check on.

### 6.3 Deploy an update

```bash
git push heroku main
```

Heroku restarts the dyno automatically. Expect ~30 seconds of downtime during restart.

### 6.4 View live logs

```bash
heroku logs --tail --app your-app-name
```

### 6.5 Restart the bot on Heroku

```bash
heroku restart --app your-app-name
```

### 6.6 Stop the bot on Heroku

Scale the dyno to zero (bot goes offline, no charges):

```bash
heroku ps:scale web=0 --app your-app-name
```

Bring it back:

```bash
heroku ps:scale web=1 --app your-app-name
```

---

## 7. Verifying the Bot is Operational

After start (allow 1–2 minutes for slash commands to propagate on first boot):

| Check | How |
|---|---|
| Bot is online | Green dot next to bot name in Discord member list |
| Slash commands work | Type `/` in any channel — bot commands should appear |
| Prefix commands work | Type `!ping` — bot should reply with latency |
| Database connected | Run `!listservers` — should show the server name (means DB read/write worked) |
| AI commands work | Run `/ask hello` — should reply (means OpenAI key is valid) |
| Slash commands not appearing | Wait up to 1 hour. If still missing after 1 hour, check startup logs for sync errors |

---

## 8. Updating the Bot

### 8.1 Code change → redeploy

```bash
git add <files>
git commit -m "describe change"
git push heroku main   # Heroku auto-restarts
```

For local, `Ctrl+C` and re-run `doppler run -- python bot.py`.

### 8.2 Add or remove a cog

1. Add/remove the cog file in `cogs/`
2. Update the `EXTENSIONS` value in Doppler (add or remove the `cogs.<name>` entry)
3. Restart the bot (redeploy on Heroku, or `Ctrl+C` + restart locally)

### 8.3 Hot-reload a cog (no restart)

Requires `ENABLE_FLASK=true` and `RELOAD_SECRET` to be set. The bot must be running.

Reload a single cog:

```bash
source /Users/mrai/.uv/venvs/discord/bin/activate
python utils/reload_extension.py cogs.confession
```

Reload all cogs at once:

```bash
python utils/reload_extension.py all
```

This reloads the code and re-syncs slash commands to Discord in the background. Useful for pushing confession or trivia fixes without taking the bot offline.

> Hot-reload only works on locally-running bots or if you expose the Flask endpoint. On Heroku you'd need to curl the endpoint directly: `curl "https://your-app.herokuapp.com/reload?cog=all&secret=YOUR_SECRET"`

### 8.4 Update dependencies

```bash
source /Users/mrai/.uv/venvs/discord/bin/activate
uv pip install -r requirements.txt --upgrade
# Test locally, then commit requirements.txt if versions changed
git push heroku main
```

### 8.5 Update bot version

Edit `configs/version.py`:

```python
__version__ = "1.3.0"
```

Commit and deploy.

---

## 9. Database Operations

### 9.1 Create collections on a fresh database

For MongoDB Atlas:
```bash
python tools/db_migrate.py
# Action: 4 (Schema only)
# Target: 2 (MongoDB Atlas)
# Collections: 1 (All)
```

For AstraDB:
```bash
cd utils && python astra_create_collection.py
```

### 9.2 Migrate between databases (e.g. AstraDB → MongoDB Atlas)

```bash
python tools/db_migrate.py
# Action: 3 (Migrate)
# Source: 1 (AstraDB)
# Target: 2 (MongoDB Atlas)
# Collections: 1 (All)
# Conflict resolution: 1 (Skip — safe default)
```

Exports are saved to `migration_export/<timestamp>/` before import begins. After verifying the bot works on the new database, update `DATABASE_PROVIDER` in Doppler.

### 9.3 Export (backup) data

```bash
python tools/db_migrate.py
# Action: 1 (Export)
# Source: whichever DB is live
# Collections: 1 (All)
```

JSON files land in `migration_export/<YYYY-MM-DD_HHMMSS>/`. Keep these as backups before major changes.

### 9.4 Restore from backup

```bash
python tools/db_migrate.py
# Action: 2 (Import)
# Target: your database
# Choose the export directory from the list
# Conflict resolution: 1 (Skip) to preserve existing data, or 2 (Overwrite) for full restore
```

### 9.5 Clean a collection (danger)

Wipes all documents from a single collection. Use only in dev/testing:

```bash
source /Users/mrai/.uv/venvs/discord/bin/activate
cd tests
python clean_collection_data.py <collection_name>
# e.g. python clean_collection_data.py trivia_leaderboard
```

---

## 10. Troubleshooting

### Bot starts but slash commands don't appear

- Wait up to **1 hour** — global slash command propagation takes time on Discord's side
- Check startup logs for `[ERROR] Failed to sync commands globally`
- Confirm the bot has `applications.commands` scope in its invite URL (§2.3)

### Bot starts but prefix commands (`!`) don't work

- Confirm **Message Content Intent** is enabled in the Discord Developer Portal (§2.2)
- Confirm `intents.message_content = True` is in `bot.py` (it is — don't remove it)

### `Missing required AstraDB/MongoDB configuration` in logs

- Env vars not loaded — run with `doppler run -- python bot.py`, not bare `python bot.py`
- Check Doppler has the correct variable names (case-sensitive)

### `[ERROR] Failed to load extension 'cogs.X'`

- Look at the full traceback in logs — usually a missing import or syntax error in the cog
- Fix the cog, restart the bot (or hot-reload: `python utils/reload_extension.py cogs.X`)

### AstraDB: `'NoneType' object has no attribute 'get'` on connect

- Do **not** call `database.info()` — it requires the Admin DevOps API and fails with regular tokens
- The migration tool (`tools/db_migrate.py`) uses `list_collection_names()` instead, which is correct

### Bot loses slash commands after restart on Heroku

- Normal behaviour — slash commands re-sync on every startup (takes up to 1 hour to propagate)
- If it persists beyond 1 hour: check `[ERROR] Failed to sync commands globally` in Heroku logs

### Hot-reload returns 403 Forbidden

- `RELOAD_SECRET` is not set, or the value sent doesn't match
- Check Doppler has `RELOAD_SECRET` set and `ENABLE_FLASK=true`

### Confession or verification features not working

- Confession: run `/confession-setup` in the server first (admin only) — settings are per-guild
- Verification: run `/setup_wizard` in the server first (admin only)
- Both features require per-guild configuration before they do anything

### Daily `/ask` limit hit unexpectedly

- Default is 30 requests per user per day (`USER_DAILY_QUE_LIMIT`)
- The counter resets at UTC midnight (based on `daily_counters` collection date field)
- Increase the limit in Doppler: `USER_DAILY_QUE_LIMIT=50`

---

## 11. Environment Variable Reference

### Required

| Variable | Description |
|---|---|
| `DISCORD_BOT_TOKEN` | Discord bot authentication token |
| `OPENAI_API_KEY` | OpenAI API key |
| `EXTENSIONS` | Comma-separated cog module paths |
| `DATABASE_PROVIDER` | `ASTRA` or `MONGODB` |

### Database — MongoDB Atlas

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URI` | — | Full `mongodb+srv://` connection string |
| `MONGODB_DB_NAME` | `samosabot` | Database name inside the cluster |

### Database — AstraDB

| Variable | Default | Description |
|---|---|---|
| `ASTRA_API_ENDPOINT` | — | AstraDB endpoint URL |
| `ASTRA_API_TOKEN` | — | AstraDB application token |
| `ASTRA_NAMESPACE` | `default_keyspace` | AstraDB keyspace |

### Bot Behaviour

| Variable | Default | Description |
|---|---|---|
| `BOT_PREFIX` | `!` | Prefix for text commands |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ENABLE_FLASK` | `false` | Start keep-alive Flask server (required on Heroku) |
| `RELOAD_SECRET` | — | Enables `/reload` endpoint (set to any random string) |
| `RELOAD_URL` | `http://localhost:8080` | URL used by `reload_extension.py` to reach the bot |

### Throttling

| Variable | Default | Description |
|---|---|---|
| `DELAY_BETWEEN_COMMANDS` | `5` | Min seconds between commands per user |
| `MAX_ALLOWED_PER_MINUTE` | `10` | Max commands per user per minute |
| `EXEMPT_COMMANDS` | `trivia` | Commands excluded from throttle (comma-separated) |

### AI Models

| Variable | Default | Description |
|---|---|---|
| `TEXT_GENERATION_MODEL` | `gpt-4o-mini` | Model for text commands |
| `IMAGE_GENERATION_MODEL` | `gpt-image-1-mini` | Model for image generation |
| `INTENT_CHECK_MODEL` | `gpt-4.1-nano` | Model for intent/safety pre-check |
| `VERIFICATION_MODEL` | `gpt-4.1-nano` | Model for verification question generation |

### Feature Limits

| Variable | Default | Description |
|---|---|---|
| `USER_DAILY_QUE_LIMIT` | `30` | Max `/ask` requests per user per day |
| `CONFESSION_AUTO_APPROVE_THRESHOLD` | `0.5` | VADER compound score above this → auto-approve |
| `CONFESSION_CONCERNING_THRESHOLD` | `-0.6` | VADER compound score below this → flag as concerning |

### Trivia

| Variable | Default |
|---|---|
| `TRIVIA_QUESTION_COUNT` | `10` |
| `TRIVIA_START_DELAY` | `30` |
| `TRIVIA_ANSWER_TIME` | `30` |
| `TRIVIA_QUESTION_BREAK_TIME` | `15` |
| `FAST_TRIVIA_ANSWER_TIME` | `15` |
| `FAST_TRIVIA_START_DELAY` | `10` |

---

*For end-user command reference see `README.md`. For codebase architecture see `CLAUDE.md`.*
