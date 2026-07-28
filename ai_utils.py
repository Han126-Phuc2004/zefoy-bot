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

FREE_VISION_MODELS = [
    "google/gemini-2.5-flash:free",
    "google/gemini-2.0-flash-exp:free",
    "qwen/qwen-2.5-vl-72b-instruct:free",
    "mistralai/pixtral-12b:free",
    "nvidia/nemotron-nano-12b-v2-vl:free"
]

def ask_groq_api(image_path):
    """Giải CAPTCHA qua Groq Cloud API siêu tốc (sử dụng Llama 3.2 Vision)."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    base64_image = image_to_base64(image_path)
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    try:
        print("[*] Thử giải CAPTCHA qua Groq Cloud API (Llama 3.2 Vision)...")
        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
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
            print("[+] Giải CAPTCHA thành công qua Groq Cloud API!")
            return text
    except Exception as e:
        print(f"[!] Lỗi gọi Groq Cloud API: {e}")
    return None

def ask_google_gemini_api(image_path):
    """Giải CAPTCHA qua Google Gemini API chính chủ (nếu có GOOGLE_API_KEY)."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return None

    base64_image = image_to_base64(image_path)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
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
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            data = res.json()
            candidates = data.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                if text:
                    print("[+] Giải CAPTCHA thành công qua Google Gemini API!")
                    return text
        else:
            print(f"[!] Google Gemini API trả về mã lỗi {res.status_code}: {res.text[:150]}")
    except Exception as e:
        print(f"[!] Lỗi gọi Google Gemini API: {e}")
    return None

def ask_text_to_openrouter(image_path, model=None):
    """Đọc CAPTCHA từ ảnh bằng cơ chế Fallback đa tầng (Groq API -> Google Gemini API -> OpenRouter Multi-Models)."""
    
    # 1. Thử Groq Cloud API nếu có GROQ_API_KEY
    if os.getenv("GROQ_API_KEY"):
        result = ask_groq_api(image_path)
        if result:
            return result
        print("[!] Groq API không thành công, chuyển sang Google Gemini API...")

    # 2. Thử Google Gemini API trực tiếp nếu có GOOGLE_API_KEY
    if os.getenv("GOOGLE_API_KEY"):
        result = ask_google_gemini_api(image_path)
        if result:
            return result
        print("[!] Google Gemini API không thành công, chuyển sang OpenRouter...")

    # 3. Thử xoay tua các mô hình OpenRouter Free
    api_key = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise Exception("Không tìm thấy GROQ_API_KEY, GOOGLE_API_KEY hoặc OPENROUTER_API_KEY trong .env")
    
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
                print(f"[+] Giải CAPTCHA thành công qua mô hình: {m}")
                return text
        except Exception as e:
            print(f"[!] Lỗi mô hình {m}: {e}")
            last_exception = e
            time.sleep(1)

    if last_exception:
        raise last_exception
    raise Exception("Không thể giải CAPTCHA bằng các mô hình AI có sẵn.")
