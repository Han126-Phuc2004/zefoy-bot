"""
telegram_bot.py  –  Điều khiển Zefoy Bot chạy trên GitHub Actions hoặc Local qua Telegram PRO
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

ALLOWED_USERS_RAW = os.getenv("ALLOWED_USERS", os.getenv("ADMIN_CHAT_ID", "")).strip()
ALLOWED_USERS = [u.strip().lstrip('@').lower() for u in ALLOWED_USERS_RAW.split(",") if u.strip()]

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

def is_user_allowed(from_user) -> bool:
    """Kiểm tra xem người dùng có thuộc danh sách Whitelist/Admin hay không (theo ID hoặc Username)."""
    if not ALLOWED_USERS:
        return True
    if not from_user:
        return False
    user_id = str(from_user.id)
    username = (getattr(from_user, 'username', '') or '').lstrip('@').lower()
    for allowed in ALLOWED_USERS:
        if allowed == user_id or (username and allowed == username):
            return True
    return False

def extract_tiktok_url(text: str) -> str:
    """Trích xuất URL TikTok chính xác từ chuỗi nhập vào."""
    if not text:
        return ""
    match = re.search(r'https?://[^\s]+', text)
    if match:
        url = match.group(0)
        return url.rstrip('.,;!>')
    return ""

def parse_duration_and_url(text: str) -> tuple[int, str]:
    """Phân tích thời gian (phút) và TikTok URL từ câu lệnh."""
    duration = 60
    url = extract_tiktok_url(text)
    text_without_url = text.replace(url, "") if url else text
    num_matches = re.findall(r'\b\d{1,3}\b', text_without_url)
    if num_matches:
        for num_str in num_matches:
            val = int(num_str)
            if 1 <= val <= 330:
                duration = val
                break
    return duration, url

def parse_goal_views(text: str) -> int:
    """Đổi chuỗi như 100k, 1M, 50000 thành số nguyên."""
    if not text:
        return 0
    clean = text.strip().lower().replace(',', '').replace('.', '')
    if clean.endswith('k'):
        try:
            return int(float(clean[:-1]) * 1000)
        except Exception:
            return 0
    elif clean.endswith('m'):
        try:
            return int(float(clean[:-1]) * 1000000)
        except Exception:
            return 0
    else:
        try:
            return int(clean)
        except Exception:
            return 0

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

def trigger_github_action(chat_id, service_id, tiktok_url, duration_minutes=60, reply_to_msg_id=None):
    if not GITHUB_PAT:
        safe_send_message(chat_id, "❌ <b>Lỗi:</b> Chưa cấu hình <code>GITHUB_PAT</code> trong <code>.env</code>!", reply_to_message_id=reply_to_msg_id)
        return False

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
            "duration_minutes": str(duration_minutes),
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
                f"⏱ <b>Thời gian cày:</b> <code>{duration_minutes} phút</code>\n"
                f"🔗 <b>Link:</b> {html.escape(tiktok_url)}\n\n"
                f"⏱ Máy chủ Ubuntu của GitHub đang khởi động bot... Nhắn <code>/stop</code> nếu muốn hủy!",
                reply_to_message_id=reply_to_msg_id
            )
            return True
        else:
            safe_send_message(
                chat_id, 
                f"❌ <b>Lỗi kết nối GitHub API (Mã {res.status_code}):</b>\n"
                f"<code>{html.escape(res.text[:200])}</code>\n"
                f"Kiểm tra lại GITHUB_PAT token hoặc GITHUB_REPO.", 
                reply_to_message_id=reply_to_msg_id
            )
            return False
    except Exception as e:
        safe_send_message(chat_id, f"❌ <b>Lỗi:</b> {html.escape(str(e))}", reply_to_message_id=reply_to_msg_id)
        return False

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    help_text = """
🤖 <b>ZEFOY TELEGRAM BOT CONTROLLER PRO</b>

Bạn có thể gửi <b>trực tiếp Link TikTok</b> hoặc gửi <b>file .txt chứa danh sách link</b> vào đây!

🔥 <b>CÁC LỆNH CÀY TƯƠNG TÁC:</b>
🔹 <code>/views [thời_gian_phút] &lt;link&gt;</code> - Tăng Views (Ví dụ: <code>/views 30 https://...</code>)
🔹 <code>/favorites [thời_gian_phút] &lt;link&gt;</code> - Tăng Yêu thích
🔹 <code>/combo [thời_gian_phút] &lt;link&gt;</code> - Cày Combo <b>Views + Favorites</b> song song!
🔹 <code>/batch &lt;link1&gt; &lt;link2&gt; ...</code> - Cày hàng loạt nhiều link
🔹 <code>/goal &lt;mục_tiêu_view&gt; &lt;link&gt;</code> - Cày theo mục tiêu (Ví dụ: <code>/goal 100k https://...</code>)

📊 <b>QUẢN LÝ & THỐNG KÊ:</b>
⚡ <code>/status</code> - Xem danh sách bot đang cày trên GitHub
📜 <code>/history</code> - Xem lịch sử 10 lần cày gần nhất
📊 <code>/report</code> - Báo cáo thống kê hiệu suất hôm nay
🛑 <code>/stop</code> - HỦY & DỪNG tất cả các bot đang cày trên GitHub!
    """
    safe_send_message(message.chat.id, help_text, reply_to_message_id=message.message_id)

@bot.message_handler(commands=['stop', 'cancel'])
def cancel_github_actions(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

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
                safe_send_message(message.chat.id, "ℹ️ <b>Hiện không có bot nào đang cày trên GitHub.</b>", reply_to_message_id=message.message_id)
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

@bot.message_handler(commands=['combo'])
def handle_combo(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    text = message.text.strip()
    duration, _ = parse_duration_and_url(text)
    
    urls = []
    for line in text.split():
        u = extract_tiktok_url(line)
        if u and u not in urls:
            urls.append(u)

    if not urls:
        safe_send_message(
            message.chat.id, 
            "⚠️ <b>Cú pháp:</b> <code>/combo [thời_gian_phút] &lt;link_tiktok&gt;</code>\n"
            "Ví dụ: <code>/combo 45 https://vt.tiktok.com/ZSxxxxxx/</code>\n"
            "Chế độ Combo sẽ khởi chạy đồng thời 2 bot song song: <b>Views (Xem) + Favorites (Yêu thích)</b>!", 
            reply_to_message_id=message.message_id
        )
        return

    safe_send_message(
        message.chat.id, 
        f"🔥 <b>Khởi chạy Combo Tương tác Đa dịch vụ cho {len(urls)} link!</b>\n"
        f"⏱ Thời gian: <code>{duration} phút/tác vụ</code>\n"
        f"⚡ Đang khởi tạo 2 bot song song (Views + Favorites) cho mỗi link...",
        reply_to_message_id=message.message_id
    )
    
    for u in urls:
        trigger_github_action(message.chat.id, "4", u, duration_minutes=duration)
        time.sleep(1.5)
        trigger_github_action(message.chat.id, "6", u, duration_minutes=duration)
        time.sleep(1.5)

@bot.message_handler(commands=['batch'])
def handle_batch(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    text = message.text.strip()
    duration, _ = parse_duration_and_url(text)
    
    urls = []
    for line in text.split():
        u = extract_tiktok_url(line)
        if u and u not in urls:
            urls.append(u)

    if not urls:
        safe_send_message(
            message.chat.id, 
            "⚠️ <b>Cú pháp:</b> <code>/batch &lt;link1&gt; &lt;link2&gt; &lt;link3&gt;</code>\n"
            "hoặc gửi trực tiếp file <code>.txt</code> chứa danh sách link TikTok!", 
            reply_to_message_id=message.message_id
        )
        return

    safe_send_message(message.chat.id, f"📥 <b>Phát hiện {len(urls)} link TikTok!</b>\nĐang gửi tác vụ cày hàng loạt lên GitHub (thời gian: {duration} phút)...", reply_to_message_id=message.message_id)
    count = 0
    for u in urls:
        if trigger_github_action(message.chat.id, "4", u, duration_minutes=duration):
            count += 1
        time.sleep(1.5)

    safe_send_message(message.chat.id, f"✅ <b>Đã gửi thành công {count}/{len(urls)} tác vụ cày lên GitHub Actions!</b>")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return
        
    doc = message.document
    if doc and doc.file_name and doc.file_name.endswith('.txt'):
        try:
            file_info = bot.get_file(doc.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            content = downloaded_file.decode('utf-8', errors='ignore')
            
            urls = []
            for line in content.splitlines():
                u = extract_tiktok_url(line)
                if u and u not in urls:
                    urls.append(u)
                    
            if not urls:
                safe_send_message(message.chat.id, "⚠️ Không tìm thấy link TikTok hợp lệ nào trong file .txt!", reply_to_message_id=message.message_id)
                return
                
            safe_send_message(message.chat.id, f"📥 <b>Đã nhận file .txt chứa {len(urls)} link TikTok!</b>\nĐang gửi tác vụ cày hàng loạt...", reply_to_message_id=message.message_id)
            
            count = 0
            for u in urls:
                if trigger_github_action(message.chat.id, "4", u, duration_minutes=60):
                    count += 1
                time.sleep(1.5)
                
            safe_send_message(message.chat.id, f"✅ <b>Đã gửi thành công {count}/{len(urls)} tác vụ lên GitHub Actions!</b>")
        except Exception as e:
            safe_send_message(message.chat.id, f"❌ <b>Lỗi đọc file txt:</b> {html.escape(str(e))}", reply_to_message_id=message.message_id)
    else:
        safe_send_message(message.chat.id, "⚠️ Vui lòng chỉ gửi file văn bản <code>.txt</code> chứa các đường link TikTok!", reply_to_message_id=message.message_id)

@bot.message_handler(commands=['status'])
def handle_status(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    if not GITHUB_PAT:
        safe_send_message(message.chat.id, "❌ Chưa cấu hình GITHUB_PAT!", reply_to_message_id=message.message_id)
        return

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?per_page=20"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            runs = res.json().get("workflow_runs", [])
            active_runs = [r for r in runs if r.get("status") in ["in_progress", "queued", "waiting", "requested"]]

            if not active_runs:
                safe_send_message(message.chat.id, "ℹ️ <b>Hiện không có bot nào đang cày trên GitHub Actions.</b>", reply_to_message_id=message.message_id)
                return

            total_jobs = 0
            runs_detail = []
            for i, run in enumerate(active_runs, 1):
                run_id = run.get("id")
                st = run.get("status")
                created_at = run.get("created_at", "")[:19].replace("T", " ")
                html_url = run.get("html_url")
                
                # Lấy danh sách Matrix Jobs bên trong
                jobs_count = 2
                try:
                    jres = requests.get(run.get("jobs_url"), headers=headers, timeout=5)
                    if jres.status_code == 200:
                        jlist = jres.json().get("jobs", [])
                        if jlist:
                            jobs_count = len(jlist)
                except Exception:
                    pass

                total_jobs += jobs_count
                status_emoji = "⏳" if st in ["queued", "waiting"] else "🚀"
                runs_detail.append(
                    f"{i}. {status_emoji} <b>Workflow ID:</b> <code>{run_id}</code>\n"
                    f"   • Số máy chủ Matrix: <b>{jobs_count} Workers song song</b>\n"
                    f"   • Trạng thái: <code>{st}</code>\n"
                    f"   • Thời gian tạo: {created_at} UTC\n"
                    f"   • Link GitHub: <a href='{html_url}'>Xem chi tiết</a>\n"
                )

            status_msg = (
                f"⚡ <b>ĐANG CÓ {len(active_runs)} TÁC VỤ WORKFLOW ({total_jobs} MÁY CHỦ MATRIX WORKERS) ĐANG CHẠY TRÊN GITHUB:</b>\n\n"
                + "\n".join(runs_detail)
            )

            safe_send_message(message.chat.id, status_msg, reply_to_message_id=message.message_id)
        else:
            safe_send_message(message.chat.id, f"❌ Lỗi kết nối GitHub API: {res.status_code}", reply_to_message_id=message.message_id)
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Lỗi: {html.escape(str(e))}", reply_to_message_id=message.message_id)

@bot.message_handler(commands=['history'])
def handle_history(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    if not GITHUB_PAT:
        safe_send_message(message.chat.id, "❌ Chưa cấu hình GITHUB_PAT!", reply_to_message_id=message.message_id)
        return

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?per_page=15"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            runs = res.json().get("workflow_runs", [])
            completed_runs = [r for r in runs if r.get("status") == "completed"]

            if not completed_runs:
                safe_send_message(message.chat.id, "📜 <b>Chưa có lịch sử chạy hoàn tất nào gần đây.</b>", reply_to_message_id=message.message_id)
                return

            hist_msg = f"📜 <b>LỊCH SỬ 10 TIẾN TRÌNH GẦN NHẤT:</b>\n\n"
            for i, run in enumerate(completed_runs[:10], 1):
                conclusion = run.get("conclusion")
                created_at = run.get("created_at", "")[:19].replace("T", " ")
                
                if conclusion == "success":
                    icon = "✅ Thành công"
                elif conclusion == "cancelled":
                    icon = "🛑 Đã hủy"
                else:
                    icon = f"❌ {conclusion}"

                hist_msg += (
                    f"{i}. {icon}\n"
                    f"   • Thời gian: {created_at} UTC\n"
                    f"   • Run ID: <code>{run.get('id')}</code>\n\n"
                )

            safe_send_message(message.chat.id, hist_msg, reply_to_message_id=message.message_id)
        else:
            safe_send_message(message.chat.id, f"❌ Lỗi kết nối GitHub API: {res.status_code}", reply_to_message_id=message.message_id)
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Lỗi: {html.escape(str(e))}", reply_to_message_id=message.message_id)

@bot.message_handler(commands=['report'])
def handle_report(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    if not GITHUB_PAT:
        safe_send_message(message.chat.id, "❌ Chưa cấu hình GITHUB_PAT!", reply_to_message_id=message.message_id)
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
            
            today_str = time.strftime("%Y-%m-%d")
            runs_today = [r for r in runs if r.get("created_at", "").startswith(today_str)]
            
            successful_runs = [r for r in runs_today if r.get("conclusion") == "success"]
            running_runs = [r for r in runs_today if r.get("status") in ["in_progress", "queued"]]
            cancelled_runs = [r for r in runs_today if r.get("conclusion") == "cancelled"]
            report_msg = (
                f"📊 <b>BÁO CÁO THỐNG KÊ TỔNG QUAN HÔM NAY ({today_str})</b>\n\n"
                f"🚀 <b>Tổng số lượt chạy:</b> {len(runs_today)}\n"
                f"✅ <b>Tác vụ hoàn tất:</b> {len(successful_runs)}\n"
                f"⚡ <b>Đang hoạt động:</b> {len(running_runs)}\n"
                f"🛑 <b>Tác vụ đã hủy:</b> {len(cancelled_runs)}\n\n"
                f"💡 <i>Mẹo: Hệ thống hoạt động 24/7 trên GitHub Actions với thời gian cày tùy chỉnh.</i>"
            )
            safe_send_message(message.chat.id, report_msg, reply_to_message_id=message.message_id)
        else:
            safe_send_message(message.chat.id, f"❌ Lỗi kết nối GitHub API: {res.status_code}", reply_to_message_id=message.message_id)
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Lỗi: {html.escape(str(e))}", reply_to_message_id=message.message_id)

@bot.message_handler(commands=['analytics', 'thongke'])
def handle_analytics(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    if not GITHUB_PAT:
        safe_send_message(message.chat.id, "❌ Chưa cấu hình GITHUB_PAT!", reply_to_message_id=message.message_id)
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
            total_runs = len(runs)
            successful_runs = len([r for r in runs if r.get("conclusion") == "success"])
            active_runs = len([r for r in runs if r.get("status") in ["in_progress", "queued"]])
            cancelled_runs = len([r for r in runs if r.get("conclusion") == "cancelled"])

            # Ước tính tổng views cày được (mỗi run trung bình cày 60-120 phút = 60,000 - 120,000 views)
            est_views = (successful_runs * 60000) + (active_runs * 15000)

            analytics_msg = (
                f"📈 <b>BÁO CÁO PHÂN TÍCH & HIỆU SUẤT HỆ THỐNG (/analytics)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚀 <b>Tổng số Tác vụ đã kích hoạt:</b> {total_runs}\n"
                f"✅ <b>Tác vụ hoàn thành xuất sắc:</b> {successful_runs}\n"
                f"⚡ <b>Máy chủ đang cày (In-Progress):</b> {active_runs} (Tương đương {active_runs * 2} Workers Matrix)\n"
                f"🛑 <b>Tác vụ đã hủy:</b> {cancelled_runs}\n"
                f"🏆 <b>Ước tính TỔNG VIEW ĐÃ BUFF:</b> ~<b>{est_views:,} Views</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>Hệ thống tự động sử dụng Matrix Workers 200 OK AI Vision chống 429 hoàn hảo.</i>"
            )
            safe_send_message(message.chat.id, analytics_msg, reply_to_message_id=message.message_id)
        else:
            safe_send_message(message.chat.id, f"❌ Lỗi kết nối GitHub API: {res.status_code}", reply_to_message_id=message.message_id)
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Lỗi: {html.escape(str(e))}", reply_to_message_id=message.message_id)

SCHEDULES_FILE = "schedules.json"

def load_schedules():
    if os.path.exists(SCHEDULES_FILE):
        try:
            with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_schedules(schedules):
    try:
        with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
            json.dump(schedules, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] Save schedules error: {e}")

def get_tiktok_user_latest_videos(username, limit=1):
    """Lấy danh sách N video mới nhất từ TikTok user profile."""
    clean_user = username.replace('@', '').strip()
    url = f"https://www.tiktok.com/@{clean_user}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    videos = []
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            found = re.findall(r'https://www\.tiktok\.com/@[\w\.\-]+/video/(\d+)', res.text)
            if not found:
                found = re.findall(r'/video/(\d+)', res.text)
            for vid in found:
                v_url = f"https://www.tiktok.com/@{clean_user}/video/{vid}"
                if v_url not in videos:
                    videos.append(v_url)
                if len(videos) >= limit:
                    break
    except Exception as e:
        print(f"[!] Scrape user videos error: {e}")
    
    if not videos:
        videos = [url]
    return videos

@bot.message_handler(commands=['target'])
def handle_target(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    text = message.text.strip()
    parts = text.split(maxsplit=2)
    if len(parts) < 2:
        safe_send_message(
            message.chat.id, 
            "⚠️ <b>Cú pháp:</b> <code>/target [số_video] @username_hoặc_link</code>\n\n"
            "Ví dụ:\n"
            "• <code>/target @nhkaoud</code> (Cày 1 video mới nhất)\n"
            "• <code>/target 3 @nhkaoud</code> (Cày 3 video mới nhất cùng lúc)", 
            reply_to_message_id=message.message_id
        )
        return

    video_count = 1
    target_input = parts[1].strip()
    
    if len(parts) >= 3 and parts[1].isdigit():
        video_count = int(parts[1])
        target_input = parts[2].strip()
    elif parts[1].isdigit():
        video_count = int(parts[1])

    duration, tiktok_url = parse_duration_and_url(target_input)
    
    if tiktok_url and not target_input.startswith('@'):
        target_urls = [tiktok_url]
    else:
        username = target_input.replace('@', '').strip()
        safe_send_message(message.chat.id, f"🔍 Đang quét <b>{video_count} video mới nhất</b> của kênh <code>@{username}</code>...", reply_to_message_id=message.message_id)
        target_urls = get_tiktok_user_latest_videos(username, limit=video_count)

    safe_send_message(
        message.chat.id, 
        f"🎯 <b>Đã cài đặt Target cày tự động cho {len(target_urls)} video:</b>\n"
        + "\n".join([f"• <code>{u}</code>" for u in target_urls]) + "\n\n"
        f"🚀 Đang khởi tạo dàn Máy chủ Matrix cày gối đầu...", 
        reply_to_message_id=message.message_id
    )

    for url in target_urls:
        trigger_github_action(message.chat.id, "4", url, duration_minutes=duration)

@bot.message_handler(commands=['goal', 'muctieu'])
def handle_goal(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    text = message.text.strip()
    parts = text.split()
    
    if len(parts) < 2:
        safe_send_message(
            message.chat.id, 
            "🎯 <b>CÚ PHÁP LỆNH /goal (CÀY THEO MỤC TIÊU VIEW):</b>\n\n"
            "<code>/goal &lt;số_views_mục_tiêu&gt; [thời_gian_phút] &lt;link_tiktok&gt;</code>\n\n"
            "<b>Ví dụ:</b>\n"
            "• <code>/goal 100k https://vt.tiktok.com/ZS48b1NEy/</code> (Cày mục tiêu 100,000 Views)\n"
            "• <code>/goal 500k 45 https://vt.tiktok.com/ZS48b1NEy/</code> (Cày 500,000 Views, 45p/worker)\n"
            "• <code>/goal 1M https://vt.tiktok.com/ZS48b1NEy/</code> (Cày 1 Triệu Views)\n\n"
            "💡 <i>Hệ thống sẽ tự động phân bổ số lượng Máy chủ Matrix Workers gối đầu để đạt mục tiêu nhanh nhất!</i>", 
            reply_to_message_id=message.message_id
        )
        return

    duration, tiktok_url = parse_duration_and_url(text)
    
    target_views = 0
    for p in parts[1:]:
        v = parse_goal_views(p)
        if v > 0:
            target_views = v
            break

    if not tiktok_url or target_views <= 0:
        safe_send_message(
            message.chat.id, 
            "⚠️ <b>Lỗi cú pháp:</b> Vui lòng nhập số views mục tiêu hợp lệ và đường link TikTok!\n"
            "Ví dụ: <code>/goal 100k https://vt.tiktok.com/ZS48b1NEy/</code>", 
            reply_to_message_id=message.message_id
        )
        return

    est_runs = max(1, min(10, (target_views + 59999) // 60000))
    est_time = est_runs * (duration if duration else 30)

    safe_send_message(
        message.chat.id, 
        f"🎯 <b>ĐÃ CÀI ĐẶT MỤC TIÊU CÀY VIEW (GOAL TARGET)!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <b>Link Target:</b> {html.escape(tiktok_url)}\n"
        f"🏆 <b>Mục tiêu View:</b> <code>{target_views:,} Views</code>\n"
        f"⚡ <b>Máy chủ phân bổ:</b> <code>{est_runs} Tiến trình Workflow ({est_runs * 4} Matrix Workers)</code>\n"
        f"⏱ <b>Thời gian ước tính:</b> ~<code>{est_time} phút</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 Đang kích hoạt tự động dàn máy chủ GitHub Actions cày gối đầu...", 
        reply_to_message_id=message.message_id
    )

    count = 0
    for _ in range(est_runs):
        if trigger_github_action(message.chat.id, "4", tiktok_url, duration_minutes=duration):
            count += 1
        time.sleep(1.5)

    safe_send_message(
        message.chat.id, 
        f"✅ <b>Đã kích hoạt thành công {count}/{est_runs} luồng cày mục tiêu ({target_views:,} Views) trên GitHub Actions!</b>", 
        reply_to_message_id=message.message_id
    )

@bot.message_handler(commands=['schedule', 'datlich'])
def handle_schedule(message):
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    text = message.text.strip()
    parts = text.split(maxsplit=2)
    if len(parts) < 3:
        schedules = load_schedules()
        msg = "⏰ <b>HƯỚNG DẪN ĐẶT LỊCH CÀY TỰ ĐỘNG (/schedule)</b>\n\n"
        msg += "<b>Cú pháp:</b> <code>/schedule &lt;số_giờ_lặp&gt; &lt;link_TikTok_hoặc_@username&gt;</code>\n"
        msg += "Ví dụ: <code>/schedule 6 https://vt.tiktok.com/ZS4RWsL2A/</code> (Cứ 6 tiếng tự cày 1 lần)\n\n"
        msg += f"📋 <b>Danh sách lịch đang hoạt động ({len(schedules)}):</b>\n"
        for i, s in enumerate(schedules, 1):
            msg += f"{i}. Lặp mỗi <b>{s.get('interval_hours')}h</b> ➔ <code>{html.escape(s.get('url'))}</code>\n"
        safe_send_message(message.chat.id, msg, reply_to_message_id=message.message_id)
        return

    try:
        interval_hours = float(parts[1])
        target_str = parts[2].strip()
        _, tiktok_url = parse_duration_and_url(target_str)
        if not tiktok_url:
            tiktok_url = target_str

        schedules = load_schedules()
        new_item = {
            "chat_id": message.chat.id,
            "interval_hours": interval_hours,
            "url": tiktok_url,
            "last_run": 0
        }
        schedules.append(new_item)
        save_schedules(schedules)

        safe_send_message(
            message.chat.id, 
            f"✅ <b>ĐÃ ĐẶT LỊCH THÀNH CÔNG!</b>\n\n"
            f"⏰ <b>Chu kỳ:</b> Cứ mỗi <b>{interval_hours} tiếng</b>\n"
            f"🔗 <b>Target:</b> <code>{html.escape(tiktok_url)}</code>\n"
            f"🤖 <i>GitHub Actions sẽ tự động kích hoạt máy chủ cày đúng giờ!</i>",
            reply_to_message_id=message.message_id
        )
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Lỗi định dạng số giờ: {html.escape(str(e))}", reply_to_message_id=message.message_id)

def run_scheduler_loop():
    """Vòng lặp daemon kiểm tra và tự động trigger công việc theo lịch."""
    while True:
        try:
            time.sleep(60)
            schedules = load_schedules()
            now = time.time()
            updated = False
            for s in schedules:
                interval_sec = s.get("interval_hours", 6) * 3600
                last_run = s.get("last_run", 0)
                if now - last_run >= interval_sec:
                    chat_id = s.get("chat_id")
                    url = s.get("url")
                    print(f"[+] [Scheduler] Kích hoạt cày tự động theo lịch cho URL: {url}")
                    trigger_github_action(chat_id, "4", url, duration_minutes=60)
                    s["last_run"] = now
                    updated = True
            if updated:
                save_schedules(schedules)
        except Exception as e:
            print(f"[!] Scheduler error: {e}")

@bot.message_handler(commands=[
    'views', 'view', 'hearts', 'heart', 'followers', 'follower', 
    'shares', 'share', 'favorites', 'favorite', 'fav', 'favs', 
    'chearts', 'cheart', 'comment', 'comments', 'live', 'livestream', 'repost', 'run'
])
def handle_service(message):
    if not message or not message.text:
        return
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    text = message.text.strip()
    duration, tiktok_url = parse_duration_and_url(text)
    
    parts = text.split(maxsplit=2)
    cmd = parts[0].lower().split('@')[0]
    
    if cmd == '/run':
        if len(parts) < 3:
            safe_send_message(message.chat.id, "⚠️ Cú pháp: <code>/run &lt;số 1-8&gt; [thời_gian_phút] &lt;link_tiktok&gt;</code>", reply_to_message_id=message.message_id)
            return
        service_id = parts[1]
    else:
        service_id = SERVICE_COMMAND_MAP.get(cmd, '4')

    if not tiktok_url:
        safe_send_message(
            message.chat.id, 
            f"⚠️ <b>Vui lòng điền link TikTok hợp lệ!</b>\n\nVí dụ: <code>{html.escape(cmd)} 30 https://vt.tiktok.com/ZSxxxxxx/</code>", 
            reply_to_message_id=message.message_id
        )
        return

    trigger_github_action(message.chat.id, service_id, tiktok_url, duration_minutes=duration, reply_to_msg_id=message.message_id)

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    if not message or not message.text:
        return
    if not is_user_allowed(message.from_user):
        safe_send_message(message.chat.id, "⛔ <b>Bạn không có quyền sử dụng Bot này.</b>", reply_to_message_id=message.message_id)
        return

    text = message.text.strip()
    
    if text.startswith('/'):
        cmd_name = text.split()[0].lower().split('@')[0]
        if cmd_name in ['/start', '/help', '/trogiup']:
            send_welcome(message)
            return
        elif cmd_name in ['/stop', '/cancel', '/dung']:
            cancel_github_actions(message)
            return

    duration, tiktok_url = parse_duration_and_url(text)
    if tiktok_url:
        trigger_github_action(message.chat.id, "4", tiktok_url, duration_minutes=duration, reply_to_msg_id=message.message_id)
    else:
        safe_send_message(
            message.chat.id, 
            "🤖 <b>ZEFOY TELEGRAM BOT CONTROLLER PRO</b>\n\n"
            "Gửi <b>link TikTok</b> trực tiếp vào đây để tăng View,\n"
            "hoặc gõ <code>/help</code> để xem danh sách lệnh!", 
            reply_to_message_id=message.message_id
        )

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK - Zefoy Telegram Bot PRO is running")

def start_health_check_server():
    port = int(os.getenv("PORT", 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"[+] Health check server listening on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"[!] Warning: Health check server stopped: {e}")

def setup_bot_commands():
    """Tự động đăng ký danh sách gợi ý nút bấm / trong menu Telegram."""
    try:
        commands = [
            telebot.types.BotCommand('start', 'Khởi động & xem hướng dẫn'),
            telebot.types.BotCommand('help', 'Xem danh sách tất cả câu lệnh'),
            telebot.types.BotCommand('views', 'Tăng Views (Ví dụ: /views 30 link)'),
            telebot.types.BotCommand('favorites', 'Tăng Yêu thích Favorites'),
            telebot.types.BotCommand('combo', 'Cày Combo Views + Favorites song song'),
            telebot.types.BotCommand('batch', 'Cày hàng loạt nhiều link TikTok'),
            telebot.types.BotCommand('goal', 'Cày theo mục tiêu Views (Ví dụ: /goal 100k link)'),
            telebot.types.BotCommand('target', 'Cày tự động theo @username kênh TikTok'),
            telebot.types.BotCommand('schedule', 'Đặt lịch cày tự động lặp lại'),
            telebot.types.BotCommand('analytics', 'Báo cáo đồ thị & tổng view cày được'),
            telebot.types.BotCommand('status', 'Xem các bot đang chạy trên GitHub'),
            telebot.types.BotCommand('history', 'Xem lịch sử 10 lần cày gần nhất'),
            telebot.types.BotCommand('report', 'Báo cáo thống kê hiệu suất hôm nay'),
            telebot.types.BotCommand('stop', 'HỦY & DỪNG tất cả các bot đang cày')
        ]
        bot.set_my_commands(commands)
        print("[+] Registered Bot Commands Menu in Telegram UI.")
    except Exception as e:
        print(f"[!] Warning set_my_commands error: {e}")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "DUMMY_TOKEN":
        print("[❌] ERROR: TELEGRAM_BOT_TOKEN is missing in .env file!")
        sys.exit(1)

    print("[+] Starting HTTP Health Check thread...")
    threading.Thread(target=start_health_check_server, daemon=True).start()
    
    print("[+] Starting Background Scheduler thread...")
    threading.Thread(target=run_scheduler_loop, daemon=True).start()
    
    try:
        bot.remove_webhook()
        setup_bot_commands()
        print("[+] Webhook cleared & Bot Commands menu registered.")
    except Exception as e:
        print(f"[!] Startup notice: {e}")

    print("[+] Starting Telegram Bot PRO Listener (Infinity Polling)...")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=False)
        except Exception as e:
            print(f"[!] Exception during polling: {e}. Retrying in 5 seconds...")
            time.sleep(5)
