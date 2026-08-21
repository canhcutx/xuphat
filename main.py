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

# Lưu ánh xạ: original_message_id -> {"webhook_url": str, "webhook_msg_id": str}
# Lưu ý: Nếu khởi động lại bot/server, các tin nhắn cũ trước đó sẽ không còn lưu trong RAM
MESSAGE_MAP = {}

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
        # Thêm ?wait=true để Discord trả về thông tin tin nhắn vừa tạo trên Webhook
        wh_post_url = webhook_url.split("?")[0] + "?wait=true"
        
        resp = requests.post(
            wh_post_url,
            json={
                "username": message.author.display_name,
                "avatar_url": str(message.author.display_avatar.url),
                "content": content,
            },
            timeout=10
        )
        
        if resp.status_code in [200, 201]:
            data = resp.json()
            wh_msg_id = data.get("id")
            if wh_msg_id:
                # Lưu lại ID để phục vụ việc sửa tin sau này
                MESSAGE_MAP[message.id] = {
                    "webhook_url": webhook_url.split("?")[0],
                    "webhook_msg_id": wh_msg_id
                }
            print(f"✅ ĐÃ LƯU [{message.channel.id}] -> Msg ID: {message.id} (Webhook Msg ID: {wh_msg_id})")
        else:
            print(f"⚠️ Webhook trả lời mã lỗi {resp.status_code}: {resp.text}")

    except Exception as e:
        print(f"❌ Lỗi gửi Webhook: {e}")

# -------------------------
# Khi người dùng chỉnh sửa tin nhắn gốc
# -------------------------
@client.event
async def on_message_edit(before, after):
    if after.channel.id not in CHANNEL_MAP:
        return

    # Nếu không có trong danh sách lưu tạm (ví dụ bot vừa restart hoặc gửi trước khi bot chạy)
    if after.id not in MESSAGE_MAP:
        print(f"⚠️ Không tìm thấy Webhook Message ID cho tin nhắn gốc {after.id} để cập nhật.")
        return

    mapping = MESSAGE_MAP[after.id]
    webhook_url = mapping["webhook_url"]
    webhook_msg_id = mapping["webhook_msg_id"]

    new_content = after.content
    if after.attachments:
        for a in after.attachments:
            new_content += f"\n{a.url}"

    if not new_content.strip():
        return

    edit_url = f"{webhook_url}/messages/{webhook_msg_id}"

    try:
        resp = requests.patch(
            edit_url,
            json={
                "content": new_content
            },
            timeout=10
        )
        if resp.status_code == 200:
            print(f"✏️ ĐÃ CẬP NHẬT tin nhắn ID {after.id} -> Webhook Msg ID: {webhook_msg_id}")
        else:
            print(f"❌ Lỗi cập nhật Webhook (HTTP {resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"❌ Lỗi gửi yêu cầu PATCH: {e}")

# -------------------------
# Khi người dùng xóa tin nhắn gốc
# -------------------------
@client.event
async def on_message_delete(message):
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
