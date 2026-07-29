"""
zefoy_headless.py  –  Phiên bản deploy trên Server / GitHub Actions / VPS (không cần màn hình)
Tự động gửi thông báo tiến trình & số lượng View về Telegram!
"""

import os
import sys
import time
import re
import argparse
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from ai_utils import ask_text_to_openrouter
from proxy_manager import get_working_proxy

# ─────────────────────────────────────────────────────────────
#  TELEGRAM NOTIFICATION HELPER
# ─────────────────────────────────────────────────────────────
def send_telegram_notification(msg: str):
    """Gửi thông báo tiến trình & số view trực tiếp về Telegram chat."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            res = requests.post(url, json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "Markdown"
            }, timeout=8)
            if res.status_code != 200:
                # If Telegram rejects markdown formatting, retry as plain text
                clean_text = re.sub(r'[*_`~]', '', msg)
                requests.post(url, json={
                    "chat_id": chat_id,
                    "text": clean_text
                }, timeout=8)
        except Exception as e:
            print(f"[!] Lỗi gửi Telegram notification: {e}")

# ─────────────────────────────────────────────────────────────
#  SERVICE MAP
# ─────────────────────────────────────────────────────────────
SERVICES = {
    "1": {"name": "Followers",       "css": ".t-followers-button"},
    "2": {"name": "Hearts",          "css": ".t-hearts-button"},
    "3": {"name": "Comments Hearts", "css": ".t-chearts-button"},
    "4": {"name": "Views",           "css": ".t-views-button"},
    "5": {"name": "Shares",          "css": ".t-shares-button"},
    "6": {"name": "Favorites",       "css": ".t-favorites-button"},
    "7": {"name": "Live Stream",     "css": ".t-livestream-button"},
    "8": {"name": "Repost",          "css": ".t-repost-button"},
}

def create_driver(proxy=None):
    """Tạo Chrome driver chạy headless (không cần màn hình)."""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--lang=en-US")
    opts.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    if proxy:
        opts.add_argument(f"--proxy-server=http://{proxy}")
        print(f"[+] [Proxy Auto-Rotate] Selenium Chrome sử dụng Free Proxy: {proxy}")

    opts.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2
    })

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
    except Exception:
        driver = webdriver.Chrome(options=opts)

    return driver

def handle_alerts(driver):
    try:
        alert = driver.switch_to.alert
        print(f"[!] Tự động đóng Alert: {alert.text}")
        alert.accept()
        time.sleep(0.5)
    except Exception:
        pass

def is_captcha_present(driver):
    handle_alerts(driver)
    try:
        captcha_inputs = driver.find_elements(By.CSS_SELECTOR,
            "input.captcha-login-input, input[name='captchalogin']")
        for inp in captcha_inputs:
            if inp.is_displayed():
                return True
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            if inp.is_displayed():
                ph = (inp.get_attribute("placeholder") or "").lower()
                if "enter the word" in ph or "enter the text" in ph:
                    return True
        images = driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            if img.is_displayed():
                src = (img.get_attribute("src") or "").lower()
                if "captcha" in src or "php" in src:
                    return True
    except Exception:
        pass
    return False

def check_remaining_time(driver):
    """Kiểm tra chính xác số giây cần chờ (cooldown) trên trang Zefoy."""
    handle_alerts(driver)
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text

        # 1. Matches: "Please wait 2 minute(s) 15 second(s)"
        m1 = re.search(r"Please wait\s*(\d+)\s*minute\(s\)\s*(\d+)\s*second\(s\)", page_text, re.IGNORECASE)
        if m1:
            return int(m1.group(1)) * 60 + int(m1.group(2))

        # 2. Matches: "Please wait 45 second(s)"
        m2 = re.search(r"Please wait\s*(\d+)\s*second\(s\)", page_text, re.IGNORECASE)
        if m2:
            return int(m2.group(1))

        # 3. Matches: "Please wait 2 minute(s)"
        m3 = re.search(r"Please wait\s*(\d+)\s*minute\(s\)", page_text, re.IGNORECASE)
        if m3:
            return int(m3.group(1)) * 60

        # 4. Matches: button text timers (e.g. 02:15, 2m 15s, 135s)
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for b in buttons:
            if b.is_displayed():
                txt = b.text.strip()
                m_btn1 = re.search(r"(\d+)\s*m(?:in)?\s*(\d+)\s*s(?:ec)?", txt, re.IGNORECASE)
                if m_btn1:
                    return int(m_btn1.group(1)) * 60 + int(m_btn1.group(2))
                m_btn2 = re.search(r"(\d{1,2}):(\d{2})", txt)
                if m_btn2:
                    return int(m_btn2.group(1)) * 60 + int(m_btn2.group(2))
                m_btn3 = re.search(r"^(\d+)\s*s(?:ec)?$", txt, re.IGNORECASE)
                if m_btn3:
                    return int(m_btn3.group(1))
    except Exception:
        pass
    return 0

def handle_timer_cooldown(seconds, service_name="", send_telegram=False):
    """Hiển thị đồng hồ đếm ngược từng giây chuyên nghiệp trong console và gửi Telegram."""
    mins, secs = divmod(seconds, 60)
    time_fmt = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
    
    print(f"\n⏱ [Timer Checker] Phát hiện thời gian chờ: {time_fmt} ({seconds} giây)")
    if send_telegram:
        send_telegram_notification(f"⏳ *[Zefoy Cooldown]*\n🔹 Dịch vụ: `{service_name}`\n⏱ Cần chờ: *{time_fmt}* ({seconds}s) trước lượt tiếp theo.")

    start_time = time.time()
    while True:
        elapsed = int(time.time() - start_time)
        remaining = seconds - elapsed
        if remaining <= 0:
            break
        m, s = divmod(remaining, 60)
        print(f"\r⏳ [Đếm ngược Cooldown] Thời gian còn lại: {m:02d}:{s:02d} ({remaining}s)...   ", end="", flush=True)
        time.sleep(1)
    
    print("\n✅ [Timer Checker] Hết thời gian chờ! Đang tự động kiểm tra & Submit lại...\n")

def select_service(driver, service_css, service_name):
    handle_alerts(driver)
    try:
        btn = driver.find_element(By.CSS_SELECTOR, service_css)
        if btn and btn.is_displayed() and btn.is_enabled():
            print(f"[+] Tìm thấy nút '{service_name}'! Đang click...")
            btn.click()
            time.sleep(2)
            return True
    except Exception:
        pass
    try:
        cls_keyword = service_css.lstrip(".")
        for b in driver.find_elements(By.TAG_NAME, "button"):
            if b.is_displayed() and b.is_enabled():
                if cls_keyword in (b.get_attribute("class") or ""):
                    print(f"[+] (fallback) Found '{service_name}' button! Clicking...")
                    b.click()
                    time.sleep(2)
                    return True
    except Exception:
        pass
    return False

def ensure_input_filled(driver, video_url):
    handle_alerts(driver)
    if not video_url or is_captcha_present(driver):
        return
    try:
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            if inp.is_displayed():
                ph   = (inp.get_attribute("placeholder") or "").lower()
                name = (inp.get_attribute("name") or "").lower()
                cls  = (inp.get_attribute("class") or "").lower()
                if "enter the word" in ph or "captchalogin" in name or "captcha-login-input" in cls:
                    continue
                val = inp.get_attribute("value") or ""
                if not val.strip():
                    inp.clear()
                    inp.send_keys(video_url)
                    print("[+] Re-filled video URL into input box.")
                break
    except Exception:
        pass

def _click_captcha_refresh(driver):
    try:
        for sel in ["img.captcha-img ~ a", "a[onclick*='captcha']",
                    ".captcha-refresh", "a[href*='captcha']",
                    "svg[class*='refresh']", "i[class*='refresh']"]:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            for btn in btns:
                if btn.is_displayed():
                    btn.click()
                    return
        imgs = driver.find_elements(By.CSS_SELECTOR, "img[src*='php'], img[src*='captcha']")
        for img in imgs:
            parent = img.find_element(By.XPATH, "..")
            for link in parent.find_elements(By.TAG_NAME, "a"):
                if link.is_displayed():
                    link.click()
                    return
    except Exception:
        pass

def solve_captcha_with_ai(driver, max_retries=5):
    handle_alerts(driver)
    if not is_captcha_present(driver):
        return True
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[*] AI giải CAPTCHA (lần {attempt}/{max_retries})...")
            handle_alerts(driver)
            captcha_img = None
            for _ in range(10):
                imgs = driver.find_elements(By.CSS_SELECTOR,
                    "img[src*='php'], img[src*='captcha']")
                for img in imgs:
                    src = img.get_attribute("src") or ""
                    if img.is_displayed() and src and "data:" not in src:
                        captcha_img = img
                        break
                if captcha_img:
                    break
                time.sleep(0.5)
            if not captcha_img:
                print("[!] Không tìm thấy ảnh CAPTCHA.")
                break
            time.sleep(1)
            img_path = "temp_captcha.png"
            captcha_img.screenshot(img_path)
            print("[*] Đang gửi ảnh CAPTCHA cho AI nhận diện...")
            raw_result = ask_text_to_openrouter(img_path)
            text_result = re.sub(r'[^a-zA-Z0-9]', '', raw_result.strip())
            print(f"[+] AI nhận diện được: '{text_result}'")
            invalid_keywords = ['loading','captcha','incorrect','error','invalid','reload']
            if not text_result or len(text_result) < 3 or text_result.lower() in invalid_keywords:
                print(f"[-] Kết quả không hợp lệ ('{text_result}'). Đổi CAPTCHA mới...")
                _click_captcha_refresh(driver)
                time.sleep(1.5)
                continue
            captcha_input = driver.find_element(
                By.CSS_SELECTOR, "input.captcha-login-input, input[name='captchalogin']")
            captcha_input.clear()
            captcha_input.send_keys(text_result)
            captcha_input.send_keys(Keys.RETURN)
            time.sleep(2.5)
            if not is_captcha_present(driver):
                print("[+] CAPTCHA đã được giải thành công bằng AI!")
                send_telegram_notification("🧩 *AI đã giải xong CAPTCHA Zefoy!*")
                return True
            else:
                print("[-] CAPTCHA vẫn còn, thử lại...")
                _click_captcha_refresh(driver)
                time.sleep(1)
        except Exception as e:
            print(f"[!] Lỗi lần {attempt}: {e}")
            _click_captcha_refresh(driver)
            time.sleep(1)
    print("[!] AI không giải được CAPTCHA. Bỏ qua và tiếp tục...")
    time.sleep(30)
    return False

def run_bot(video_url: str, service: dict):
    service_name = service["name"]
    service_css  = service["css"]

    print(f"\n{'='*50}")
    print(f"  ZEFOY HEADLESS BOT  |  Dịch vụ: {service_name}")
    print(f"  URL: {video_url}")
    print(f"{'='*50}\n")

    send_telegram_notification(f"🎬 *Bắt đầu chạy Zefoy Bot*\n🔹 Dịch vụ: `{service_name}`\n🔗 Link: {video_url}")

    proxy = get_working_proxy(max_checks=15)
    driver = create_driver(proxy=proxy)
    try:
        print("[+] Đang mở trang Zefoy.com...")
        driver.get("https://zefoy.com/")
        time.sleep(4)
        handle_alerts(driver)

        print("[*] Đang kiểm tra CAPTCHA...")
        if is_captcha_present(driver):
            solve_captcha_with_ai(driver)
        else:
            time.sleep(3)
            if is_captcha_present(driver):
                solve_captcha_with_ai(driver)

        print(f"[*] Đang chọn dịch vụ '{service_name}'...")
        select_retries = 0
        max_select_retries = 15
        while True:
            select_retries += 1
            handle_alerts(driver)
            if is_captcha_present(driver):
                solve_captcha_with_ai(driver)
                continue
            inputs = driver.find_elements(By.TAG_NAME, "input")
            visible_input = None
            for inp in inputs:
                if inp.is_displayed():
                    ph   = (inp.get_attribute("placeholder") or "").lower()
                    name = (inp.get_attribute("name") or "").lower()
                    if "enter the word" in ph or "captchalogin" in name:
                        continue
                    visible_input = inp
                    break
            if visible_input:
                print(f"[+] Đã mở phần '{service_name}'! Nhập URL...")
                ensure_input_filled(driver, video_url)
                break
            else:
                success_click = select_service(driver, service_css, service_name)
                if not success_click and select_retries >= max_select_retries:
                    err_msg = f"⚠️ *[Zefoy Alert]* Dịch vụ `{service_name}` hiện đang *BỊ KHÓA / BẢO TRÌ* trên Zefoy.com!\n🔗 Link: {video_url}"
                    print(f"[!] {err_msg}")
                    send_telegram_notification(err_msg)
                    return

            time.sleep(2)

        print("[+] Bắt đầu vòng lặp tự động...")

        cycle = 0
        total_submits = 0
        while True:
            cycle += 1
            try:
                handle_alerts(driver)
                time.sleep(2)

                if is_captcha_present(driver):
                    solve_captcha_with_ai(driver)
                    continue

                ensure_input_filled(driver, video_url)

                buttons = driver.find_elements(By.TAG_NAME, "button")
                search_btn = None
                submit_btn = None
                for b in buttons:
                    if not b.is_displayed():
                        continue
                    txt = b.text.strip()
                    if "Search" in txt and b.is_enabled():
                        search_btn = b
                    elif "btn-dark" in (b.get_attribute("class") or "") or \
                         (re.search(r'^\d[\d,.]*$', txt) and "Search" not in txt):
                        submit_btn = b

                wait_sec = check_remaining_time(driver)
                if wait_sec > 0:
                    handle_timer_cooldown(wait_sec, service_name=service_name, send_telegram=True)
                elif submit_btn:
                    count_text = submit_btn.text.strip()
                    total_submits += 1
                    msg_submit = f"🎉 *[Zefoy Buff Thành Công!]*\n🔹 Dịch vụ: `{service_name}`\n🔢 Kết quả: *{count_text}*\n📊 Lượt buff thứ: *#{total_submits}*\n🔗 Link: {video_url}"
                    print(f"[Cycle {cycle}] {msg_submit}")
                    send_telegram_notification(msg_submit)
                    submit_btn.click()
                    time.sleep(5)
                elif search_btn:
                    ensure_input_filled(driver, video_url)
                    print(f"[Cycle {cycle}] Click Search...")
                    search_btn.click()
                    time.sleep(3)
                else:
                    time.sleep(5)

            except KeyboardInterrupt:
                print("\n[!] Dừng bot.")
                break
            except Exception as e:
                print(f"[Cycle {cycle}] Lỗi: {e}")
                time.sleep(5)
    finally:
        send_telegram_notification(f"🛑 *Zefoy Bot đã kết thúc tác vụ.*\n🔹 Dịch vụ: `{service_name}`\n🔗 Link: {video_url}")
        driver.quit()
        print("[+] Đã đóng browser.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zefoy Headless Bot")
    parser.add_argument("--service", default=os.getenv("ZEFOY_SERVICE", "4"),
                        help="Số dịch vụ (1-8). Mặc định: 4 (Views)")
    parser.add_argument("--url", default=os.getenv("ZEFOY_URL", ""),
                        help="TikTok Video URL")
    parser.add_argument("--duration", default=os.getenv("BOT_DURATION", "60"),
                        help="Thời gian chạy (phút)")
    args, unknown = parser.parse_known_args()

    if args.service not in SERVICES:
        print(f"[!] Dịch vụ không hợp lệ: {args.service}. Chọn 1-8.")
        sys.exit(1)

    if not args.url:
        print("[!] Thiếu TikTok URL!")
        sys.exit(1)

    run_bot(video_url=args.url, service=SERVICES[args.service])
