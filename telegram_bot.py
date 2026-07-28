"""
telegram_bot.py  –  Điều khiển Zefoy Bot chạy trên GitHub Actions hoặc Local qua Telegram
"""

import os
import sys
import requests
import telebot
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "Han126-Phuc2004/zefoy-bot")
GITHUB_PAT = os.getenv("GITHUB_PAT", os.getenv("GH_PAT", ""))

if not TELEGRAM_TOKEN:
    print("[!] Thieu TELEGRAM_BOT_TOKEN trong file .env!")

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
🤖 *ZEFOY TELEGRAM CONTROLLER FOR GITHUB ACTIONS*

Mỗi khi bạn gửi lệnh, Bot sẽ kích hoạt **GitHub Actions (Server miễn phí của GitHub)** chạy buff tự động!

*Danh sách câu lệnh:*
🔹 `/views <link_tiktok>` - Kích hoạt GitHub cày Views
🔹 `/hearts <link_tiktok>` - Kích hoạt GitHub cày Hearts
🔹 `/followers <link_tiktok>` - Kích hoạt GitHub cày Followers
🔹 `/shares <link_tiktok>` - Kích hoạt GitHub cày Shares
🔹 `/favorites <link_tiktok>` - Kích hoạt GitHub cày Favorites

🔹 `/run <số_1_đến_8> <link_tiktok>` - Chọn dịch vụ theo số (1-8)
    """
    bot.reply_to(message, help_text, parse_mode="Markdown")

def trigger_github_action(chat_id, service_id, tiktok_url):
    """Gửi yêu cầu tới GitHub API để kích hoạt GitHub Actions runner."""
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
            "tiktok_url": tiktok_url
        }
    }
    
    service_name = SERVICES.get(str(service_id), "Views")
    
    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code in [204, 200, 201]:
            bot.send_message(chat_id, f"🚀 *Đã gửi lệnh thành công tới GitHub Actions!*\n🔹 Dịch vụ: `{service_name}`\n🔗 Link: {tiktok_url}\n⏱ Server Ubuntu của GitHub đang khởi động bot cày view cho bạn...", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"❌ *Lỗi khi gọi GitHub API ({res.status_code}):*\n`{res.text}`", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(chat_id, f"❌ *Lỗi:* {e}", parse_mode="Markdown")

@bot.message_handler(commands=['views', 'hearts', 'followers', 'shares', 'favorites', 'run'])
def handle_service(message):
    text_parts = message.text.strip().split(maxsplit=2)
    cmd = text_parts[0].lower()
    
    service_map = {'/followers': '1', '/hearts': '2', '/views': '4', '/shares': '5', '/favorites': '6'}
    
    if cmd == '/run':
        if len(text_parts) < 3:
            bot.reply_to(message, "⚠️ Cú pháp đúng: `/run <số 1-8> <link_tiktok>`", parse_mode="Markdown")
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

if __name__ == "__main__":
    if TELEGRAM_TOKEN and TELEGRAM_TOKEN != "DUMMY_TOKEN":
        print("[+] Telegram Bot Controller is running and listening for commands...")
        bot.infinity_polling()
    else:
        print("[!] Please configure TELEGRAM_BOT_TOKEN in .env")
