import os
import base64
import re
import time
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Cache model đã verify thành công để dùng lại nhanh chóng
VERIFIED_MODEL_CACHE = {
    "google": None,
    "groq": None,
    "openrouter": None
}

def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# ─────────────────────────────────────────────────────────────
#  1. DYNAMIC GOOGLE GEMINI AUTOMATION SCANNER
# ─────────────────────────────────────────────────────────────
def get_working_google_gemini_model(api_key):
    """Tự động kiểm tra API Google để tìm model Gemini nào đang SỐNG & CÓ QUOTA (200 OK)."""
    global VERIFIED_MODEL_CACHE
    if VERIFIED_MODEL_CACHE["google"]:
        return VERIFIED_MODEL_CACHE["google"]

    url_list = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        res = requests.get(url_list, timeout=5)
        if res.status_code == 200:
            models_data = res.json().get("models", [])
            # Lọc các model dạng gemini flash/pro
            candidate_models = []
            for m in models_data:
                name = m.get("name", "").replace("models/", "")
                if "gemini" in name and ("flash" in name or "pro" in name):
                    candidate_models.append(name)
            
            # Đưa gemini-2.5-flash và gemini-2.0-flash lên đầu
            candidate_models.sort(key=lambda x: (0 if "2.5-flash" in x else (1 if "2.0-flash" in x else 2)))
            
            for m in candidate_models:
                test_url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
                test_res = requests.post(test_url, json={"contents": [{"parts": [{"text": "hi"}]}]}, timeout=5)
                if test_res.status_code == 200:
                    print(f"[+] [Automation Scanner] Google Model ĐANG SỐNG & SẴN SÀNG: {m}")
                    VERIFIED_MODEL_CACHE["google"] = m
                    return m
                else:
                    print(f"[!] [Automation Scanner] Google Model {m} trả về lỗi {test_res.status_code}")
    except Exception as e:
        print(f"[!] [Automation Scanner] Lỗi quét Google API: {e}")
    return "gemini-2.5-flash"

def ask_google_gemini_api(image_path):
    """Giải CAPTCHA qua Google Gemini API dùng model đã quét tự động thành công."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return None

    model_name = get_working_google_gemini_model(api_key)
    base64_image = image_to_base64(image_path)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
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
        print(f"[*] Thử giải CAPTCHA qua Google Gemini API ({model_name})...")
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            data = res.json()
            candidates = data.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                if text:
                    print(f"[+] Giải CAPTCHA thành công qua Google Gemini API ({model_name})!")
                    return text
        elif res.status_code == 429:
            print(f"[!] Google Gemini API {model_name} dính Quota (429), xóa cache để quét lại...")
            VERIFIED_MODEL_CACHE["google"] = None
    except Exception as e:
        print(f"[!] Lỗi gọi Google Gemini API: {e}")
    return None


# ─────────────────────────────────────────────────────────────
#  2. DYNAMIC GROQ CLOUD AUTOMATION SCANNER
# ─────────────────────────────────────────────────────────────
def get_working_groq_model(api_key):
    """Tự động quét danh sách model trên Groq API để tìm model Vision sống."""
    global VERIFIED_MODEL_CACHE
    if VERIFIED_MODEL_CACHE["groq"]:
        return VERIFIED_MODEL_CACHE["groq"]

    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json().get("data", [])
            vision_models = [m.get("id") for m in data if "vision" in m.get("id", "").lower() or "llama-3.2" in m.get("id", "").lower()]
            for m in vision_models:
                print(f"[+] [Automation Scanner] Tìm thấy Groq Vision Model: {m}")
                VERIFIED_MODEL_CACHE["groq"] = m
                return m
    except Exception as e:
        print(f"[!] [Automation Scanner] Lỗi quét Groq API: {e}")
    return None

def ask_groq_api(image_path):
    """Giải CAPTCHA qua Groq Cloud API."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    model_name = get_working_groq_model(api_key)
    if not model_name:
        return None

    base64_image = image_to_base64(image_path)
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
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
        print(f"[!] Groq model {model_name} lỗi: {e}")
        VERIFIED_MODEL_CACHE["groq"] = None
    return None


# ─────────────────────────────────────────────────────────────
#  3. DYNAMIC OPENROUTER AUTOMATION SCANNER
# ─────────────────────────────────────────────────────────────
def get_live_openrouter_free_models():
    """Tự động quét toàn bộ hệ thống OpenRouter để tìm danh sách các mô hình Vision Miễn phí đang mở endpoint."""
    try:
        res = requests.get("https://openrouter.ai/api/v1/models", timeout=5)
        if res.status_code == 200:
            data = res.json().get("data", [])
            live_free = []
            for m in data:
                mid = m.get("id", "")
                if mid.endswith(":free"):
                    architecture = m.get("architecture", {})
                    modality = str(architecture.get("modality", "")).lower()
                    if "image" in modality or "vision" in modality or "multimodal" in modality or "vl" in mid or "flash" in mid:
                        live_free.append(mid)
            if live_free:
                print(f"[+] [Automation Scanner] Tìm thấy {len(live_free)} OpenRouter Free Vision Models đang sống: {live_free}")
                return live_free
    except Exception as e:
        print(f"[!] [Automation Scanner] Lỗi quét OpenRouter: {e}")
    return ["inclusionai/ling-3.0-flash:free", "nvidia/nemotron-nano-12b-v2-vl:free", "google/gemma-4-31b-it:free"]


def ask_text_to_openrouter(image_path, model=None):
    """Tự động chọn mô hình AI sống 100% bằng thuật toán Automation Scanner."""
    
    # 1. Thử Google Gemini API tự động quét model 200 OK
    if os.getenv("GOOGLE_API_KEY"):
        result = ask_google_gemini_api(image_path)
        if result:
            return result
        print("[!] Chuyển sang Groq...")

    # 2. Thử Groq Cloud API
    if os.getenv("GROQ_API_KEY"):
        result = ask_groq_api(image_path)
        if result:
            return result
        print("[!] Chuyển sang OpenRouter...")

    # 3. Quét động các model Free sống trên OpenRouter
    api_key = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise Exception("Không tìm thấy GROQ_API_KEY, GOOGLE_API_KEY hoặc OPENROUTER_API_KEY trong .env")
    
    is_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1" if is_openrouter else None
    )
    base64_image = image_to_base64(image_path)
    
    openrouter_live_models = get_live_openrouter_free_models()
    models_to_try = [model] if model else (openrouter_live_models if is_openrouter else ["gpt-4o"])
    
    last_exception = None
    for m in models_to_try:
        try:
            print(f"[*] Thử giải CAPTCHA qua OpenRouter ({m})...")
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
                print(f"[+] Giải CAPTCHA thành công qua OpenRouter ({m})!")
                return text
        except Exception as e:
            print(f"[!] Lỗi OpenRouter {m}: {e}")
            last_exception = e
            time.sleep(1)

    if last_exception:
        raise last_exception
    raise Exception("Không thể giải CAPTCHA bằng bất kỳ mô hình AI nào.")
