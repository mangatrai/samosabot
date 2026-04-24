# 🤖 Discord Bot - User Guide

A feature-rich Discord bot that brings **Trivia Games, Truth or Dare, Anonymous Confessions, Random Facts, AI-generated Jokes, Pickup Lines, Roasts, and more** to your server!

---

## 🚀 Features

- 🏆 **Clan Events** – Point-based clan competitions with leaderboards, activity scoring, and daily recaps
- 🎉 **Trivia Game** – Play interactive trivia with automatic score tracking and leaderboards
- 🎯 **Truth or Dare** – Interactive party game with user submissions and feedback
- 💬 **Anonymous Confessions** – Submit confessions with sentiment analysis; admins can require approval, auto-approve positive posts, and review with First/Previous/Next/Last pagination
- 📚 **Random Facts** – Get interesting facts about animals and general topics
- 🤣 **AI-Powered Jokes** – Multiple joke categories including dad jokes, dark humor, and more
- 💘 **Pickup Lines** – Generate flirty and witty pickup lines
- 🔥 **Roast Machine** – Generate playful AI-powered roasts
- 🔮 **AI Fortune Teller** – Receive fun AI-generated fortunes
- 📢 **Question of the Day** – Daily thought-provoking questions
- 🚢 **Ship** – See compatibility between two users

---

## 🎮 Commands

### 🏆 Clan Events

A point-based clan competition system. Admins define clans (Discord roles), create timed events with configurable activities, and mods award points to members. All mod commands are ephemeral (visible only to the mod).

#### Setup (Manage Server only)

| Command | Description |
|---------|-------------|
| `/events setup` | Configure clan roles, mod roles, channels, and auto-post setting |
| `/events settings` | View current configuration |

#### Event Lifecycle (mod only)

| Command | Description |
|---------|-------------|
| `/event create` | Create a new event — multi-step: basic info → select activities → set point values |
| `/event start <event>` | Set event to active and optionally post an announcement |
| `/event stop <event>` | End an event and optionally post final leaderboard |
| `/event list` | List all events with status and dates |

#### Scoring (mod only)

| Command | Description |
|---------|-------------|
| `/event award @member <event> <activity>` | Award fixed points for a completed activity; accumulates on repeated awards |
| `/event adjust @member <event> <points> <reason>` | Add or subtract points with a mandatory reason (stored in audit log) |

#### Leaderboard (everyone)

| Command | Description |
|---------|-------------|
| `/event leaderboard [member] [event]` | View scores and clan rankings — all-time or per-event |

**How it works:**
- Clans are Discord roles configured in `/events setup`
- Each member belongs to the first matching clan role
- Events have curated activities (QOTD, Picture of the Week, Clue Game, Bump Server, Invite a Friend) plus custom activities you add
- Point values are fixed per activity at event creation time
- Adjustments are stored separately and factored in at query time (full audit trail)
- If **Auto-Post** is enabled: start/stop announcements and a daily clan recap post automatically to the announcement channel

---

### 🎉 Trivia Game
| Command | Description |
|---------|-------------|
| `/trivia start <category>` | Start a trivia game |
| `/trivia stop` | Stop current trivia game |
| `/trivia leaderboard` | View top players |
| `!trivia start <category>` | Start trivia (prefix command) |
| `!trivia stop` | Stop trivia (prefix command) |
| `!mystats` | View your trivia stats |

**Categories:** History, Science, Geography, Sports, Movies, Animals, Music, Video Games, Technology, Literature, Mythology, Food & Drink, Celebrities, Riddles, Space, Cars, Marvel & DC, Holidays

**Speed Options:** Normal (default) or Fast-paced

---

### 🎯 Truth or Dare
| Command | Description |
|---------|-------------|
| `/tod` | Start a Truth or Dare game |
| `/tod-submit` | Submit your own questions |

**Game Types:**
- **Truth** – Answer personal questions
- **Dare** – Complete fun challenges  
- **Would You Rather** – Make tough choices
- **Never Have I Ever** – Share experiences
- **Paranoia** – Spooky questions

**Rating Options:** Family-friendly (PG13) or Adult Only (R)

---

### 💬 Anonymous Confessions

Users submit confessions via slash command only (for anonymity). Every confession is analyzed for sentiment (positive, negative, neutral, concerning). Admins can require approval, enable auto-approval for positive confessions, and review queued confessions with approve/reject buttons. Every posted confession gets a discussion thread.

| Command | Description |
|---------|-------------|
| `/confession <message>` | Submit an anonymous confession (10–2000 characters) |
| `/confession-setup` | Configure confession settings **(admin only)** |
| `/confession-view <id>` | View a confession by ID **(admin only)** |
| `/confession-history` | List confession history with First/Previous/Next/Last pagination **(admin only)** |

**Setup (admin):** Use `/confession-setup` with action **Enable** to turn on confessions and set the confession channel. If you want review before posting, set **approval required** and the **admin channel**; you can optionally enable **auto-approve** so positive confessions post without review.

**Workflow:**
- **No approval required:** Confession is posted to the confession channel and a thread is created; you get an ephemeral confirmation.
- **Approval required, auto-approve on:** Positive confessions are posted and a thread is created; others go to the admin channel for review.
- **Approval required, auto-approve off:** All confessions go to the admin channel; admins use ✅ Approve / ❌ Reject. Approved confessions are posted and get a thread; you are notified by DM when your confession is approved or rejected.

**Confession history:** Admins use `/confession-history` to see a paginated table (ID, Status, Submitted by, Sentiment, Preview, Submitted) and use **First**, **Previous**, **Next**, **Last** buttons to move between pages.

---

### 📚 Random Facts
| Command | Description |
|---------|-------------|
| `/fact` | Get a random general fact |
| `/fact animals` | Get a random animal fact |
| `/fact-submit` | Submit your own fact |
| `!fact` | Prefix command version |

**Sources:** Real APIs + AI-generated facts as backup

---

### 🤣 Jokes
| Command | Description |
|---------|-------------|
| `/joke dad` | Get a dad joke |
| `/joke insult` | Get a witty insult joke |
| `/joke general` | Get a general joke |
| `/joke dark` | Get a dark humor joke |
| `/joke spooky` | Get a spooky joke |
| `/joke-submit` | Submit your own dad joke |
| `!joke <category>` | Prefix command version |

---

### 💘 Pickup Lines
| Command | Description |
|---------|-------------|
| `/pickup` | Get a fun pickup line |
| `!pickup` | Prefix command version |

---

### 🔥 Roast Machine
| Command | Description |
|---------|-------------|
| `/roast @user` | Generate a playful roast |
| `!roast @user` | Prefix command version |

---

### 🔮 Fortune Teller
| Command | Description |
|---------|-------------|
| `!fortune` | Get an AI-generated fortune |

---

### 💝 Compliments
| Command | Description |
|---------|-------------|
| `!compliment @user` | Generate a nice compliment for a user |

---

### 🚢 Ship
| Command | Description |
|---------|-------------|
| `/ship <user1> <user2>` | See compatibility percentage between two users |
| `!ship <user1> <user2>` | Ship (prefix command) |

---

### 📢 Question of the Day
| Command | Description |
|---------|-------------|
| `/qotd` | Get a random thought-provoking question |
| `!qotd` | Prefix command version |
| `!setqotdchannel <channel>` | Set the QOTD channel (admin) |
| `!startqotd` | Start the daily QOTD schedule (admin) |

---

### 🔧 Utility Commands
| Command | Description |
|---------|-------------|
| `/help` | List all commands and categories |
| `!help` | Help (prefix command) |
| `!ping` | Check bot response time |
| `/ask <question>` | Ask the AI anything or generate images |
| `!asksamosa <question>` | Ask the AI (prefix command) |
| `/verification` | Configure server verification |
| `/verification_status` | Check verification settings |
| `/setup_wizard` | Start verification setup wizard |

---

### ⚙️ Admin Commands
| Command | Description |
|---------|-------------|
| `/samosa botstatus <channel>` | Set bot status channel |
| `!samosa botstatus <channel>` | Set bot status (prefix) |
| `!listservers` | List all registered servers |

---

## 🎯 How to Use

### Getting Started
1. **Invite the bot** to your server with proper permissions
2. **Use slash commands** (recommended) - type `/` and select the bot
3. **Use prefix commands** - type `!` followed by the command

### Truth or Dare Game Flow
1. Use `/tod` to start a game
2. Click **Truth**, **Dare**, **Random**, or other game type buttons
3. Answer the question or complete the challenge
4. Click buttons to get new questions (buttons work even after bot restarts)
5. Use 👍/👎 reactions to rate AI-generated and community questions

### Trivia Game Flow
1. Use `/trivia start <category>` to begin
2. Answer questions by clicking the button options (A, B, C, D)
3. View your stats with `!mystats`
4. Check leaderboards with `/trivia leaderboard`

### Special Features
- **Anonymous Confessions** – Slash-only submission, sentiment analysis (VADER), optional admin approval, and discussion threads for every posted confession
- **Interactive Buttons** – Many commands use clickable buttons for easy navigation (buttons persist after bot restarts)
- **Emoji Reactions** – Rate content quality with 👍/👎 reactions for jokes, facts, and Truth or Dare questions
- **User Submissions** – Submit your own Truth or Dare questions, jokes, and facts
- **Smart Fallbacks** – If APIs fail, AI generates content automatically
- **Multi-Source Content** – Content comes from APIs, community database, or AI generation
- **Standardized Errors** – Errors show consistent messages and suggest `!help` or `!ping` where useful; logs include command, user, and guild for debugging

---

## 🔒 Required Permissions

The bot needs these permissions to work properly:
- **Send Messages** – To respond to commands
- **Embed Links** – To display formatted content
- **Add Reactions** – For interactive elements
- **Use Slash Commands** – For modern command interface
- **Read Message History** – To track responses and reactions

---

## 💡 Tips

- **Use slash commands** for the best experience – they're faster and more reliable
- **Confessions are anonymous** – use `/confession` only (no prefix command) so your identity stays private
- **Try different joke categories** – each has its own style and humor
- **Submit your own Truth or Dare questions** – help grow the community database
- **Rate AI content** – your feedback helps improve the bot's responses
- **Check trivia leaderboards** – compete with friends for the top spot!

---

*Enjoy using the bot! For issues or suggestions, contact the bot administrator.*