import os
import base64
import re
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# --- Utility Functions ---
def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

FREE_VISION_MODELS = [
    "google/gemini-2.5-flash:free",
    "google/gemini-2.0-flash-exp:free",
    "qwen/qwen-2.5-vl-72b-instruct:free",
    "mistralai/pixtral-12b:free",
    "nvidia/nemotron-nano-12b-v2-vl:free"
]

# --- OpenRouter Functions ---
def ask_text_to_openrouter(image_path, model=None):
    """Read CAPTCHA text from image using OpenRouter free vision models with automatic fallback list."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENROUTER_API_KEY or OPENAI_API_KEY not configured in .env")
    
    is_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1" if is_openrouter else None
    )
    base64_image = image_to_base64(image_path)
    
    models_to_try = [model] if model else (FREE_VISION_MODELS if is_openrouter else ["gpt-4o"])
    
    last_exception = None
    for m in models_to_try:
        try:
            print(f"[*] Thử giải CAPTCHA bằng mô hình: {m}...")
            response = client.chat.completions.create(
                model=m,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                        {"type": "text", "text": "Read the text in this CAPTCHA image. Return only the exact text shown, nothing else."}
                    ]
                }],
                max_tokens=30
            )
            text = response.choices[0].message.content.strip()
            if text:
                return text
        except Exception as e:
            print(f"[!] Lỗi khi gọi model {m}: {e}")
            last_exception = e
            time.sleep(1)

    if last_exception:
        raise last_exception
    raise Exception("Không thể giải CAPTCHA bằng các mô hình AI có sẵn.")
