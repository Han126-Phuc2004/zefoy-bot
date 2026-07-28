"""
telegram_bot.py  –  Điều khiển Zefoy Bot chạy trên GitHub Actions hoặc Local qua Telegram
"""

import os
import sys
import requests
import telebot
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

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = """
🤖 *ZEFOY TELEGRAM BOT CONTROLLER*

Gửi link TikTok trực tiếp hoặc chọn lệnh bên dưới:

🔹 `/views <link>` - Tự động tăng Views
🔹 `/hearts <link>` - Tự động tăng Hearts
🔹 `/followers <link>` - Tự động tăng Followers
🔹 `/shares <link>` - Tự động tăng Shares

🛑 `/stop` - HỦY DỪNG tất cả các bot đang cày view trên GitHub!
    """
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['stop', 'cancel'])
def cancel_github_actions(message):
    """Hủy và dừng tất cả các tiến trình đang chạy trên GitHub Actions."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?status=in_progress"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}" if GITHUB_PAT else "",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            runs = res.json().get("workflow_runs", [])
            if not runs:
                bot.reply_to(message, "ℹ️ *Hiện không có bot nào đang chạy trên GitHub.*", parse_mode="Markdown")
                return
            
            canceled_count = 0
            for run in runs:
                run_id = run.get("id")
                cancel_url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs/{run_id}/cancel"
                cancel_res = requests.post(cancel_url, headers=headers)
                if cancel_res.status_code in [202, 200]:
                    canceled_count += 1
            
            bot.reply_to(message, f"🛑 *Đã gửi lệnh dừng thành công cho {canceled_count} bot đang chạy trên GitHub!*", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❌ *Lỗi kiểm tra GitHub API ({res.status_code})*", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ *Lỗi:* {e}", parse_mode="Markdown")

def trigger_github_action(chat_id, service_id, tiktok_url):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}" if GITHUB_PAT else "",
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
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code in [204, 200, 201]:
            bot.send_message(
                chat_id, 
                f"🚀 *Đã khởi tạo tác vụ trên GitHub Actions!*\n\n🔹 Dịch vụ: `{service_name}`\n🔗 Link: {tiktok_url}\n⏱ Máy chủ Ubuntu của GitHub đang khởi động bot... Muốn dừng hãy nhắn `/stop`!", 
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                chat_id, 
                f"❌ *Lỗi kết nối GitHub API (Mã {res.status_code}):*\nKiểm tra lại GITHUB_PAT token.", 
                parse_mode="Markdown"
            )
    except Exception as e:
        bot.send_message(chat_id, f"❌ *Lỗi:* {e}", parse_mode="Markdown")

@bot.message_handler(commands=['views', 'hearts', 'followers', 'shares', 'favorites', 'run'])
def handle_service(message):
    text_parts = message.text.strip().split(maxsplit=2)
    cmd = text_parts[0].lower()
    
    service_map = {'/followers': '1', '/hearts': '2', '/views': '4', '/shares': '5', '/favorites': '6'}
    
    if cmd == '/run':
        if len(text_parts) < 3:
            bot.reply_to(message, "⚠️ Cú pháp: `/run <số 1-8> <link_tiktok>`", parse_mode="Markdown")
            return
        service_id = text_parts[1]
        tiktok_url = text_parts[2]
    else:
        if len(text_parts) < 2:
            bot.reply_to(message, f"⚠️ Vui lòng điền link TikTok!\nVí dụ: `{cmd} https://vt.tiktok.com/ZSxxxxxx/`", parse_mode="Markdown")
            return
        service_id = service_map.get(cmd, '4')
        tiktok_url = text_parts[1]

    trigger_github_action(message.chat.id, service_id, tiktok_url)

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    txt = message.text.strip()
    if "tiktok.com" in txt.lower() or "http" in txt.lower():
        trigger_github_action(message.chat.id, "4", txt)
    else:
        bot.reply_to(message, "🤖 Gửi link TikTok vào đây để tăng View, gõ `/stop` để dừng bot, hoặc gõ `/help` để xem hướng dẫn!")

if __name__ == "__main__":
    print("[+] Starting Telegram Bot Listener...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
