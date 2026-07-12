import os
import requests
from flask import Flask, request, jsonify
from supabase import create_client
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# 🔑 የEnvironment Variables ስሞች
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("🚨 ስህተት: SUPABASE_URL ወይም SUPABASE_KEY አልተጫነም!")
    return create_client(url, key)

# 📬 1. TELEGRAM WEBHOOK HANDLER
@app.route('/api/webhook', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    
    # 🔍 የመጣውን መልዕክት በVercel Log ላይ ለማየት (ደህንነቱ የተጠበቀ)
    print(f"📩 አዲስ የቴሌግራም ዌብሁክ ጥያቄ መጥቷል: {update}")

    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text == "/start":
            reply_text = "👋 እንኳን ደህና መጡ! የሽያጭ ማስተዳደሪያ ቦቱ ከVercel እና Supabase ጋር በትክክል ተገናኝቷል::"
            send_telegram_message(chat_id, reply_text)
        elif text == "/status":
            reply_text = "🟢 ሰርቨሩ፣ ዌብሳይቱ እና ቦቱ በጥሩ ሁኔታ ላይ ይገኛሉ!"
            send_telegram_message(chat_id, reply_text)
        else:
            reply_text = f"የላኩት መልዕክት ደርሶኛል: '{text}'"
            send_telegram_message(chat_id, reply_text)

    return jsonify({"status": "ok"}), 200

# ✉️ የተሻሻለ የመልዕክት መላኪያ ረዳት (ችግሩን ሎግ ላይ የሚያሳይ)
def send_telegram_message(chat_id, text):
    if not BOT_TOKEN:
        print("🚨 ሎግ ማስጠንቀቂያ: TELEGRAM_BOT_TOKEN በVercel Environment Variables ውስጥ አልተገኘም! (ባዶ ነው)")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    
    try:
        res = requests.post(url, json=payload)
        # 📊 ቴሌግራም የመለሰውን ውጤት በLogs ላይ ማተም
        print(f"📊 የቴሌግራም API ምላሽ ኮድ: {res.status_code}")
        print(f"📊 የቴሌግራም API ምላሽ ዝርዝር: {res.text}")
    except Exception as e:
        print(f"🚨 የኔትወርክ ስህተት (መልዕክት መላክ አልተቻለም): {e}")


# --- (ሌሎቹ የShop, Products, Sales ኤፒአይ መንገዶች እዚህ ይቀጥላሉ... እንዳሉ ይቆዩ) ---
