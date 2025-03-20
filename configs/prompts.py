import random
random_number = random.randint(1, 1000000)

# QOTD prompt
qotd_prompt = (
    f"Generate a concise, engaging, unpredictable, and quirky single-sentence Question of the Day for a Discord server. "
    "The question should be thought-provoking yet humorous and silly, sparking lively group discussions, but keep it short—ideally under 20 words."
    "Avoid starting with phrases like 'Question of the Day' and do not reference the random number. "
    "For example: 'If animals could talk, which species would be the sassiest?' "
    f"Here is a random number to force variation: {random_number}. Do not include this number in your final response."
)

#jokes prompt
joke_insult_prompt = f"""
Generate a brutally scathing and cutting insult joke that delivers a real verbal smack. The joke should be aggressively witty and uniquely insulting, ensuring it doesn't come off as a soft blow. It must be playful yet ruthless, and the punchline should hit hard with clever sarcasm. Avoid generic or mild responses.

Respond strictly in JSON format:
{{
  "setup": "Setup sentence here",
  "punchline": "Punchline sentence here"
}}

Here is a random number to force variation: {random_number}
Do not return the random number in the response.
"""

joke_dad_prompt = f"""
Generate a fresh, witty, and truly unique dad joke that is short and to the point. The joke should have a concise setup and a punchy punchline that delivers a quick, humorous twist. Avoid common, overused jokes and explore a wide range of topics or wordplays to keep it surprising.

Respond strictly in JSON format:
{{
  "setup": "Setup sentence here",
  "punchline": "Punchline sentence here"
}}

Here is a random number to force variation: {random_number}
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

Here is a random number to force variation: {random_number}
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
    f"Here is a random number to force variation: {random_number} (do not return this number in the response). "
    f"Examples:\n"
    f"- 'Are you French? Because Eiffel for you.'\n"
    f"- 'If kisses were snowflakes, I'd send you a blizzard.'\n"
    f"- 'Are you made of copper and tellurium? Because you’re Cu-Te.'\n"
    f"- 'I was blinded by your beauty… but I’m fine now. Hey, what’s your name again?'\n"
    f"- 'Are you an unfinished novel? Because I just can’t put you down.' "
)

ask_samosa_instruction_prompt = (
    "Your job is to analyze the following prompt and determine two things. "
    "First, determine if the prompt is allowed. The prompt is disallowed if it contains content that is illegal, incites violence, is divisive, or otherwise sensitive in nature, "
    "except that creative requests such as love stories, love scenes, or smut are explicitly allowed. "
    "User mentions (e.g., <@UserID>) are permitted when used in creative or descriptive contexts and do not constitute sensitive content by themselves. "
    "Second, determine if the prompt is intended to generate an image or text. "
    "Return your answer as a JSON object with exactly two keys: "
    "'isAllowed' (a boolean) and 'intent' (a string that is either 'text' or 'image'). "
    "For example, if the prompt is allowed and should generate text, return exactly: "
    '{"isAllowed": true, "intent": "text"}. '
    "Only return the JSON object without any additional text. "
)

roast_prompt = (
    "Generate a scathing, witty, and edgy roast for {target}. The roast should be brutally insulting and sharply critical, "
    "using clever humor and sarcasm, without crossing into mean-spiritedness. After delivering the harsh roast, "
    "end with a sincere, unexpected compliment that softens the blow and leaves the target feeling respected. "
    "Ensure the transition from insult to compliment is smooth and creative."
)