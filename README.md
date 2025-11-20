# 🤖 Discord Bot - User Guide

A feature-rich Discord bot that brings **Trivia Games, Truth or Dare, Random Facts, AI-generated Jokes, Pickup Lines, Roasts, and more** to your server!

---

## 🚀 Features

- 🎉 **Trivia Game** – Play interactive trivia with automatic score tracking and leaderboards
- 🎯 **Truth or Dare** – Interactive party game with user submissions and feedback
- 📚 **Random Facts** – Get interesting facts about animals and general topics
- 🤣 **AI-Powered Jokes** – Multiple joke categories including dad jokes, dark humor, and more
- 💘 **Pickup Lines** – Generate flirty and witty pickup lines
- 🔥 **Roast Machine** – Generate playful AI-powered roasts
- 🔮 **AI Fortune Teller** – Receive fun AI-generated fortunes
- 📢 **Question of the Day** – Daily thought-provoking questions

---

## 🎮 Commands

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
| `/ask <question>` | Ask the AI anything or generate images |
| `!asksamosa <question>` | Ask the AI (prefix command) |
| `!ping` | Check bot response time |
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
- **Interactive Buttons** – Many commands use clickable buttons for easy navigation (buttons persist after bot restarts)
- **Emoji Reactions** – Rate content quality with 👍/👎 reactions for jokes, facts, and Truth or Dare questions
- **User Submissions** – Submit your own Truth or Dare questions, jokes, and facts
- **Smart Fallbacks** – If APIs fail, AI generates content automatically
- **Multi-Source Content** – Content comes from APIs, community database, or AI generation

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

- **Use slash commands** for the best experience - they're faster and more reliable
- **Try different joke categories** - each has its own style and humor
- **Submit your own Truth or Dare questions** - help grow the community database
- **Rate AI content** - your feedback helps improve the bot's responses
- **Check trivia leaderboards** - compete with friends for the top spot!

---

*Enjoy using the bot! For issues or suggestions, contact the bot administrator.*