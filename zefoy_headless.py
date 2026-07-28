"""
zefoy_headless.py  –  Phiên bản deploy trên Server / GitHub Actions / VPS (không cần màn hình)
Chạy: python zefoy_headless.py --service 4 --url "https://vt.tiktok.com/xxx"
"""

import os
import sys
import time
import re
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from ai_utils import ask_text_to_openrouter

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

def create_driver():
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

    driver = create_driver()
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
        while True:
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
                select_service(driver, service_css, service_name)
            time.sleep(2)

        print("[+] Bắt đầu vòng lặp tự động...")

        cycle = 0
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

                page_text = driver.find_element(By.TAG_NAME, "body").text

                if submit_btn:
                    count_text = submit_btn.text.strip()
                    print(f"[Cycle {cycle}] Submit! Số lượng: {count_text}")
                    submit_btn.click()
                    time.sleep(5)
                elif "Please wait" in page_text:
                    match = re.search(r"Please wait (\d+) minute\(s\) (\d+) second\(s\)", page_text)
                    if match:
                        mins, secs = match.group(1), match.group(2)
                        wait_sec = int(mins)*60 + int(secs)
                        print(f"[Cycle {cycle}] Chờ: {mins}m {secs}s (sleep {wait_sec}s)")
                        time.sleep(min(wait_sec, 300))
                elif search_btn:
                    ensure_input_filled(driver, video_url)
                    print(f"[Cycle {cycle}] Click Search...")
                    search_btn.click()
                    time.sleep(3)
                else:
                    print(f"[Cycle {cycle}] Đợi 10s...")
                    time.sleep(10)

            except KeyboardInterrupt:
                print("\n[!] Dừng bot.")
                break
            except Exception as e:
                print(f"[Cycle {cycle}] Lỗi: {e}")
                time.sleep(5)
    finally:
        driver.quit()
        print("[+] Đã đóng browser.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zefoy Headless Bot")
    parser.add_argument("--service", default=os.getenv("ZEFOY_SERVICE", "4"),
                        help="Số dịch vụ (1-8). Mặc định: 4 (Views)")
    parser.add_argument("--url", default=os.getenv("ZEFOY_URL", ""),
                        help="TikTok Video URL")
    args = parser.parse_args()

    if args.service not in SERVICES:
        print(f"[!] Dịch vụ không hợp lệ: {args.service}. Chọn 1-8.")
        sys.exit(1)

    if not args.url:
        print("[!] Thiếu TikTok URL!")
        sys.exit(1)

    run_bot(video_url=args.url, service=SERVICES[args.service])
