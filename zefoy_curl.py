import os
import sys
import time
import base64
import re
from curl_cffi import requests
from ai_utils import ask_text_to_openrouter

def run_zefoy_curl(tiktok_url, service_id="4", duration_minutes=60):
    print(f"⚡ [SIÊU BOT CURL-CFFI] Khởi tạo kết nối siêu tốc tới Zefoy (Tốc độ x5)...")
    session = requests.Session(impersonate="chrome120")
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })

    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    try:
        res = session.get("https://zefoy.com", timeout=10)
        if res.status_code != 200:
            print(f"[!] Không thể truy cập Zefoy. Status: {res.status_code}")
            return False
            
        print("[+] Kết nối Zefoy qua curl_cffi thành công (200 OK)! PHPSESSID:", session.cookies.get("PHPSESSID"))

        # Tìm captcha encoded
        m_encoded = re.search(r'name="captcha_encoded"\s+value="(.*?)"', res.text)
        captcha_encoded = m_encoded.group(1) if m_encoded else ""

        # Lấy ảnh CAPTCHA
        img_match = re.search(r'<img[^>]+src=["\'](data:image/[^"\']+)["\']', res.text)
        if not img_match:
            img_match = re.search(r'src=["\'](data:image/png;base64,[^"\']+)["\']', res.text)

        if img_match:
            base64_data = img_match.group(1)
            # Lưu tạm ảnh captcha
            img_bytes = base64.b64decode(base64_data.split(",")[1])
            with open("captcha_curl.png", "wb") as f:
                f.write(img_bytes)

            print("[*] Đã tải ảnh CAPTCHA thành công qua curl_cffi. Đang gửi cho AI Vision...")
            captcha_text = ask_text_to_openrouter("captcha_curl.png")
            print(f"[+] AI nhận diện CAPTCHA: '{captcha_text}'")

            # Submit CAPTCHA qua POST
            post_data = {
                "captchalogin": captcha_text,
                "captcha_encoded": captcha_encoded
            }
            res_post = session.post("https://zefoy.com/", data=post_data, timeout=10)
            print(f"[+] Đã Submit CAPTCHA. Status: {res_post.status_code}")
        else:
            print("[*] Trang không yêu cầu CAPTCHA hoặc captcha_img được load qua JS.")

    except Exception as e:
        print(f"[!] Lỗi Siêu Bot Curl-Cffi: {e}")
        print("[*] Tự động fallback sang Selenium Headless...")
        return False

    return True

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("ZEFOY_URL", "https://vt.tiktok.com/ZSxxxxxx/")
    service = sys.argv[2] if len(sys.argv) > 2 else os.getenv("ZEFOY_SERVICE", "4")
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.getenv("BOT_DURATION", "60"))

    success = run_zefoy_curl(url, service_id=service, duration_minutes=duration)
    if not success:
        # Fallback sang zefoy_headless.py mặc định
        import subprocess
        subprocess.run([sys.executable, "zefoy_headless.py", url, service, str(duration)])
