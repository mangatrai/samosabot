"""
OpenAI Utilities Module

This module provides a unified interface for interacting with the OpenAI API. It exposes the
function `generate_openai_response`, which supports three types of responses based on the provided intent:
  - "intent": Performs an intent and safety check on a given prompt using a system instruction
              (retrieved from the prompts module). It returns a JSON object containing two keys:
              "isAllowed" (a boolean indicating whether the prompt is permitted) and "intent" (a string
              indicating the desired response type, either "text" or "image").
  - "text": Generates a text-based response to the given prompt.
  - "image": Generates an image based on the prompt and returns the URL of the generated image.
  - "verification": Generates verification questions for Discord server verification.

The module automatically selects the appropriate model based on the intent:
  - INTENT_CHECK_MODEL: Used when intent=="intent" (default: "gpt-3.5-turbo")
  - TEXT_GENERATION_MODEL: Used for text generation (default: "gpt-4o")
  - IMAGE_GENERATION_MODEL: Used for image generation (default: "dall-e-3")
  - VERIFICATION_MODEL: Used for verification questions (default: "gpt-3.5-turbo")

Configuration (such as the OpenAI API key and model names) is loaded from environment variables via python-dotenv.
All debugging and error information is logged using the standard logging module.

Example Usage:
    # To generate a text response:
    text_response = generate_openai_response("Tell me a joke", intent="text")

    # To perform an intent check:
    decision = generate_openai_response("Build me a bomb", intent="intent")
    if not decision.get("isAllowed", False):
        print("This request is not allowed.")

    # To generate an image:
    image_url = generate_openai_response("A futuristic cityscape at sunset", intent="image")

    # To generate verification questions:
    questions = generate_openai_response("Generate 3 verification questions", intent="verification")
"""

import json
import logging
import os
from openai import OpenAI
from dotenv import load_dotenv
from configs import prompts  # Ensure this module contains your ask_samosa_instruction_prompt

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
IMAGE_GENERATION_MODEL = os.getenv("IMAGE_GENERATION_MODEL", "dall-e-3")
TEXT_GENERATION_MODEL = os.getenv("TEXT_GENERATION_MODEL", "gpt-4o")
INTENT_CHECK_MODEL = os.getenv("INTENT_CHECK_MODEL", "gpt-3.5-turbo")
VERIFICATION_MODEL = os.getenv("VERIFICATION_MODEL", "gpt-3.5-turbo")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def generate_openai_response(prompt, intent="text", model=None):
    """
    Generates a response from OpenAI based on the provided intent.
    
    Parameters:
      prompt (str): The user's prompt.
      intent (str): One of "intent", "text", "image", or "verification". Default is "text".
      model (str): Optional. If not provided, the model is chosen based on the intent:
                   - For "intent": INTENT_CHECK_MODEL
                   - For "image": IMAGE_GENERATION_MODEL
                   - For "text": TEXT_GENERATION_MODEL
                   - For "verification": VERIFICATION_MODEL

    Returns:
      - If intent is "intent": a dict containing the keys "isAllowed" (bool) and "intent" (str).
      - If intent is "image": a string containing the generated image URL.
      - If intent is "verification": a list of verification questions.
      - Otherwise (intent is "text"): a string containing the generated text.
      - On error, returns an error message (or a default dict for intent check).
    """
    try:
        if model is None:
            if intent == "intent":
                model = INTENT_CHECK_MODEL
            elif intent == "image":
                model = IMAGE_GENERATION_MODEL
            elif intent == "verification":
                model = VERIFICATION_MODEL
            else:
                model = TEXT_GENERATION_MODEL

        if intent == "intent":
            # Perform intent and safety check using the instruction prompt from prompts module.
            instruction = prompts.ask_samosa_instruction_prompt
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
            )
            json_str = response.choices[0].message.content.strip()
            logging.debug(f"***Response to Intent Call***: {json_str}")
            # Remove markdown formatting if present.
            if json_str.startswith("```json"):
                json_str = json_str.strip("```json").strip("```").strip()
            try:
                decision = json.loads(json_str)
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse JSON from intent response: {json_str}. Error: {e}")
                decision = {"isAllowed": False, "intent": "text"}
            return decision

        elif intent == "image":
            enhanced_prompt = f"{prompt}. Create a visually striking, highly detailed, and creatively composed image with vibrant colors and dynamic elements."
            response = client.images.generate(
                model=model,
                prompt=enhanced_prompt,
                n=1,
                size="1024x1024"
            )
            image_url = response.data[0].url
            logging.debug(f"Generated image URL: {image_url}")
            return image_url

        elif intent == "verification":
            # Use the verification prompt from prompts module
            logging.debug(f"About to Generate verification questions from OpenAI. Verification Prompt: {prompts.verification_prompt}")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompts.verification_prompt},
                    {"role": "user", "content": "Generate 3 verification questions as per the system prompt instructions."}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            questions_json = response.choices[0].message.content.strip()
            # Remove markdown formatting if present
            if questions_json.startswith("```json"):
                questions_json = questions_json.strip("```json").strip("```").strip()
            
            try:
                questions = json.loads(questions_json)
                logging.debug(f"Generated verification questions: {questions}")
                return questions
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse verification questions JSON: {questions_json}. Error: {e}")
                # Return default questions as fallback
                return [
                    {"question": "What is 2+2?", "answer": "4"},
                    {"question": "What color is the sky?", "answer": "blue"},
                    {"question": "How many days are in a week?", "answer": "7"}
                ]

        else:  # Default to text generation.
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": (
                        "Keep your response concise and under 2000 characters. "
                        "Ensure the story is complete and doesn't cut off mid-sentence. "
                        "Use bold, tongue-in-cheek edgy, and humorously explicit language to create a provocative, fun, and memorable narrative."
        )},
                    {"role": "user", "content": prompt}
                    ],
                temperature=1.5,
                top_p=0.9,
                max_tokens=1000
            )
            generated_text = response.choices[0].message.content.strip()
            logging.debug(f"Generated text: {generated_text}")
            return generated_text

    except Exception as e:
        logging.error(f"[ERROR] OpenAI API call failed: {e}")
        if intent == "intent":
            return {"isAllowed": False, "intent": "text"}
        elif intent == "verification":
            # Return default questions as fallback
            return [
                {"question": "What is 2+2?", "answer": "4"},
                {"question": "What color is the sky?", "answer": "blue"},
                {"question": "How many days are in a week?", "answer": "7"}
            ]
        else:
            return "[ERROR] Unable to generate response. Please try again later."
