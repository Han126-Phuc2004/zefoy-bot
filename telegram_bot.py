"""
telegram_bot.py  –  Điều khiển Zefoy Bot qua Telegram Chat
Chạy: python telegram_bot.py
"""

import os
import sys
import time
import subprocess
import threading
import telebot
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TELEGRAM_TOKEN:
    print("[!] Thiếu TELEGRAM_BOT_TOKEN trong file .env!")
    print("    Vui lòng tạo bot trên Telegram (@BotFather) và điền token vào .env")
    sys.exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Quản lý tiến trình bot đang chạy
current_process = None
current_status = "Đang rảnh 😴"

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

*Danh sách câu lệnh:*
🔹 `/views <link_tiktok>` - Tự động tăng Views
🔹 `/hearts <link_tiktok>` - Tự động tăng Hearts
🔹 `/followers <link_tiktok>` - Tự động tăng Followers
🔹 `/shares <link_tiktok>` - Tự động tăng Shares
🔹 `/favorites <link_tiktok>` - Tự động tăng Favorites

🔹 `/run <dịch_vụ_1_đến_8> <link_tiktok>` - Chọn dịch vụ theo số
🔹 `/status` - Kiểm tra trạng thái bot
🔹 `/stop` - Dừng bot ngay lập tức

*Ví dụ:*
`/views https://vt.tiktok.com/ZSxxxxxx/`
    """
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['status'])
def check_status(message):
    global current_status
    bot.reply_to(message, f"📊 *Trạng thái hiện tại:* {current_status}", parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def stop_bot(message):
    global current_process, current_status
    if current_process and current_process.poll() is None:
        current_process.terminate()
        current_process = None
        current_status = "Đang rảnh 😴"
        bot.reply_to(message, "🛑 *Đã dừng Zefoy Bot thành công!*", parse_mode="Markdown")
    else:
        bot.reply_to(message, "ℹ️ Hiện không có bot nào đang chạy.")

def run_zefoy_task(chat_id, service_id, tiktok_url):
    global current_process, current_status
    service_name = SERVICES.get(service_id, "Views")
    current_status = f"⚡ Đang cày `{service_name}` cho URL: {tiktok_url}"

    bot.send_message(chat_id, f"🚀 *Đã khởi chạy Zefoy Bot!*\n🔹 Dịch vụ: `{service_name}`\n🔗 Link: {tiktok_url}\n⏱ Bot sẽ tự động giải CAPTCHA & chạy ngầm.", parse_mode="Markdown")

    cmd = [sys.executable, "zefoy_headless.py", "--service", str(service_id), "--url", tiktok_url]

    try:
        current_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )

        for line in iter(current_process.stdout.readline, ''):
            line = line.strip()
            if line:
                if "Submit!" in line or "Click Search" in line or "CAPTCHA đã được giải" in line:
                    bot.send_message(chat_id, f"📌 `{line}`", parse_mode="Markdown")

        current_process.wait()
    except Exception as e:
        bot.send_message(chat_id, f"❌ *Lỗi:* {e}", parse_mode="Markdown")
    finally:
        current_process = None
        current_status = "Đang rảnh 😴"
        bot.send_message(chat_id, "🏁 *Bot đã kết thúc tác vụ!*", parse_mode="Markdown")

@bot.message_handler(commands=['views', 'hearts', 'followers', 'shares', 'favorites', 'run'])
def handle_service_command(message):
    global current_process
    if current_process and current_process.poll() is None:
        bot.reply_to(message, "⚠️ *Bot đang chạy tác vụ khác!* Gõ `/stop` để dừng trước khi chạy mới.", parse_mode="Markdown")
        return

    text_parts = message.text.strip().split(maxsplit=2)
    cmd = text_parts[0].lower()

    service_map = {
        '/followers': '1',
        '/hearts': '2',
        '/views': '4',
        '/shares': '5',
        '/favorites': '6'
    }

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

    # Khởi chạy thread
    t = threading.Thread(target=run_zefoy_task, args=(message.chat.id, service_id, tiktok_url))
    t.start()

if __name__ == "__main__":
    print("🤖 Telegram Bot Controller đã sẵn sàng lắng nghe tin nhắn...")
    bot.infinity_polling()
