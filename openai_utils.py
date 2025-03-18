from openai import OpenAI
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # LOG_LEVEL for logging

# Convert LOG_LEVEL string to logging level constant
try:
    log_level = getattr(logging, LOG_LEVEL.upper())
except AttributeError:
    print(f"WARNING: Invalid LOG_LEVEL '{LOG_LEVEL}'. Defaulting to INFO.")
    log_level = logging.INFO

# Configure logging
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Make call to OpenAI to generate Response
def generate_openai_prompt(prompt):
    """Generates a response from OpenAI based on the given prompt."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Or your preferred model
            messages=[{"role": "system", "content": prompt}],
            temperature=1.5,
            top_p=0.9,
        )
        generated_text = response.choices[0].message.content.strip()
        logging.debug(f"Generated text: {generated_text}")
        return generated_text
    except Exception as e:
        print(f"[ERROR] OpenAI API call failed: {e}")
        return "[ERROR] Unable to generate response. Please try again later."