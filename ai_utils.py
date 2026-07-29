import os
import base64
import re
import time
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Danh sách model Vision miễn phí mới nhất trên OpenRouter
OPENROUTER_FREE_MODELS = [
    "inclusionai/ling-3.0-flash:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "google/gemma-4-31b-it:free"
]

# Danh sách model Google Gemini chính chủ
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash-latest"
]

def ask_groq_api(image_path):
    """Giải CAPTCHA qua Groq Cloud API."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    base64_image = image_to_base64(image_path)
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    # Groq sử dụng mô hình llama-3.2-11b-vision-preview hoặc tương đương nếu khả dụng
    for model_name in ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"]:
        try:
            print(f"[*] Thử giải CAPTCHA qua Groq Cloud API ({model_name})...")
            response = client.chat.completions.create(
                model=model_name,
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
                print(f"[+] Giải CAPTCHA thành công qua Groq Cloud API ({model_name})!")
                return text
        except Exception as e:
            print(f"[!] Groq model {model_name} không khả dụng: {e}")
    return None

def ask_google_gemini_api(image_path):
    """Giải CAPTCHA qua Google Gemini API (Tự động xoay tua gemini-2.5-flash -> gemini-2.0-flash)."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return None

    base64_image = image_to_base64(image_path)
    
    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": "image/png", "data": base64_image}},
                        {"text": "Read the text in this CAPTCHA image. Return only the exact text shown, nothing else."}
                    ]
                }
            ]
        }
        
        try:
            print(f"[*] Thử giải CAPTCHA qua Google Gemini API ({model})...")
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    if text:
                        print(f"[+] Giải CAPTCHA thành công qua Google Gemini API ({model})!")
                        return text
            else:
                print(f"[!] Google Gemini API model {model} lỗi {res.status_code}: {res.text[:120]}")
        except Exception as e:
            print(f"[!] Lỗi gọi Google Gemini API model {model}: {e}")
            
    return None

def ask_text_to_openrouter(image_path, model=None):
    """Đọc CAPTCHA từ ảnh bằng cơ chế Fallback thông minh 3 tầng."""
    
    # 1. Thử Google Gemini API chính chủ (mô hình gemini-2.5-flash đang HOẠT ĐỘNG RẤT TỐT!)
    if os.getenv("GOOGLE_API_KEY"):
        result = ask_google_gemini_api(image_path)
        if result:
            return result
        print("[!] Google Gemini API không khả dụng, chuyển sang Groq...")

    # 2. Thử Groq Cloud API nếu có GROQ_API_KEY
    if os.getenv("GROQ_API_KEY"):
        result = ask_groq_api(image_path)
        if result:
            return result
        print("[!] Groq API không khả dụng, chuyển sang OpenRouter...")

    # 3. Thử OpenRouter Free Models
    api_key = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise Exception("Không tìm thấy GROQ_API_KEY, GOOGLE_API_KEY hoặc OPENROUTER_API_KEY trong .env")
    
    is_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1" if is_openrouter else None
    )
    base64_image = image_to_base64(image_path)
    
    models_to_try = [model] if model else (OPENROUTER_FREE_MODELS if is_openrouter else ["gpt-4o"])
    
    last_exception = None
    for m in models_to_try:
        try:
            print(f"[*] Thử giải CAPTCHA bằng mô hình OpenRouter: {m}...")
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
                print(f"[+] Giải CAPTCHA thành công qua mô hình OpenRouter: {m}")
                return text
        except Exception as e:
            print(f"[!] Lỗi mô hình {m}: {e}")
            last_exception = e
            time.sleep(1)

    if last_exception:
        raise last_exception
    raise Exception("Không thể giải CAPTCHA bằng các mô hình AI có sẵn.")
