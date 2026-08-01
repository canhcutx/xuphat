import json
import os
import threading
import discord  # Gói discord.py-self
from flask import Flask
import requests

# Lấy Token từ biến môi trường
TOKEN = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN")

# Lấy cấu hình các cặp kênh nguồn -> webhook đích
# Ví dụ cấu hình: "CHANNEL_ID_1:WEBHOOK_URL_1,CHANNEL_ID_2:WEBHOOK_URL_2"
CHANNEL_MAP_RAW = os.getenv("CHANNEL_MAP", "")

# Chuyển đổi chuỗi CHANNEL_MAP thành dictionary { channel_id_int: webhook_url_str }
CHANNEL_MAP = {}
if CHANNEL_MAP_RAW:
    pairs = CHANNEL_MAP_RAW.split(",")
    for pair in pairs:
        if ":" in pair:
            ch_id, wh_url = pair.strip().split(":", 1)
            try:
                CHANNEL_MAP[int(ch_id.strip())] = wh_url.strip()
            except ValueError:
                print(f"⚠️ Channel ID không hợp lệ: {ch_id}")

# Nếu vẫn muốn hỗ trợ cấu hình kiểu cũ (1 kênh)
SINGLE_SOURCE_ID = os.getenv("SOURCE_CHANNEL_ID")
SINGLE_WEBHOOK = os.getenv("WEBHOOK_URL")
if SINGLE_SOURCE_ID and SINGLE_WEBHOOK:
    try:
        CHANNEL_MAP[int(SINGLE_SOURCE_ID)] = SINGLE_WEBHOOK
    except ValueError:
        pass

MAP_FILE = "message_map.json"

# -------------------------
# Load / Save mapping ID tin nhắn
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

client = discord.Client()

@client.event
async def on_ready():
    print(f"✅ Selfbot đã đăng nhập thành công dưới tên: {client.user}")
    print(f"📌 Đang theo dõi {len(CHANNEL_MAP)} kênh cấu hình.")

@client.event
async def on_message(message):
    # Kiểm tra xem kênh nhắn tin có nằm trong danh sách theo dõi không
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
        r = requests.post(
            webhook_url + "?wait=true",
            json={
                "username": message.author.display_name,
                "avatar_url": str(message.author.display_avatar.url),
                "content": content,
            },
            timeout=10
        )

        if r.status_code in [200, 204]:
            data = r.json()
            message_map[str(message.id)] = {
                "webhook_msg_id": data["id"],
                "webhook_url": webhook_url
            }
            save_map()
            print(f"FORWARD [{message.channel.id}] -> Msg ID: {message.id}")
    except Exception as e:
        print(f"❌ Lỗi gửi Webhook: {e}")

@client.event
async def on_message_edit(before, after):
    if before.channel.id not in CHANNEL_MAP:
        return

    source_id = str(before.id)
    if source_id not in message_map:
        return

    map_info = message_map[source_id]
    webhook_msg_id = map_info["webhook_msg_id"]
    webhook_url = map_info["webhook_url"]

    content = after.content
    if after.attachments:
        for a in after.attachments:
            content += f"\n{a.url}"

    try:
        requests.patch(
            f"{webhook_url}/messages/{webhook_msg_id}",
            json={"content": content},
            timeout=10
        )
        print(f"EDIT [{before.channel.id}] -> Msg ID: {before.id}")
    except Exception as e:
        print(f"❌ Lỗi sửa Webhook: {e}")

@client.event
async def on_message_delete(message):
    if message.channel.id not in CHANNEL_MAP:
        return

    source_id = str(message.id)
    if source_id not in message_map:
        return

    map_info = message_map[source_id]
    webhook_msg_id = map_info["webhook_msg_id"]
    webhook_url = map_info["webhook_url"]

    try:
        requests.delete(f"{webhook_url}/messages/{webhook_msg_id}", timeout=10)
        del message_map[source_id]
        save_map()
        print(f"DELETE [{message.channel.id}] -> Msg ID: {message.id}")
    except Exception as e:
        print(f"❌ Lỗi xóa Webhook: {e}")

# -------------------------
# Web Server Keep-Alive
# -------------------------

app = Flask(__name__)

@app.route("/")
def home():
    return "Multi-Channel Selfbot Mirror is Alive 24/7!"

def run_bot():
    if TOKEN:
        client.run(TOKEN)
    else:
        print("❌ LỖI: Chưa cài đặt TOKEN biến môi trường!")

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
