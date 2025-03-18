import random

# QOTD prompt
qotd_prompt = f"Generate an engaging Question of the Day for a Discord server. The question should be thought-provoking, fun, and suitable for group discussions. Don't add Question of the Day at beginning and also keep it single sentence. Example: 'What's the most useless talent you have?'. Here is a random number to force variation: {random.randint(1, 1000000)}. dont return the random number in response"

#jokes prompt
joke_insult_prompt = f"""
Generate a witty and humorous insult joke. It should roast someone in a fun and clever way, making sure it's playful and not overly offensive.
Avoid generic responses and ensure it's unique.

Respond strictly in JSON format:
{{
  "setup": "Setup sentence here",
  "punchline": "Punchline sentence here"
}}

Here is a random number to force variation: {random.randint(1, 1000000)}
Do not return the random number in the response.
"""

joke_dad_prompt = f"""
Tell me a fresh and funny dad joke. Ensure it's unique and not a common one.

Respond strictly in JSON format:
{{
  "setup": "Setup sentence here",
  "punchline": "Punchline sentence here"
}}

Here is a random number to force variation: {random.randint(1, 1000000)}
Do not return the random number in the response.
"""
joke_gen_prompt = f"""
Tell me a fresh, unpredictable, and humorous joke. Use different topics like animals, professions, technology, relationships, and daily life.
Do not repeat previous jokes.

Respond strictly in JSON format:
{{
  "setup": "Setup sentence here",
  "punchline": "Punchline sentence here"
}}

Here is a random number to force variation: {random.randint(1, 1000000)}
Do not return the random number in the response.
"""

# Pickup prompt
pickup_prompt = (
    f"Generate a bold, irresistibly flirty, and exceptionally witty pickup line. "
    f"The line should be **fun, cheeky, and playful** while avoiding anything offensive or inappropriate. "
    f"Think of lines that would make someone **smirk, blush, or laugh out loud.** "
    f"Ensure each response is **completely original**—avoid generic or predictable themes like WiFi, computers, and common clichés. "
    f"Use unexpected twists, pop culture nods, double entendres, clever wordplay, and **creative metaphors**. "
    f"Vary the topics—think of romance, adventure, luxury, art, literature, the supernatural, music, and even historical figures. "
    f"Make each line sound **fresh and unique**, ensuring no slight variation of previous ones. "
    f"Here is a random number to force variation: {random.randint(1, 1000000)} (do not return this number in the response). "
    f"Examples:\n"
    f"- 'Are you French? Because Eiffel for you.'\n"
    f"- 'If kisses were snowflakes, I'd send you a blizzard.'\n"
    f"- 'Are you made of copper and tellurium? Because you’re Cu-Te.'\n"
    f"- 'I was blinded by your beauty… but I’m fine now. Hey, what’s your name again?'\n"
    f"- 'Are you an unfinished novel? Because I just can’t put you down.' "
)