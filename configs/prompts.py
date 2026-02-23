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

# QOTD prompt — seed injected per-request in cog (no module-level random here)
qotd_prompt = (
    "Generate a fun, engaging discussion question for a Discord server. "
    "Keep it under 15 words. Mix direct questions and hypotheticals; do not repeat the same theme. "
    "Examples: 'What's the best book you read recently?' 'If you were a candy bar, which would you be?' 'Who is a stranger you will never forget?' "
)

#jokes prompt - Hybrid approach: simple but with variation and creativity instructions
joke_insult_prompt = f"""Generate a joke that ends with a witty insult or burn. The punchline should be a clever way to make fun of someone. Think of jokes like: "Why did the smart person avoid you? Because they didn't want to catch stupid!" or "What do you call someone who's always wrong? You!"

Respond in JSON format:
{{
  "setup": "Setup sentence here",
  "punchline": "Punchline sentence here"
}}
"""

joke_dad_prompt = """Generate a fresh, witty dad joke with creative wordplay. Avoid common jokes like scarecrow, bicycle, or atoms. Use unexpected topics and clever twists.

Respond in JSON format:
{{
  "setup": "Setup sentence here", 
  "punchline": "Punchline sentence here"
}}
"""

joke_gen_prompt = """Generate a creative, unpredictable joke. Use diverse topics like technology, relationships, professions, or daily life. Avoid common jokes and ensure originality.

Respond in JSON format:
{{
  "setup": "Setup sentence here",
  "punchline": "Punchline sentence here"
}}
"""

# Pickup prompt — variation injected per-request at call site
pickup_prompt = """Generate a witty, creative pickup line. Use unexpected twists, clever wordplay, and creative metaphors. Vary topics and ensure originality.
"""

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

truth_r_prompt = (
    "Generate an explicit, adult-oriented truth question for mature audiences. "
    "Keep it under 15 words. Be direct and explicit about adult topics. "
    "Examples: 'What's your wildest sexual fantasy?' or 'What's the kinkiest thing you've tried?'"
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

dare_r_prompt = (
    "Generate an explicit, adult-oriented dare challenge for mature audiences. "
    "Keep it under 15 words. Be direct and explicit about adult activities. "
    "Examples: 'Strip down to your underwear' or 'Perform a sensual dance for the group'"
)

wyr_pg_prompt = (
    "Generate a fun, family-friendly 'Would You Rather' question for a party game. "
    "Keep it under 15 words. Make it interesting and thought-provoking but appropriate for all ages. "
    "Examples: 'Would you rather be able to fly or be invisible?' or 'Would you rather have unlimited money or unlimited time?'"
)

wyr_pg13_prompt = (
    "Generate a playful, flirty 'Would You Rather' question for adults on a date or party. "
    "Keep it under 15 words. Be suggestive but not explicit. "
    "Examples: 'Would you rather kiss someone you hate or never kiss again?' or 'Would you rather have a one-night stand or a long-term relationship?'"
)

wyr_r_prompt = (
    "Generate an explicit, adult-oriented 'Would You Rather' question for mature audiences. "
    "Keep it under 15 words. Be direct and explicit about adult topics. "
    "Examples: 'Would you rather have sex in public or with a stranger?' or 'Would you rather try BDSM or a threesome?'"
)

nhie_pg_prompt = (
    "Generate a fun, family-friendly 'Never Have I Ever' statement for a party game. "
    "Keep it under 15 words. Make it interesting but appropriate for all ages. "
    "Examples: 'Never have I ever been to a concert' or 'Never have I ever lied about my age'"
)

nhie_pg13_prompt = (
    "Generate a playful, flirty 'Never Have I Ever' statement for adults on a date or party. "
    "Keep it under 15 words. Be suggestive but not explicit. "
    "Examples: 'Never have I ever had a one-night stand' or 'Never have I ever sent a nude photo'"
)

nhie_r_prompt = (
    "Generate an explicit, adult-oriented 'Never Have I Ever' statement for mature audiences. "
    "Keep it under 15 words. Be direct and explicit about adult experiences. "
    "Examples: 'Never have I ever had sex in public' or 'Never have I ever tried BDSM'"
)

paranoia_pg_prompt = (
    "Generate a fun, family-friendly paranoia question for a party game. "
    "Keep it under 15 words. Make it spooky but appropriate for all ages. "
    "Examples: 'Who in this room would you trust with a secret?' or 'Who do you think is most likely to betray you?'"
)

paranoia_pg13_prompt = (
    "Generate a playful, flirty paranoia question for adults on a date or party. "
    "Keep it under 15 words. Be suggestive but not explicit. "
    "Examples: 'Who in this room would you most want to kiss?' or 'Who do you think has the dirtiest mind?'"
)

paranoia_r_prompt = (
    "Generate an explicit, adult-oriented paranoia question for mature audiences. "
    "Keep it under 15 words. Be direct and explicit about adult topics. "
    "Examples: 'Who in this room would you most want to have sex with?' or 'Who do you think has the kinkiest fantasies?'"
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
