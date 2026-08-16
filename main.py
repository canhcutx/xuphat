import json
import os
import threading
import discord  # discord.py-self
from flask import Flask
import requests

TOKEN = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN")
CHANNEL_MAP_RAW = os.getenv("CHANNEL_MAP", "")

CHANNEL_MAP = {}
if CHANNEL_MAP_RAW:
    clean_raw = CHANNEL_MAP_RAW.replace("\n", "").replace(" ", "").strip()
    pairs = clean_raw.split(",")
    for pair in pairs:
        if ":" in pair:
            ch_id, wh_url = pair.split(":", 1)
            try:
                CHANNEL_MAP[int(ch_id)] = wh_url
            except ValueError:
                print(f"⚠️ Channel ID không hợp lệ: {ch_id}")

SINGLE_SOURCE_ID = os.getenv("SOURCE_CHANNEL_ID")
SINGLE_WEBHOOK = os.getenv("WEBHOOK_URL")
if SINGLE_SOURCE_ID and SINGLE_WEBHOOK:
    try:
        CHANNEL_MAP[int(SINGLE_SOURCE_ID)] = SINGLE_WEBHOOK
    except ValueError:
        pass

client = discord.Client()

@client.event
async def on_ready():
    print(f"✅ Selfbot đã đăng nhập thành công dưới tên: {client.user}")
    print(f"📌 Các kênh đang được theo dõi: {list(CHANNEL_MAP.keys())}")

# -------------------------
# Nhận tin nhắn mới
# -------------------------
@client.event
async def on_message(message):
    if message.channel.id not in CHANNEL_MAP:
        return

    webhook_url = CHANNEL_MAP[message.channel.id]
    content = message.content

    # Nối link file/ảnh đính kèm
    if message.attachments:
        for a in message.attachments:
            content += f"\n{a.url}"

    if not content.strip():
        return

    try:
        requests.post(
            webhook_url,
            json={
                "username": message.author.display_name,
                "avatar_url": str(message.author.display_avatar.url),
                "content": content,
            },
            timeout=10
        )
        print(f"✅ ĐÃ LƯU [{message.channel.id}] -> Msg ID: {message.id}")
    except Exception as e:
        print(f"❌ Lỗi gửi Webhook: {e}")

# -------------------------
# Khi người dùng xóa tin nhắn gốc
# -------------------------
@client.event
async def on_message_delete(message):
    # BỎ QUA - KHÔNG XÓA TIN NHẮN TRÊN WEBHOOK ĐỂ LƯU TRỮ VĨNH VIỄN
    if message.channel.id in CHANNEL_MAP:
        print(f"🛡️ Tin nhắn ID {message.id} bị xóa ở kênh gốc nhưng đã được giữ lại trên Webhook.")

# -------------------------
# Web Server Keep-Alive
# -------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Archive Selfbot Mirror is Alive 24/7!"

def run_bot():
    if TOKEN:
        client.run(TOKEN)
    else:
        print("❌ LỖI: Chưa cài đặt TOKEN!")

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
