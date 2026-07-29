import os
import sys
import time
import base64
import re
from curl_cffi import requests
from ai_utils import ask_text_to_openrouter
from proxy_manager import get_working_proxy

def run_zefoy_curl(tiktok_url, service_id="4", duration_minutes=60):
    print(f"⚡ [SIÊU BOT CURL-CFFI] Khởi tạo kết nối siêu tốc tới Zefoy (Tốc độ x5)...")
    
    proxy = get_working_proxy(max_checks=15)
    session = requests.Session(impersonate="chrome120")
    if proxy:
        proxy_url = f"http://{proxy}"
        session.proxies = {"http": proxy_url, "https": proxy_url}
        print(f"[+] [Proxy Auto-Rotate] Đã kết nối Zefoy qua Free Proxy: {proxy}")

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })

    try:
        res = session.get("https://zefoy.com", timeout=10)
        if res.status_code != 200:
            print(f"[!] Không thể truy cập Zefoy qua HTTP. Status: {res.status_code}")
            return False
            
        print("[+] Kết nối Zefoy qua curl_cffi thành công (200 OK)! PHPSESSID:", session.cookies.get("PHPSESSID"))

        # Kiểm tra xem Zefoy có load CAPTCHA qua JavaScript hay không
        m_encoded = re.search(r'name="captcha_encoded"\s+value="(.*?)"', res.text)
        captcha_encoded = m_encoded.group(1) if m_encoded else ""

        # Lấy ảnh CAPTCHA
        img_match = re.search(r'<img[^>]+src=["\'](data:image/[^"\']+)["\']', res.text)
        if not img_match:
            img_match = re.search(r'src=["\'](data:image/png;base64,[^"\']+)["\']', res.text)

        if img_match:
            base64_data = img_match.group(1)
            img_bytes = base64.b64decode(base64_data.split(",")[1])
            with open("captcha_curl.png", "wb") as f:
                f.write(img_bytes)

            print("[*] Đã tải ảnh CAPTCHA qua curl_cffi. Đang gửi cho AI Vision...")
            captcha_text = ask_text_to_openrouter("captcha_curl.png")
            print(f"[+] AI nhận diện CAPTCHA: '{captcha_text}'")

            post_data = {
                "captchalogin": captcha_text,
                "captcha_encoded": captcha_encoded
            }
            res_post = session.post("https://zefoy.com/", data=post_data, timeout=10)
            print(f"[+] Đã Submit CAPTCHA. Status: {res_post.status_code}")
            return True
        else:
            print("[*] Zefoy yêu cầu JavaScript render DOM động để tạo CAPTCHA key. Chuyển sang Selenium Headless...")
            return False

    except Exception as e:
        print(f"[!] Curl-Cffi notice: {e}")
        return False

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("ZEFOY_URL", "https://vt.tiktok.com/ZSxxxxxx/")
    service = sys.argv[2] if len(sys.argv) > 2 else os.getenv("ZEFOY_SERVICE", "4")
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.getenv("BOT_DURATION", "60"))

    success = run_zefoy_curl(url, service_id=service, duration_minutes=duration)
    if not success:
        print("[⚡] Tự động kích hoạt Selenium Headless Driver để cày 120 phút...")
        import subprocess
        subprocess.run([sys.executable, "zefoy_headless.py", "--service", service, "--url", url, "--duration", str(duration)])
