import random
random_number = random.randint(1, 1000000)

# Verification prompt
verification_prompt = (
    f"Generate 3 simple verification questions for a Discord server that:\n"
    f"1. Are very easy to answer\n"
    f"2. Have clear, unambiguous answers\n"
    f"3. Are appropriate for all ages\n"
    f"4. Don't require special knowledge\n"
    f"5. Are similar in difficulty to these examples:\n"
    f"   - 'What is 2+2?' (answer: '4')\n"
    f"   - 'What color is the sky?' (answer: 'blue')\n"
    f"   - 'How many days are in a week?' (answer: '7')\n\n"
    f"Return the questions in this exact JSON format:\n"
    f"[\n"
    f"    {{\"question\": \"Question 1?\", \"answer\": \"answer1\"}},\n"
    f"    {{\"question\": \"Question 2?\", \"answer\": \"answer2\"}},\n"
    f"    {{\"question\": \"Question 3?\", \"answer\": \"answer3\"}}\n"
    f"]\n\n"
    f"Here is a random number to force variation: {random_number}. Do not include this number in your response."
)

# QOTD prompt
qotd_prompt = (
    f"Generate a concise, engaging, unpredictable, and quirky single-sentence Question of the Day for a Discord server. "
    "The question should be thought-provoking yet humorous and silly, sparking lively group discussions, but keep it short—ideally under 20 words."
    "Avoid starting with phrases like 'Question of the Day' and do not reference the random number. "
    "For example: 'If animals could talk, which species would be the sassiest?' "
    f"Here is a random number to force variation: {random_number}. Do not include this number in your final response."
)

#jokes prompt - Hybrid approach: simple but with variation and creativity instructions
joke_insult_prompt = f"""Generate a joke that ends with a witty insult or burn. The punchline should be a clever way to make fun of someone. Think of jokes like: "Why did the smart person avoid you? Because they didn't want to catch stupid!" or "What do you call someone who's always wrong? You!"

Respond in JSON format:
{{
  "setup": "Setup sentence here",
  "punchline": "Punchline sentence here"
}}

Random variation: {random_number}"""

joke_dad_prompt = f"""Generate a fresh, witty dad joke with creative wordplay. Avoid common jokes like scarecrow, bicycle, or atoms. Use unexpected topics and clever twists.

Respond in JSON format:
{{
  "setup": "Setup sentence here", 
  "punchline": "Punchline sentence here"
}}

Random variation: {random_number}"""

joke_gen_prompt = f"""Generate a creative, unpredictable joke. Use diverse topics like technology, relationships, professions, or daily life. Avoid common jokes and ensure originality.

Respond in JSON format:
{{
  "setup": "Setup sentence here",
  "punchline": "Punchline sentence here"
}}

Random variation: {random_number}"""

# Pickup prompt - Hybrid approach: simple but with creativity and variation
pickup_prompt = f"""Generate a witty, creative pickup line. Use unexpected twists, clever wordplay, and creative metaphors. Vary topics and ensure originality.

Random variation: {random_number}"""

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

# Truth and Dare prompts
truth_pg_prompt = (
    "Generate a fun, family-friendly truth question for a party game. "
    "Keep it under 15 words. Make it interesting but appropriate for all ages. "
    "Examples: 'What's your biggest fear?' or 'What's the most embarrassing thing you've done?'"
)

truth_pg13_prompt = (
    "Generate a playful, flirty truth question for adults on a date or party. "
    "Keep it under 15 words. Be suggestive but not explicit. "
    "Examples: 'What's your biggest turn-on?' or 'What's the naughtiest thing you've done?'"
)

dare_pg_prompt = (
    "Generate a fun, family-friendly dare challenge for a party game. "
    "Keep it under 15 words. Make it entertaining but safe for all ages. "
    "Examples: 'Do 10 jumping jacks' or 'Sing your favorite song'"
)

dare_pg13_prompt = (
    "Generate a playful, flirty dare challenge for adults on a date or party. "
    "Keep it under 15 words. Be suggestive but not explicit. "
    "Examples: 'Give someone a 30-second massage' or 'Whisper something naughty in someone's ear'"
)

wyr_prompt = (
    "Generate a fun 'Would You Rather' question for a party game. "
    "Keep it under 15 words. Make it interesting and thought-provoking. "
    "Examples: 'Would you rather be able to fly or be invisible?' or 'Would you rather have unlimited money or unlimited time?'"
)

nhie_prompt = (
    "Generate a fun 'Never Have I Ever' statement for a party game. "
    "Keep it under 15 words. Make it interesting but not too personal. "
    "Examples: 'Never have I ever been to a concert' or 'Never have I ever lied about my age'"
)

# Facts prompts
fact_general_prompt = (
    "Generate a fun, interesting random fact about science, history, nature, or technology. "
    "Keep it under 50 words and make it educational and entertaining. "
    "Examples: 'The human brain contains approximately 86 billion neurons' or 'Honey never spoils - archaeologists have found edible honey in ancient Egyptian tombs'"
)

fact_animals_prompt = (
    "Generate a fun, interesting fact about animals (cats, dogs, or other pets). "
    "Keep it under 50 words and make it educational and entertaining. "
    "Examples: 'Cats spend 70% of their lives sleeping' or 'Dogs have a sense of smell 40 times stronger than humans'"
)
