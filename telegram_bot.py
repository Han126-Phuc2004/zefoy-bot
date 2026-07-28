"""
telegram_bot.py  –  Điều khiển Zefoy Bot chạy trên GitHub Actions hoặc Local qua Telegram
"""

import os
import sys
import html
import re
import time
import requests
import telebot
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "Han126-Phuc2004/zefoy-bot").strip()
GITHUB_PAT = os.getenv("GITHUB_PAT", os.getenv("GH_PAT", "")).strip()

bot = telebot.TeleBot(TELEGRAM_TOKEN if TELEGRAM_TOKEN else "DUMMY_TOKEN")

SERVICES = {
    "1": "Followers",
    "2": "Hearts",
    "3": "Comments Hearts",
    "4": "Views",
    "5": "Shares",
    "6": "Favorites",
    "7": "Live Stream",
    "8": "Repost"
}

SERVICE_COMMAND_MAP = {
    '/follower': '1', '/followers': '1', '/sub': '1', '/subs': '1',
    '/heart': '2', '/hearts': '2', '/like': '2', '/likes': '2',
    '/cheart': '3', '/chearts': '3', '/comment': '3', '/comments': '3',
    '/view': '4', '/views': '4',
    '/share': '5', '/shares': '5',
    '/favorite': '6', '/favorites': '6', '/fav': '6', '/favs': '6',
    '/live': '7', '/livestream': '7',
    '/repost': '8'
}

def extract_tiktok_url(text: str) -> str:
    """Trích xuất URL TikTok chính xác từ chuỗi nhập vào."""
    if not text:
        return ""
    match = re.search(r'https?://[^\s]+', text)
    if match:
        url = match.group(0)
        return url.rstrip('.,;!>')
    return ""

def safe_send_message(chat_id, text, parse_mode="HTML", reply_to_message_id=None):
    """Gửi tin nhắn Telegram an toàn, tự động fallback về plain text nếu bị lỗi format."""
    try:
        return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_to_message_id=reply_to_message_id)
    except Exception as e:
        print(f"[!] Send message with parse_mode='{parse_mode}' failed: {e}. Retrying as plain text...")
        try:
            clean_text = re.sub(r'<[^>]+>', '', text)
            return bot.send_message(chat_id, clean_text, parse_mode=None, reply_to_message_id=reply_to_message_id)
        except Exception as e2:
            print(f"[❌] Failed to send telegram message: {e2}")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    print(f"[+] Handling /start or /help from chat_id={message.chat.id}")
    help_text = """
🤖 <b>ZEFOY TELEGRAM BOT CONTROLLER</b>

Bạn có thể gửi <b>trực tiếp Link TikTok</b> vào đây hoặc sử dụng các lệnh:

🔹 <code>/view &lt;link&gt;</code> hoặc <code>/views &lt;link&gt;</code> - Tăng Views
🔹 <code>/heart &lt;link&gt;</code> hoặc <code>/hearts &lt;link&gt;</code> - Tăng Hearts
🔹 <code>/follower &lt;link&gt;</code> hoặc <code>/followers &lt;link&gt;</code> - Tăng Followers
🔹 <code>/share &lt;link&gt;</code> hoặc <code>/shares &lt;link&gt;</code> - Tăng Shares
🔹 <code>/favorite &lt;link&gt;</code> hoặc <code>/favorites &lt;link&gt;</code> - Tăng Favorites
🔹 <code>/run &lt;1-8&gt; &lt;link&gt;</code> - Tùy chọn dịch vụ (1:Followers, 2:Hearts, 3:CHearts, 4:Views, 5:Shares, 6:Favorites, 7:Live, 8:Repost)

🛑 <code>/stop</code> - HỦY & DỪNG tất cả các bot đang cày view trên GitHub!
    """
    safe_send_message(message.chat.id, help_text, reply_to_message_id=message.message_id)

@bot.message_handler(commands=['stop', 'cancel'])
def cancel_github_actions(message):
    print(f"[+] Handling /stop or /cancel from chat_id={message.chat.id}")
    if not GITHUB_PAT:
        safe_send_message(message.chat.id, "❌ <b>Lỗi:</b> Chưa cấu hình <code>GITHUB_PAT</code> trong <code>.env</code>!", reply_to_message_id=message.message_id)
        return

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?per_page=100"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            runs = res.json().get("workflow_runs", [])
            active_runs = [r for r in runs if r.get("status") in ["in_progress", "queued", "waiting", "requested"]]
            
            if not active_runs:
                safe_send_message(message.chat.id, "ℹ️ <b>Hiện không có bot nào đang chạy trên GitHub.</b>", reply_to_message_id=message.message_id)
                return
            
            canceled_count = 0
            for run in active_runs:
                run_id = run.get("id")
                cancel_url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs/{run_id}/cancel"
                cancel_res = requests.post(cancel_url, headers=headers, timeout=10)
                if cancel_res.status_code in [202, 200]:
                    canceled_count += 1
            
            safe_send_message(message.chat.id, f"🛑 <b>Đã gửi lệnh dừng thành công cho {canceled_count} bot đang chạy trên GitHub!</b>", reply_to_message_id=message.message_id)
        else:
            safe_send_message(message.chat.id, f"❌ <b>Lỗi kiểm tra GitHub API ({res.status_code})</b>\n<code>{html.escape(res.text[:200])}</code>", reply_to_message_id=message.message_id)
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ <b>Lỗi:</b> {html.escape(str(e))}", reply_to_message_id=message.message_id)

def trigger_github_action(chat_id, service_id, tiktok_url, reply_to_msg_id=None):
    if not GITHUB_PAT:
        safe_send_message(chat_id, "❌ <b>Lỗi:</b> Chưa cấu hình <code>GITHUB_PAT</code> trong <code>.env</code>!", reply_to_message_id=reply_to_msg_id)
        return

    url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    payload = {
        "event_type": "telegram_trigger",
        "client_payload": {
            "service": str(service_id),
            "tiktok_url": tiktok_url,
            "chat_id": str(chat_id)
        }
    }
    
    service_name = SERVICES.get(str(service_id), "Views")
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code in [204, 200, 201]:
            safe_send_message(
                chat_id, 
                f"🚀 <b>Đã khởi tạo tác vụ trên GitHub Actions!</b>\n\n"
                f"🔹 <b>Dịch vụ:</b> <code>{html.escape(service_name)}</code>\n"
                f"🔗 <b>Link:</b> {html.escape(tiktok_url)}\n"
                f"⏱ Máy chủ Ubuntu của GitHub đang khởi động bot... Muốn dừng hãy nhắn <code>/stop</code>!",
                reply_to_message_id=reply_to_msg_id
            )
        else:
            safe_send_message(
                chat_id, 
                f"❌ <b>Lỗi kết nối GitHub API (Mã {res.status_code}):</b>\n"
                f"<code>{html.escape(res.text[:200])}</code>\n"
                f"Kiểm tra lại GITHUB_PAT token hoặc GITHUB_REPO.", 
                reply_to_message_id=reply_to_msg_id
            )
    except Exception as e:
        safe_send_message(chat_id, f"❌ <b>Lỗi:</b> {html.escape(str(e))}", reply_to_message_id=reply_to_msg_id)

@bot.message_handler(commands=[
    'views', 'view', 'hearts', 'heart', 'followers', 'follower', 
    'shares', 'share', 'favorites', 'favorite', 'fav', 'favs', 
    'chearts', 'cheart', 'comment', 'comments', 'live', 'livestream', 'repost', 'run'
])
def handle_service(message):
    if not message or not message.text:
        return
    
    text = message.text.strip()
    print(f"[+] Received command: '{text}' from chat_id={message.chat.id}")
    parts = text.split(maxsplit=2)
    cmd = parts[0].lower().split('@')[0]
    
    if cmd == '/run':
        if len(parts) < 3:
            safe_send_message(message.chat.id, "⚠️ Cú pháp: <code>/run &lt;số 1-8&gt; &lt;link_tiktok&gt;</code>", reply_to_message_id=message.message_id)
            return
        service_id = parts[1]
        raw_url = parts[2]
    else:
        service_id = SERVICE_COMMAND_MAP.get(cmd, '4')
        raw_url = text[len(parts[0]):].strip() if len(parts) > 1 else ""

    tiktok_url = extract_tiktok_url(raw_url)
    if not tiktok_url:
        safe_send_message(
            message.chat.id, 
            f"⚠️ <b>Vui lòng điền link TikTok hợp lệ!</b>\n\nVí dụ: <code>{html.escape(cmd)} https://vt.tiktok.com/ZSxxxxxx/</code>", 
            reply_to_message_id=message.message_id
        )
        return

    trigger_github_action(message.chat.id, service_id, tiktok_url, reply_to_msg_id=message.message_id)

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    if not message or not message.text:
        return
    text = message.text.strip()
    print(f"[+] Handling fallback message: '{text}' from chat_id={message.chat.id}")
    
    if text.startswith('/'):
        cmd_name = text.split()[0].lower().split('@')[0]
        if cmd_name in ['/start', '/help', '/trogiup']:
            send_welcome(message)
            return
        elif cmd_name in ['/stop', '/cancel', '/dung']:
            cancel_github_actions(message)
            return

    tiktok_url = extract_tiktok_url(text)
    if tiktok_url:
        trigger_github_action(message.chat.id, "4", tiktok_url, reply_to_msg_id=message.message_id)
    else:
        safe_send_message(
            message.chat.id, 
            "🤖 <b>ZEFOY TELEGRAM BOT CONTROLLER</b>\n\n"
            "Gửi <b>link TikTok</b> trực tiếp vào đây để tự động tăng View,\n"
            "hoặc gõ <code>/help</code> để xem danh sách hướng dẫn lệnh!", 
            reply_to_message_id=message.message_id
        )

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK - Zefoy Telegram Bot is running")

def start_health_check_server():
    port = int(os.getenv("PORT", 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"[+] Health check server listening on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"[!] Warning: Health check server stopped: {e}")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "DUMMY_TOKEN":
        print("[❌] ERROR: TELEGRAM_BOT_TOKEN is missing in .env file!")
        sys.exit(1)

    print("[+] Starting HTTP Health Check thread...")
    threading.Thread(target=start_health_check_server, daemon=True).start()
    
    try:
        bot.remove_webhook(drop_pending_updates=True)
        print("[+] Webhook cleared & pending updates dropped.")
    except Exception as e:
        print(f"[!] remove_webhook notice: {e}")

    print("[+] Starting Telegram Bot Listener (Infinity Polling)...")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
        except Exception as e:
            print(f"[!] Exception during polling: {e}. Retrying in 5 seconds...")
            time.sleep(5)
