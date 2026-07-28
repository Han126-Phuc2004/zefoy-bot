import os
import re
import time
import base64
from dotenv import load_dotenv
from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

load_dotenv()

# ─── AI: OpenRouter ────────────────────────────────────────────────────────────

def image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def ask_captcha_ai(image_path, model="nvidia/nemotron-nano-12b-v2-vl:free"):
    """Gửi ảnh CAPTCHA cho OpenRouter, trả về text nhận diện được."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise Exception("OPENROUTER_API_KEY chưa được cấu hình trong .env")
    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    b64 = image_to_base64(image_path)
    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": (
                    "This is a CAPTCHA image. Read the exact characters shown. "
                    "Return ONLY the alphanumeric characters, no spaces, no explanation."
                )}
            ]
        }],
        max_tokens=30
    )
    return response.choices[0].message.content.strip()

# ─── Selenium Helpers ──────────────────────────────────────────────────────────

def handle_alerts(driver):
    """Tự động đóng alert dialog nếu có."""
    try:
        alert = driver.switch_to.alert
        print(f"[!] Auto-close Alert: {alert.text[:60]}")
        alert.accept()
        time.sleep(0.5)
    except Exception:
        pass

def is_captcha_present(driver):
    """Kiểm tra CAPTCHA có đang hiển thị không."""
    handle_alerts(driver)
    try:
        for inp in driver.find_elements(By.CSS_SELECTOR,
                "input.captcha-login-input, input[name='captchalogin']"):
            if inp.is_displayed():
                return True
        for inp in driver.find_elements(By.TAG_NAME, "input"):
            if inp.is_displayed():
                ph = (inp.get_attribute("placeholder") or "").lower()
                if "enter the word" in ph or "enter the text" in ph:
                    return True
        for img in driver.find_elements(By.TAG_NAME, "img"):
            if img.is_displayed():
                src = (img.get_attribute("src") or "").lower()
                if "captcha" in src or ("php" in src and "?" in src):
                    return True
    except Exception:
        pass
    return False

def _click_captcha_refresh(driver):
    """Bấm nút refresh để lấy CAPTCHA mới."""
    try:
        for sel in [".captcha-refresh", "a[onclick*='captcha']",
                    "a[href*='captcha']", "i[class*='refresh']", "svg[class*='refresh']"]:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    el.click()
                    return
        # Fallback: link gần ảnh CAPTCHA
        for img in driver.find_elements(By.CSS_SELECTOR,
                "img[src*='php'], img[src*='captcha']"):
            parent = img.find_element(By.XPATH, "..")
            for link in parent.find_elements(By.TAG_NAME, "a"):
                if link.is_displayed():
                    link.click()
                    return
    except Exception:
        pass

def solve_captcha_with_ai(driver, max_retries=6):
    """
    Tự động giải CAPTCHA bằng AI (OpenRouter).
    Có retry loop, chờ ảnh load, refresh sau khi sai.
    Fallback về thủ công nếu AI thất bại.
    """
    handle_alerts(driver)
    if not is_captcha_present(driver):
        return True

    INVALID = {'loading', 'captcha', 'incorrect', 'error', 'invalid', 'reload',
               'please', 'wait', 'verify', 'check', 'code', 'wrong'}

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[*] AI giải CAPTCHA (lần {attempt}/{max_retries})...")
            handle_alerts(driver)

            # 1. Chờ ảnh CAPTCHA load xong
            captcha_img = None
            for _ in range(12):
                for img in driver.find_elements(By.CSS_SELECTOR,
                        "img[src*='php'], img[src*='captcha']"):
                    src = img.get_attribute("src") or ""
                    if img.is_displayed() and src and "data:" not in src and len(src) > 20:
                        captcha_img = img
                        break
                if captcha_img:
                    break
                time.sleep(0.5)

            if not captcha_img:
                print("[!] Không tìm thấy ảnh CAPTCHA.")
                break

            time.sleep(1)  # Chờ render đầy đủ

            # 2. Chụp ảnh
            img_path = "temp_captcha.png"
            captcha_img.screenshot(img_path)

            # 3. Gửi cho AI
            print("[*] Đang gửi ảnh cho AI nhận diện...")
            raw = ask_captcha_ai(img_path)
            text = re.sub(r"[^a-zA-Z0-9]", "", raw).strip()
            print(f"[+] AI nhận diện: '{text}'")

            # Bỏ qua kết quả không hợp lệ
            if not text or len(text) < 3 or text.lower() in INVALID or \
               any(kw in text.lower() for kw in INVALID):
                print(f"[-] Kết quả không hợp lệ. Đổi CAPTCHA mới...")
                _click_captcha_refresh(driver)
                time.sleep(1.5)
                continue

            # 4. Tìm lại input và điền
            inputs = driver.find_elements(By.CSS_SELECTOR,
                "input.captcha-login-input, input[name='captchalogin']")
            captcha_input = next((i for i in inputs if i.is_displayed()), None)
            if not captcha_input:
                print("[-] Không tìm thấy ô nhập CAPTCHA.")
                continue

            captcha_input.clear()
            captcha_input.send_keys(text)
            captcha_input.send_keys(Keys.RETURN)
            time.sleep(2.5)

            # 5. Kiểm tra kết quả
            if not is_captcha_present(driver):
                print("[+] CAPTCHA giải thành công!")
                return True
            else:
                print("[-] Sai CAPTCHA, thử lại...")
                _click_captcha_refresh(driver)
                time.sleep(1)

        except Exception as e:
            print(f"[!] Lỗi lần {attempt}: {e}")
            _click_captcha_refresh(driver)
            time.sleep(1)

    # Fallback thủ công
    print("[!] AI thất bại. Vui lòng nhập CAPTCHA thủ công trên trình duyệt...")
    while is_captcha_present(driver):
        handle_alerts(driver)
        time.sleep(1)
    print("[+] CAPTCHA đã được giải!")
    return True

# ─── Zefoy Bot ─────────────────────────────────────────────────────────────────

def select_views_service(driver):
    """Bấm nút Views trên Zefoy."""
    handle_alerts(driver)
    try:
        btn = driver.find_element(By.CSS_SELECTOR, ".t-views-button")
        if btn.is_displayed() and btn.is_enabled():
            print("[+] Bấm nút Views...")
            btn.click()
            time.sleep(2)
            return True
    except Exception:
        pass
    try:
        for b in driver.find_elements(By.TAG_NAME, "button"):
            if b.is_displayed() and b.is_enabled():
                if "t-views-button" in (b.get_attribute("class") or ""):
                    b.click()
                    time.sleep(2)
                    return True
    except Exception:
        pass
    return False

def ensure_input_filled(driver, video_url):
    """Đảm bảo ô nhập URL TikTok đã được điền."""
    handle_alerts(driver)
    if not video_url or is_captcha_present(driver):
        return
    try:
        for inp in driver.find_elements(By.TAG_NAME, "input"):
            if inp.is_displayed():
                ph = (inp.get_attribute("placeholder") or "").lower()
                name = (inp.get_attribute("name") or "").lower()
                cls = (inp.get_attribute("class") or "").lower()
                if "enter the word" in ph or "captchalogin" in name or "captcha-login-input" in cls:
                    continue
                val = inp.get_attribute("value") or ""
                if not val.strip():
                    inp.clear()
                    inp.send_keys(video_url)
                    print("[+] Đã điền URL vào ô nhập.")
                break
    except Exception:
        pass

def check_remaining_time(driver):
    """Kiểm tra chính xác số giây cần chờ (cooldown) trên trang Zefoy."""
    handle_alerts(driver)
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text

        m1 = re.search(r"Please wait\s*(\d+)\s*minute\(s\)\s*(\d+)\s*second\(s\)", page_text, re.IGNORECASE)
        if m1:
            return int(m1.group(1)) * 60 + int(m1.group(2))

        m2 = re.search(r"Please wait\s*(\d+)\s*second\(s\)", page_text, re.IGNORECASE)
        if m2:
            return int(m2.group(1))

        m3 = re.search(r"Please wait\s*(\d+)\s*minute\(s\)", page_text, re.IGNORECASE)
        if m3:
            return int(m3.group(1)) * 60

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

def handle_timer_cooldown(seconds):
    """Hiển thị đồng hồ đếm ngược từng giây trong console."""
    mins, secs = divmod(seconds, 60)
    time_fmt = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
    print(f"\n⏱ [Timer Checker] Phát hiện thời gian chờ: {time_fmt} ({seconds} giây)")
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

def run_zefoy_bot(video_url=""):
    """Bot chính: tự động tăng views TikTok trên Zefoy."""
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_experimental_option("detach", True)
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2
    })

    driver = webdriver.Chrome(options=options)

    print("\n[+] Đang mở Zefoy.com...")
    driver.get("https://zefoy.com/")
    time.sleep(3)
    handle_alerts(driver)

    # Giải CAPTCHA lần đầu
    print("[*] Kiểm tra CAPTCHA...")
    if is_captcha_present(driver):
        solve_captcha_with_ai(driver)
    else:
        time.sleep(3)
        if is_captcha_present(driver):
            solve_captcha_with_ai(driver)

    # Chọn dịch vụ Views
    print("[*] Đang tìm và chọn dịch vụ Views...")
    while True:
        try:
            handle_alerts(driver)
            if is_captcha_present(driver):
                solve_captcha_with_ai(driver)
                continue

            visible_input = None
            for inp in driver.find_elements(By.TAG_NAME, "input"):
                if inp.is_displayed():
                    ph = (inp.get_attribute("placeholder") or "").lower()
                    name = (inp.get_attribute("name") or "").lower()
                    if "enter the word" in ph or "captchalogin" in name:
                        continue
                    visible_input = inp
                    break

            if visible_input:
                print("[+] Đã vào phần Views! Nhập URL TikTok...")
                ensure_input_filled(driver, video_url)
                break
            else:
                select_views_service(driver)
        except Exception:
            pass
        time.sleep(2)

    print("[+] Bot đang chạy. Tự động Search & Submit views...\n")

    # Vòng lặp chính
    while True:
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
                     (re.search(r"^\d[\d,.]*$", txt) and "Search" not in txt):
                    submit_btn = b

            wait_sec = check_remaining_time(driver)
            if wait_sec > 0:
                handle_timer_cooldown(wait_sec)
            elif submit_btn:
                count = submit_btn.text.strip()
                print(f"[+] Submit! Views hiện tại: {count}")
                submit_btn.click()
                time.sleep(5)
            elif search_btn:
                ensure_input_filled(driver, video_url)
                print("\n[+] Click Search...")
                search_btn.click()
                time.sleep(3)

        except KeyboardInterrupt:
            print("\n[!] Đã dừng bot.")
            break
        except Exception as e:
            print(f"\n[!] {e}")
            time.sleep(3)


if __name__ == "__main__":
    url = input("Enter TikTok Video URL (or press Enter to paste in browser): ").strip()
    run_zefoy_bot(url)
