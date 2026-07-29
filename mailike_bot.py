# -*- coding: utf-8 -*-
"""
mailike_bot.py — Tự động thả tim TikTok miễn phí qua mailike.xyz
─────────────────────────────────────────────────────────────────
API đã reverse-engineer:
  Login : POST /checklogin.php  (username, password, type=login)
  Submit: POST /dichvumienphi.php (id, soluong, type=tt_tymfree)
  Balance: GET /nap-popup.php
─────────────────────────────────────────────────────────────────
"""

import requests
import time
import re
import os
import json
import sys
from datetime import datetime

# Fix Windows console encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ═══════════════════════════════════════════
#  CẤU HÌNH
# ═══════════════════════════════════════════

MAILIKE_USERNAME = os.environ.get("MAILIKE_USERNAME", "")
MAILIKE_PASSWORD = os.environ.get("MAILIKE_PASSWORD", "")

# TikTok video URL muon tha tim
TIKTOK_URL = os.environ.get(
    "TIKTOK_URL",
    "https://www.tiktok.com/@homec.pubg/video/7667474858036563208"
)

# Số tim mỗi lần (free: min 10, max 20)
QUANTITY = 10

# Loại dịch vụ
SERVICE_TYPE = "tt_tymfree"  # free TikTok like

# Cooldown tối thiểu giữa 2 lần gửi (giây)
COOLDOWN_MIN = 185  # 3 phút + 5s buffer

# Vòng lặp tối đa (None = chạy mãi)
MAX_LOOPS = None

# ═══════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════

BASE_URL = "https://mailike.xyz"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Origin": BASE_URL,
    "X-Requested-With": "XMLHttpRequest",
}


# ═══════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {
        "INFO": "[*]",
        "OK":   "[+]",
        "ERR":  "[-]",
        "WAIT": "[~]",
        "WARN": "[!]",
        "HEAD": "[=]",
    }
    icon = icons.get(level, "[ ]")
    print(f"[{ts}] {icon} {msg}", flush=True)


# ═══════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════

def login(username: str, password: str) -> requests.Session:
    """
    Đăng nhập vào mailike.xyz, trả về session đã xác thực.
    Endpoint: POST /checklogin.php
    Payload : username, password, type=login
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    log(f"Đang đăng nhập với tài khoản: {username}", "INFO")

    payload = {
        "username": username,
        "password": password,
        "type": "login",
    }
    headers_login = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"{BASE_URL}/login",
    }

    try:
        resp = session.post(
            f"{BASE_URL}/checklogin.php",
            data=payload,
            headers=headers_login,
            timeout=30,
            allow_redirects=True,
        )

        raw = resp.text.strip()
        log(f"Login response [{resp.status_code}]: {raw[:200]}", "INFO")

        # Server tra JSON: {"status": true/false}
        try:
            data = json.loads(raw)
            if data.get("status") is True or data.get("success") is True:
                log("Dang nhap thanh cong (JSON ok)!", "OK")
                _print_cookies(session)
                return session
            else:
                log(f"Dang nhap that bai: {data}", "ERR")
                return None
        except Exception:
            pass

        # Fallback: kiem tra bang session cookie va goi /info
        session_cookies = dict(session.cookies)
        log(f"Cookies: {list(session_cookies.keys())}", "INFO")

        if "PHPSESSID" not in session_cookies and "laravel_session" not in session_cookies:
            log("Khong co session cookie — that bai.", "ERR")
            return None

        # Xac nhan bang cach goi /info
        try:
            info_resp = session.get(f"{BASE_URL}/info", timeout=10, allow_redirects=False)
            # Neu redirect -> chua dang nhap
            if info_resp.status_code in (301, 302):
                loc = info_resp.headers.get("Location", "")
                if "login" in loc:
                    log("Session khong hop le, bi redirect ve login.", "ERR")
                    return None
        except Exception:
            pass

        log("Dang nhap thanh cong!", "OK")
        _print_cookies(session)
        return session

    except requests.RequestException as e:
        log(f"Login request failed: {e}", "ERR")
        return None


def _print_cookies(session: requests.Session):
    """In cookies hiện tại của session."""
    cookies = dict(session.cookies)
    log(f"Session cookies ({len(cookies)} items):", "INFO")
    for k, v in cookies.items():
        # Ẩn bớt giá trị dài
        display = v[:40] + "..." if len(v) > 40 else v
        print(f"    {k} = {display}")


# ═══════════════════════════════════════════
#  CORE API
# ═══════════════════════════════════════════

def check_balance(session: requests.Session) -> float:
    """Kiểm tra số dư ví."""
    try:
        resp = session.get(
            f"{BASE_URL}/nap-popup.php",
            headers={**HEADERS, "Referer": f"{BASE_URL}/"},
            timeout=10
        )
        data = json.loads(resp.text)
        balance = data.get("balance", 0)
        log(f"Số dư ví: {balance:,}đ", "INFO")
        return float(balance)
    except Exception as e:
        log(f"Không lấy được balance: {e}", "WARN")
        return 0.0


def send_free_like(
    session: requests.Session,
    tiktok_url: str,
    quantity: int = 10,
    service_type: str = "tt_tymfree"
) -> dict:
    """
    Gửi request thả tim miễn phí.
    POST /dichvumienphi.php
    Body: id={url}&soluong={qty}&type={service_type}
    """
    payload = {
        "id": tiktok_url,
        "soluong": str(quantity),
        "type": service_type,
    }
    headers_post = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"{BASE_URL}/tang-tym-video-tiktok-mien-phi",
    }

    log(f"POST /dichvumienphi.php → type={service_type}, soluong={quantity}")
    log(f"URL: {tiktok_url[:70]}")

    try:
        resp = session.post(
            f"{BASE_URL}/dichvumienphi.php",
            data=payload,
            headers=headers_post,
            timeout=30,
        )
        raw = resp.text.strip()
        log(f"Raw response: {raw[:400]}", "INFO")

        return _parse_response(raw, resp.status_code)

    except requests.RequestException as e:
        log(f"Request error: {e}", "ERR")
        return {"success": False, "message": str(e), "raw": ""}


def _parse_response(raw: str, status_code: int) -> dict:
    """Parse phản hồi từ server (dạng JS script hoặc JSON)."""

    # Dạng: <script>showSuccessNotification("...");</script>
    ok_match = re.search(
        r'showSuccessNotification\(["\']([^"\']+)["\']',
        raw, re.IGNORECASE
    )
    if ok_match:
        msg = ok_match.group(1)
        log(f"Thanh cong: {msg}", "OK")
        return {"success": True, "message": msg, "raw": raw}

    # Dạng: <script>showErrorNotification("...");</script>
    err_match = re.search(
        r'showErrorNotification\(["\']([^"\']+)["\']',
        raw, re.IGNORECASE
    )
    if err_match:
        msg = err_match.group(1)
        log(f"Server: {msg}", "WARN")
        return {"success": False, "message": msg, "raw": raw}

    # JSON thuần
    try:
        data = json.loads(raw)
        success = data.get("status") == "success" or data.get("success") is True
        msg = data.get("message", str(data))
        log(f"JSON: {msg}", "OK" if success else "WARN")
        return {"success": success, "message": msg, "data": data, "raw": raw}
    except Exception:
        pass

    # Không rõ định dạng
    log(f"Phản hồi không rõ [{status_code}]: {raw[:200]}", "WARN")
    return {"success": False, "message": "Unknown response", "raw": raw}


def _parse_cooldown(message: str) -> int:
    """Lấy số giây cooldown từ thông báo server."""
    # "Vui lòng chờ 3 phút nữa..."
    m = re.search(r'(\d+)\s*phút', message)
    if m:
        return int(m.group(1)) * 60 + 10

    # "Vui lòng chờ 45 giây nữa..."
    m = re.search(r'(\d+)\s*giây', message)
    if m:
        return int(m.group(1)) + 5

    return COOLDOWN_MIN


# ═══════════════════════════════════════════
#  COUNTDOWN HELPER
# ═══════════════════════════════════════════

def countdown(seconds: int):
    """Đếm ngược với hiển thị realtime."""
    start = time.time()
    while True:
        elapsed = time.time() - start
        remaining = max(0, seconds - elapsed)
        mins, secs = divmod(int(remaining), 60)
        print(f"\r    [~] Con {mins:02d}:{secs:02d}s...", end="", flush=True)
        if remaining <= 0:
            break
        time.sleep(1)
    print()  # newline


# ═══════════════════════════════════════════
#  MAIN BOT LOOP
# ═══════════════════════════════════════════

def run_bot():
    global MAILIKE_USERNAME, MAILIKE_PASSWORD

    log("=" * 55, "HEAD")
    log(" Mailike.xyz - TikTok Free Like Bot (Direct API)")
    log("=" * 55, "HEAD")
    log(f"Target: {TIKTOK_URL}")
    log(f"Service: {SERVICE_TYPE} | Quantity: {QUANTITY} likes/round")

    # ── Tu dong hoi credentials neu chua co ──
    if not MAILIKE_USERNAME:
        print()
        print("  Nhap thong tin dang nhap mailike.xyz:")
        MAILIKE_USERNAME = input("  Username/Email: ").strip()
        import getpass
        MAILIKE_PASSWORD = getpass.getpass("  Password: ").strip()
        print()

    # ── Dang nhap, lay session ──
    session = login(MAILIKE_USERNAME, MAILIKE_PASSWORD)
    if not session:
        log("Dang nhap that bai, dung.", "ERR")
        return

    # ── Balance ──
    check_balance(session)

    # ── Vòng lặp ──
    loop = 0
    total_ok = 0
    total_tim = 0

    while True:
        loop += 1
        if MAX_LOOPS and loop > MAX_LOOPS:
            log(f"Đã đạt {MAX_LOOPS} vòng, dừng.", "INFO")
            break

        log(f"--- Vong #{loop} ---", "INFO")
        result = send_free_like(session, TIKTOK_URL, QUANTITY, SERVICE_TYPE)

        if result["success"]:
            total_ok += 1
            total_tim += QUANTITY
            log(f"Tổng: {total_ok} lần | {total_tim} tim", "OK")
            wait = COOLDOWN_MIN

        else:
            msg = result.get("message", "")

            # Cooldown từ server
            if any(k in msg for k in ["phút", "giây", "chờ", "wait"]):
                wait = _parse_cooldown(msg)

            # Session hết hạn → re-login
            elif any(k in msg.lower() for k in ["đăng nhập", "login", "session"]):
                log("Session hết hạn, đang đăng nhập lại...", "WARN")
                session = login(MAILIKE_USERNAME, MAILIKE_PASSWORD)
                if not session:
                    log("Re-login thất bại, dừng.", "ERR")
                    break
                wait = 5

            # Hết lượt free trong ngày
            elif any(k in msg for k in ["ngày", "day", "freeInDay"]):
                log("Hết lượt free hôm nay. Chờ đến 00:00 reset.", "WARN")
                wait = 3700

            else:
                wait = COOLDOWN_MIN

        log(f"Chờ {wait}s trước lần tiếp...", "WAIT")
        countdown(wait)


# ═══════════════════════════════════════════
#  ENTRY
# ═══════════════════════════════════════════

if __name__ == "__main__":
    run_bot()
