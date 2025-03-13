# 🤖 Discord Bot with OpenAI & PostgreSQL

A feature-rich Discord bot that brings **Trivia Games, QOTD (Question of the Day), AI-generated Jokes, and Pickup Lines** to your server. This bot integrates **OpenAI for dynamic content** and **PostgreSQL for persistent storage**.

---

## 🚀 Features

- 🎉 **Trivia Game** – Play interactive trivia with automatic score tracking.
- 📢 **QOTD (Question of the Day)** – Generate and schedule daily thought-provoking questions.
- 🤣 **AI-Powered Jokes** – Fetch dad jokes, insult jokes, and general humor from OpenAI.
- 💘 **Pickup Lines** – Generate flirty and witty pickup lines.
- 🏆 **Persistent Leaderboards** – Trivia scores are stored and can be retrieved anytime.
- 🔄 **Scheduled Bot Status Updates** – Sends periodic bot status messages to a designated channel.

---

# 🎮 Discord Bot
---
## 🎮 Bot Commands

### 🎉 Trivia Game
| Command | Description |
|---------|-------------|
| `!trivia start <category>` | Start a trivia game. |
| `!trivia stop` | Stop an ongoing trivia game. |
| `!mystats` | View your trivia stats. |

### 📢 Question of the Day (QOTD)
| Command | Description |
|---------|-------------|
| `!setqotdchannel <channel>` | Set QOTD channel. |
| `!startqotd` | Start daily QOTD schedule. |
| `!qotd` | Get a random question. |

### 🤣 AI Jokes
| Command | Description |
|---------|-------------|
| `!joke dad` | Get a dad joke. |
| `!joke insult` | Get a witty insult joke. |
| `!joke` | Get a general joke. |

### 💘 Pickup Lines
| Command | Description |
|---------|-------------|
| `!pickup` | Get a fun AI-generated pickup line. |

### 🔄 Bot Status
| Command | Description |
|---------|-------------|
| `!samosa botstatus <channel>` | Set a bot status channel. |


---

## 🎯 Built With

| Technology | Description |
|------------|-------------|
| **Python** | Core programming language. |
| **Discord.py** | Discord bot framework. |
| **OpenAI API** | AI-generated content. |
| **PostgreSQL** | Database for storing user data. |
| **SQLAlchemy** | ORM for database queries. |