"""
ai_video_generator.py  –  Tự động viết Kịch bản, Tạo Giọng đọc AI & Xuất Video TikTok ngắn (9:16)
Cơ chế: Dùng PIL + MoviePy + Edge-TTS (Không cần ImageMagick, tương thích 100% Windows/Linux/Cloud)
"""

import os
import re
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import time
import gc
import json
import random
import asyncio
import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

try:
    import edge_tts
    from moviepy import ImageClip, AudioFileClip
except ImportError:
    pass

def generate_tiktok_script(topic: str) -> dict:
    """Sử dụng Gemini API hoặc OpenRouter/Groq để sinh kịch bản TikTok hấp dẫn (Hook + 3 Facts)."""
    prompt = f"""
    Bạn là một nhà sáng tạo nội dung TikTok hàng đầu. Hãy viết 1 kịch bản video ngắn (TikTok/Reels) về chủ đề: "{topic}".
    
    Yêu cầu trả về duy nhất một cấu trúc JSON như sau (không kèm markdown format nào khác):
    {{
        "title": "Tiêu đề hấp dẫn",
        "hook": "Câu mở đầu giật gân thu hút người xem trong 3s đầu",
        "facts": [
            "Ý 1 ngắn gọn cô đọng",
            "Ý 2 ngắn gọn cô đọng",
            "Ý 3 ngắn gọn cô đọng"
        ],
        "call_to_action": "Hãy thả tim và follow kênh để khám phá thêm nhiều điều kỳ thú!",
        "search_keywords": ["vũ trụ", "khoa học"]
    }}
    """
    
    # Thử Google Gemini API
    google_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if google_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={google_key}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
            if res.status_code == 200:
                raw_txt = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                json_str = re.sub(r'```json\s*|\s*```', '', raw_txt).strip()
                return json.loads(json_str)
        except Exception as e:
            print(f"[!] Lỗi Gemini API trong script gen: {e}")
            
    # Fallback script mẫu nếu không có API key hoặc API bận
    return {
        "title": f"BÍ ẨN {topic.upper()}",
        "hook": f"Bạn có biết sự thật ngỡ ngàng này về {topic} mà 99% mọi người chưa hề hay biết?",
        "facts": [
            f"Điều thứ nhất: {topic} ẩn chứa những bí mật vượt xa trí tưởng tượng của con người.",
            f"Điều thứ hai: Các nhà khoa học đã chứng minh hiện tượng này xảy ra liên tục hàng ngày.",
            f"Điều thứ ba: Chỉ cần tìm hiểu sâu hơn bạn sẽ thấy mọi thứ vô cùng kỳ diệu."
        ],
        "call_to_action": "Hãy thả tim và follow kênh để khám phá thêm nhiều điều kỳ thú!",
        "search_keywords": [topic]
    }

async def _async_tts(text: str, output_path: str, voice: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def generate_everai_tts(text: str, output_path: str, voice_code: str = "vi_female_kieunhi_mn") -> bool:
    """Tạo giọng đọc AI từ EverAI API (https://www.everai.vn/api/v1/tts)."""
    api_key = os.getenv("EVERAI_API_KEY", "").strip()
    if not api_key:
        return False
        
    print(f"[EverAI TTS] Dang tao giong doc qua EverAI API ({voice_code})...")
    url = "https://www.everai.vn/api/v1/tts"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "input_text": text,
        "text": text,
        "voice_code": voice_code,
        "audio_type": "mp3",
        "speed_rate": 1.0,
        "pitch_rate": 1.0
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        if res.status_code == 200:
            if res.headers.get("content-type", "").startswith("audio/"):
                with open(output_path, "wb") as f:
                    f.write(res.content)
                print(f"[EverAI TTS] Da luu file am thanh EverAI truc tiep: {output_path}")
                return True

            data = res.json()
            if data.get("error_code") and data.get("error_code") != 0:
                print(f"[!] EverAI Notice: {data.get('error_message')}")
                return False

            audio_url = data.get("audio_link") or (data.get("result") or {}).get("audio_link")
            request_id = (data.get("result") or {}).get("request_id") or data.get("request_id")
            
            if not audio_url and request_id:
                for _ in range(5):
                    time.sleep(1.5)
                    poll_res = requests.get(f"https://www.everai.vn/api/v1/tts/{request_id}", headers=headers, timeout=5)
                    if poll_res.status_code == 200:
                        poll_data = poll_res.json()
                        audio_url = poll_data.get("result", {}).get("audio_link") or poll_data.get("audio_link")
                        if audio_url:
                            break
                            
            if audio_url:
                audio_res = requests.get(audio_url, timeout=10)
                if audio_res.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(audio_res.content)
                    print(f"[EverAI TTS] Da luu file am thanh EverAI: {output_path}")
                    return True
        print(f"[!] EverAI API notice status: {res.status_code}")
    except Exception as e:
        print(f"[!] Lỗi EverAI TTS: {e}")
    return False

def generate_voiceover(text: str, output_audio_path: str, voice: str = "vi-VN-HoaiMyNeural") -> bool:
    """Tự động chuyển kịch bản văn bản thành giọng đọc AI Tiếng Việt truyền cảm chuẩn HD."""
    # 1. Thử EverAI API nếu có cấu hình EVERAI_API_KEY
    if os.getenv("EVERAI_API_KEY"):
        everai_voice = os.getenv("EVERAI_VOICE_CODE", "vi_female_kieunhi_mn")
        success = generate_everai_tts(text, output_audio_path, voice_code=everai_voice)
        if success:
            return True
        print("[!] Chuyen sang Edge-TTS...")

    # 2. Dự phòng Edge-TTS Microsoft Neural Voice (Asyncio Thread Safe)
    try:
        print(f"[AI Voice] Dang sinh giong doc Edge-TTS ({voice})...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_async_tts(text, output_audio_path, voice))
        finally:
            loop.close()
        print(f"[AI Voice] Da luu file am thanh Edge-TTS: {output_audio_path}")
        return True
    except Exception as e:
        print(f"[!] Lỗi sinh giọng đọc TTS: {e}")
        return False

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Cắt dòng văn bản tự động để không bị tràn khung màn hình 9:16."""
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines

import subprocess
import imageio_ffmpeg

def create_video_frame(script_data: dict, width: int = 720, height: int = 1280) -> Image.Image:
    """Vẽ 1 khung ảnh đẹp chuẩn CRISP HD 720p 9:16 dùng Pillow (Nền Dark Slate + Card Phụ Đề + Title Vàng Gold)."""
    img = Image.new("RGB", (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 40)
        font_body = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 30)
    except Exception:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
        
    title_text = script_data['title'].upper()
    title_lines = wrap_text(title_text, font_title, width - 110, draw)
    
    y_cursor = 150
    card_bg = (30, 41, 59)
    draw.rounded_rectangle([40, y_cursor - 15, width - 40, y_cursor + len(title_lines) * 55 + 15], radius=15, fill=card_bg, outline=(234, 179, 8), width=3)
    
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        w = bbox[2] - bbox[0]
        x = (width - w) // 2
        draw.text((x, y_cursor), line, font=font_title, fill=(234, 179, 8))
        y_cursor += 55
        
    y_cursor += 50
    body_lines = []
    body_lines.extend(wrap_text(f"🔥 {script_data['hook']}", font_body, width - 140, draw))
    body_lines.append("")
    for i, fact in enumerate(script_data['facts'], 1):
        body_lines.extend(wrap_text(f"✨ Điều {i}: {fact}", font_body, width - 140, draw))
        body_lines.append("")
    body_lines.extend(wrap_text(f"👉 {script_data['call_to_action']}", font_body, width - 140, draw))
    
    card_top = y_cursor - 20
    card_bottom = min(height - 100, y_cursor + len(body_lines) * 38 + 30)
    draw.rounded_rectangle([45, card_top, width - 45, card_bottom], radius=18, fill=(30, 41, 59))
    
    for line in body_lines:
        if not line:
            y_cursor += 16
            continue
        bbox = draw.textbbox((0, 0), line, font=font_body)
        w = bbox[2] - bbox[0]
        x = (width - w) // 2
        fill_color = (255, 255, 255)
        if "🔥" in line:
            fill_color = (56, 189, 248)
        elif "👉" in line:
            fill_color = (74, 222, 128)
        draw.text((x, y_cursor), line, font=font_body, fill=fill_color)
        y_cursor += 38
        
    return img

def render_tiktok_video(topic: str, output_mp4_path: str = "output_tiktok.mp4", status_callback=None) -> str:
    """Hàm trung tâm: Viết kịch bản ➔ Sinh giọng đọc ➔ Xuất file MP4 siêu tốc qua Direct FFmpeg CLI."""
    print(f"\n[AI Video Generator] Bat dau tu dong tao video CRISP HD cho chu de: '{topic}'...")
    
    if status_callback:
        status_callback("1/4", "🧠 Đang viết kịch bản AI...")
        
    script_data = generate_tiktok_script(topic)
    full_speech = f"{script_data['hook']} { ' '.join(script_data['facts']) } {script_data['call_to_action']}"
    print(f"[Kich ban AI]:\n- Hook: {script_data['hook']}\n- So y: {len(script_data['facts'])}")
    
    if status_callback:
        status_callback("2/4", "🎙️ Đang sinh giọng đọc AI (EverAI/Edge-TTS)...")

    ts = int(time.time())
    temp_audio = f"temp_voice_{ts}.mp3"
    temp_img = f"temp_frame_{ts}.png"
    
    generate_voiceover(full_speech, temp_audio)
    
    if not os.path.exists(temp_audio):
        raise Exception("Khong the tao file am thanh TTS.")
        
    if status_callback:
        status_callback("3/4", f"🎨 Đang vẽ khung hình Crisp HD 720p...")

    img_obj = create_video_frame(script_data, width=720, height=1280)
    img_obj.save(temp_img)
    
    # Đọc thời lượng âm thanh để ép FFmpeg xuất đúng số giây, tránh lặp vô tận
    try:
        audio_clip = AudioFileClip(temp_audio)
        duration = audio_clip.duration
        audio_clip.close()
    except Exception:
        duration = 15.0

    if status_callback:
        status_callback("4/4", f"⚡ Đang xuất video HD qua Direct FFmpeg CLI ({duration:.1f}s)...")

    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        ffmpeg_exe = "ffmpeg"
    except Exception:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    cmd = [
        ffmpeg_exe, "-y",
        "-loop", "1",
        "-framerate", "1",
        "-i", temp_img,
        "-i", temp_audio,
        "-t", f"{duration:.2f}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-r", "1",
        output_mp4_path
    ]
    print(f"[Direct FFmpeg Engine] Executing render command ({duration:.1f}s)...")
    res = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120
    )
    
    if os.path.exists(temp_img):
        try:
            os.remove(temp_img)
        except Exception:
            pass
    if os.path.exists(temp_audio):
        try:
            os.remove(temp_audio)
        except Exception:
            pass

    if res.returncode != 0:
        err_msg = res.stderr.decode('utf-8', errors='ignore')
        print(f"[!] FFmpeg CLI Error: {err_msg}")
        raise Exception(f"Lỗi render FFmpeg: {err_msg[:100]}")
        
    gc.collect()
    print(f"[Hoan thanh] Da tao xong video CRISP HD sieu toc: {output_mp4_path}")
    return output_mp4_path

if __name__ == "__main__":
    test_topic = "5 Sự thật kỳ lạ về vũ trụ"
    render_tiktok_video(test_topic, "test_output.mp4")
