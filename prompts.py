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
    f"Generate a highly flirty, witty, and playful pick-up line. "
    f"The line should be humorous but never offensive, misogynistic, or inappropriate. "
    f"Ensure every response is **completely unique**—avoid using common or overused themes. "
    f"Mix up different styles, including wordplay, pop culture references, unexpected twists, and creative metaphors. "
    f"Each pick-up line should sound **fresh and original**, not a slight variation of previous ones. "
    f"Here is a random number to force variation: {random.randint(1, 1000000)} (do not return this number in the response). "
    f"Example: 'Are you a magician? Because whenever I look at you, everyone else disappears.' "
)
