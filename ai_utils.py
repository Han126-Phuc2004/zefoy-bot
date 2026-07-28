import os
import base64
import re
import time
from dotenv import load_dotenv
from openai import OpenAI, APIStatusError

load_dotenv()

# --- Utility Functions ---
def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# --- OpenRouter Functions ---
def ask_text_to_openrouter(image_path, model=None):
    """Read CAPTCHA text from image using OpenRouter free vision models."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENROUTER_API_KEY or OPENAI_API_KEY not configured in .env")
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1" if os.getenv("OPENROUTER_API_KEY") else None
    )
    base64_image = image_to_base64(image_path)
    model_to_use = model if model else ("nvidia/nemotron-nano-12b-v2-vl:free" if os.getenv("OPENROUTER_API_KEY") else "gpt-4o")
    
    response = client.chat.completions.create(
        model=model_to_use,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                {"type": "text", "text": "Read the text in this CAPTCHA image. Return only the exact text shown, nothing else."}
            ]
        }],
        max_tokens=50
    )
    return response.choices[0].message.content.strip()
