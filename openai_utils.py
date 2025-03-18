from openai import OpenAI
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
USE_LLM_INTENT = os.getenv("USE_LLM_INTENT", "True").lower() == "true"  # Added this line

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

def generate_openai_response(prompt):
    """Generates a response from OpenAI, intelligently choosing between text and image."""
    try:
        if USE_LLM_INTENT: # added if statement
            # Ask the model to determine the intent
            intent_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Your job is to strictly return either 'image' or 'text' and nothing else."},
                    {"role": "user", "content": prompt}
                    ],
                max_tokens=10,
            )
            intent = intent_response.choices[0].message.content.strip().lower()

            if "image" in intent:
                # Generate an image
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    n=1,
                    size="1024x1024"
                )
                image_url = response.data[0].url
                logging.debug(f"Generated image URL: {image_url}")
                return image_url
            else:
                # Generate text
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=1.5,
                    top_p=0.9,
                )
                generated_text = response.choices[0].message.content.strip()
                logging.debug(f"Generated text: {generated_text}")
                return generated_text
        else: # added else statement
            # Fallback to keyword-based intent detection
            if "image" in prompt.lower() or "draw" in prompt.lower() or "picture" in prompt.lower():
                # Generate an image
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    n=1,
                    size="1024x1024"
                )
                image_url = response.data[0].url
                logging.debug(f"Generated image URL: {image_url}")
                return image_url
            else:
                # Generate text
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=1.5,
                    top_p=0.9,
                )
                generated_text = response.choices[0].message.content.strip()
                logging.debug(f"Generated text: {generated_text}")
                return generated_text

    except Exception as e:
        logging.error(f"[ERROR] OpenAI API call failed: {e}")
        return "[ERROR] Unable to generate response. Please try again later."