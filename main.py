import json
import os
import threading
import discord  # Cần cài đặt gói: discord.py-self
from flask import Flask
import requests

# Lấy Token & Webhook từ biến môi trường
TOKEN = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Ép kiểu int cho SOURCE_CHANNEL_ID
RAW_CHANNEL_ID = os.getenv("SOURCE_CHANNEL_ID")
SOURCE_CHANNEL_ID = int(RAW_CHANNEL_ID) if RAW_CHANNEL_ID else None

MAP_FILE = "message_map.json"

# -------------------------
# Load / Save mapping
# -------------------------

def load_map():
    if os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Lỗi đọc file map: {e}")
    return {}

def save_map():
    try:
        with open(MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(message_map, f, indent=2)
    except Exception as e:
        print(f"Lỗi lưu file map: {e}")

message_map = load_map()

# -------------------------
# Discord Selfbot Setup
# -------------------------

# Đối với Selfbot (User Account), dùng Client cơ bản
client = discord.Client()

@client.event
async def on_ready():
    print(f"✅ Selfbot đã đăng nhập thành công dưới tên: {client.user}")

@client.event
async def on_message(message):
    # Lọc kênh tin nhắn
    if not SOURCE_CHANNEL_ID or message.channel.id != SOURCE_CHANNEL_ID:
        return

    content = message.content

    # Nối link các tệp đính kèm (ảnh, file) vào nội dung tin nhắn
    if message.attachments:
        for a in message.attachments:
            content += f"\n{a.url}"

    # Nếu không có nội dung lẫn file thì không gửi
    if not content.strip():
        return

    if WEBHOOK_URL:
        try:
            r = requests.post(
                WEBHOOK_URL + "?wait=true",
                json={
                    "username": message.author.display_name,
                    "avatar_url": str(message.author.display_avatar.url),
                    "content": content,
                },
                timeout=10
            )

            if r.status_code in [200, 204]:
                data = r.json()
                message_map[str(message.id)] = data["id"]
                save_map()
                print(f"FORWARD -> Msg ID: {message.id}")
        except Exception as e:
            print(f"❌ Lỗi gửi Webhook: {e}")

@client.event
async def on_message_edit(before, after):
    if not SOURCE_CHANNEL_ID or before.channel.id != SOURCE_CHANNEL_ID:
        return

    source_id = str(before.id)
    if source_id not in message_map:
        return

    webhook_msg_id = message_map[source_id]
    content = after.content

    if after.attachments:
        for a in after.attachments:
            content += f"\n{a.url}"

    if WEBHOOK_URL:
        try:
            requests.patch(
                f"{WEBHOOK_URL}/messages/{webhook_msg_id}",
                json={"content": content},
                timeout=10
            )
            print(f"EDIT -> Msg ID: {before.id}")
        except Exception as e:
            print(f"❌ Lỗi sửa Webhook: {e}")

@client.event
async def on_message_delete(message):
    if not SOURCE_CHANNEL_ID or message.channel.id != SOURCE_CHANNEL_ID:
        return

    source_id = str(message.id)
    if source_id not in message_map:
        return

    webhook_msg_id = message_map[source_id]

    if WEBHOOK_URL:
        try:
            requests.delete(f"{WEBHOOK_URL}/messages/{webhook_msg_id}", timeout=10)
            del message_map[source_id]
            save_map()
            print(f"DELETE -> Msg ID: {message.id}")
        except Exception as e:
            print(f"❌ Lỗi xóa Webhook: {e}")

# -------------------------
# Web Server Keep-Alive (Dành cho Render)
# -------------------------

app = Flask(__name__)

@app.route("/")
def home():
    return "Selfbot Mirror is Alive 24/7!"

def run_bot():
    if TOKEN:
        # discord.py-self chạy bằng User Token
        client.run(TOKEN)
    else:
        print("❌ LỖI: Chưa cài đặt TOKEN biến môi trường!")

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
