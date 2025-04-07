# 🤖 Discord Bot with OpenAI & AstraDB

A feature-rich Discord bot that brings **Trivia Games, QOTD (Question of the Day), AI-generated Jokes, Pickup Lines, Roasts, Compliments, and Fortune Telling** to your server. This bot integrates **OpenAI for dynamic content** and **AstraDB for persistent storage**. Additionally, the bot now records server registrations including installation date, current status (JOINED/LEFT), and last updated timestamp.

---

## 🚀 Features

- 🎉 **Trivia Game** – Play interactive trivia with automatic score tracking and leaderboards.
- 🏆 **Trivia Leaderboard** – View the top trivia players in the server.
- 📢 **QOTD (Question of the Day)** – Generate and schedule daily thought-provoking questions.
- 🤣 **AI-Powered Jokes** – Fetch dad jokes, insult jokes, and general humor from OpenAI.
- 💘 **Pickup Lines** – Generate flirty and witty pickup lines.
- 🔥 **Roast & Compliment Machine** – Generate playful yet biting AI-powered roasts and compliments.
- 🔮 **AI Fortune Teller** – Receive a fun AI-generated fortune about your future.
- 🔄 **Scheduled Bot Status Updates** – Sends periodic bot status messages to a designated channel.
- 🌐 **Server Registration & Monitoring** – Automatically records every server (guild) where the bot is installed, capturing the guild ID, name, installation date, current status (JOINED/LEFT), and last updated timestamp.
- 📜 **List Servers** – Use the `!listservers` command to display all registered servers along with their details.

---

## 🎮 Bot Commands

### 🎉 Trivia Game
| Command | Description |
|---------|-------------|
| `!trivia start <category>` | Start a trivia game in the selected category. |
| `!trivia stop` | Stop an ongoing trivia game. |
| `!mystats` | View your trivia stats. |
| `!trivia leaderboard` | View the top trivia players on the server. |

| Slash Command | Description |
|--------------|-------------|
| `/trivia start <category>` | Start a trivia game in the selected category. |
| `/trivia stop` | Stop an ongoing trivia game. |
| `/trivia leaderboard` | View the top trivia players on the server. |

#### 🎯 Available Trivia Categories:
- History
- Science
- Geography
- Sports
- Movies
- Animals
- Music
- Video Games
- Technology
- Literature
- Mythology
- Food & Drink
- Celebrities
- Riddles & Brain Teasers
- Space & Astronomy
- Cars & Automobiles
- Marvel & DC (Comics)
- Holidays & Traditions

#### ⚡ Trivia Speed Settings:
- **Slow-Paced** (Default): More time to think and answer questions
- **Fast-Paced**: Quick questions with shorter answer times

To start a fast-paced trivia game, use:
- `!trivia start <category> fast` (Prefix command)
- `/trivia start <category> speed:Fast` (Slash command)

---

### 📢 Question of the Day (QOTD)
| Command | Description |
|---------|-------------|
| `!setqotdchannel <channel>` | Set the QOTD channel. |
| `!startqotd` | Start the daily QOTD schedule. |
| `!qotd` | Get a random question. |

| Slash Command | Description |
|--------------|-------------|
| `/qotd` | Get a random question. |

---

### 🤣 AI Jokes
| Command | Description |
|---------|-------------|
| `!joke dad` | Get a dad joke. |
| `!joke insult` | Get a witty insult joke. |
| `!joke` | Get a general joke. |

---

### 💘 Pickup Lines
| Command | Description |
|---------|-------------|
| `!pickup` | Get a fun AI-generated pickup line. |

---

### 🔥 Roast & Compliment Machine
| Command | Description |
|---------|-------------|
| `!roast @user` | Generate a playful AI-powered roast for a user. |
| `!compliment @user` | Generate a nice AI-powered compliment for a user. |

---

### 🔮 AI Fortune Teller
| Command | Description |
|---------|-------------|
| `!fortune` | Receive a fun AI-generated fortune about your future. |

---

### 🔄 Bot Status
| Command | Description |
|---------|-------------|
| `!samosa botstatus <channel>` | Set a bot status channel. |

| Slash Command | Description |
|--------------|-------------|
| `/samosa botstatus <channel>` | Set a bot status channel. |

---

### 🌐 Server Registration & Monitoring
| Command | Description |
|---------|-------------|
| `!listservers` | List all registered servers with details such as guild name, ID, installation date, status, and last updated timestamp. |

---

## 🎯 Built With

| Technology      | Description                                       |
|-----------------|---------------------------------------------------|
| **Python**      | Core programming language.                        |
| **Discord.py**  | Discord bot framework for prefix and slash commands. |
| **OpenAI API**  | AI-generated dynamic content.                     |
| **AstraDB**     | Database for persistent storage via astrapy.       |

---

## 🔒 Verification & Setup

### Required Bot Permissions
- **Send Messages**: To send trivia questions, results, and other bot messages
- **Embed Links**: To display formatted trivia questions and results
- **Add Reactions**: For interactive elements
- **View Channels**: To see messages in channels where trivia is played
- **Read Message History**: To track user responses
- **Use Slash Commands**: To register and use slash commands

### Server Roles
- **Bot Role**: Should have permissions to send messages, embed links, and add reactions
- **User Role**: Should have permissions to view channels and send messages
- **Admin Role**: Should have permissions to manage channels and roles

### Verification Commands
| Slash Command | Description |
|--------------|-------------|
| `/verification` | Configure verification settings (enable/disable/setup) |
| `/verification_status` | Check current verification settings for the server |
| `/setup_wizard` | Start the verification setup wizard to configure the system step by step |

The verification system automatically creates a temporary verification channel for new members and guides them through the verification process.

---
