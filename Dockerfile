# ─────────────────────────────────────────────────────────────
#  Dockerfile cho Render.com (Telegram Bot Controller)
#  Lưu ý: Chrome/Selenium chạy trên GitHub Actions.
#  Render chỉ cần chạy nhẹ telegram_bot.py (Build cực nhanh ~10s).
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Cài đặt Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Mã Nguồn
COPY . .

# Port cho Health Check Server trên Render
EXPOSE 10000

# Chạy Telegram Bot
CMD ["python", "telegram_bot.py"]
