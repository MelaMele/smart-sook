import os
import requests
from flask import Flask, request, jsonify
from supabase import create_client
from datetime import datetime, timezone

app = Flask(__name__)

# 🔑 የEnvironment Variables መረጃዎች
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OWNER_ID = os.environ.get("OWNER_TELEGRAM_ID")

# 🗄️ የSupabase ግንኙነት መክፈቻ ረዳት
def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("🚨 ስህተት: SUPABASE_URL ወይም SUPABASE_KEY አልተጫነም!")
    return create_client(url, key)

# 📊 የዛሬ ሽያጮችን ከSupabase ፈልጎ የሚያመጣ ተግባር
def fetch_today_sales():
    try:
        supabase = get_supabase()
        # የዛሬውን ቀን በ ISO ፎርማት መውሰድ (YYYY-MM-DD)
        today = datetime.now(timezone.utc).date().isoformat()
        
        # 'sales' ከሚለው ሰንጠረዥ ላይ የዛሬ ሽያጮችን መውሰድ
        res = supabase.table("sales").select("amount").gte("created_at", today).execute()
        
        sales_data = res.data
        if not sales_data:
            return f"📊 የዛሬ ሽያጭ ({today})፦ እስካሁን በሲስተሙ ላይ የተመዘገበ አዲስ ሽያጭ የለም።"
            
        total_amount = sum(item.get("amount", 0) for item in sales_data)
        total_count = len(sales_data)
        
        return f"📊 የዕለቱ የሽያጭ መረጃ ({today})፦\n\n💰 ጠቅላላ ገቢ፦ {total_amount:,} ብር\n🛒 የሽያጭ ብዛት፦ {total_count} ጊዜ"
    except Exception as e:
        return f"❌ የሽያጭ መረጃ ከSupabase ላይ ሲነበብ ስህተት አጋጠመ፦ {str(e)}"

# 🚨 ያልተከፈሉ የዱቤ እዳዎችን ከSupabase ፈልጎ የሚያመጣ ተግባር
def fetch_active_debts():
    try:
        supabase = get_supabase()
        # 'debts' ሰንጠረዥ ውስጥ ስታተሳቸው 'unpaid' (ያልተከፈለ) የሆኑትን መውሰድ
        res = supabase.table("debts").select("customer_name, amount").eq("status", "unpaid").execute()
        
        debt_data = res.data
        if not debt_data:
            return "🟢 የዱቤ መረጃ፡ በአሁኑ ሰዓት ያልተሰበሰበ ምንም የዱቤ እዳ የለም!"
            
        total_debt = sum(item.get("amount", 0) for item in debt_data)
        
        report = "🚨 ያልተሰበሰቡ የዱቤ/እዳ መዝገቦች ማጠቃለያ፦\n\n"
        for index, item in enumerate(debt_data, 1):
            report += f"{index}. {item['customer_name']} ➡️ {item['amount']:,} ብር\n"
            
        report += f"\n🛑 ጠቅላላ ያልተሰበሰበ እዳ፦ {total_debt:,} ብር"
        return report
    except Exception as e:
        return f"❌ የዱቤ መረጃ ከSupabase ላይ ሲነበብ ስህተት አጋጠመ፦ {str(e)}"

# ✉️ መልዕክት ወደ ቴሌግራም መላኪያ ረዳት (ክትትል ያለው)
def send_telegram_message(chat_id, text):
    if not BOT_TOKEN:
        print("🚨 ሎግ ማስጠንቀቂያ: TELEGRAM_BOT_TOKEN በVercel Environment Variables ውስጥ አልተገኘም!")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    
    try:
        res = requests.post(url, json=payload)
        print(f"📊 የቴሌግራም API ምላሽ ኮድ: {res.status_code}")
        print(f"📊 የቴሌግራም API ምላሽ ዝርዝር: {res.text}")
    except Exception as e:
        print(f"🚨 የኔትወርክ ስህተት (መልዕክት መላክ አልተቻለም): {e}")

# 📬 1. TELEGRAM WEBHOOK HANDLER (ዋናው የቦት መቀበያ መስመር)
@app.route('/api/webhook', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    print(f"📩 አዲስ የቴሌግራም ዌብሁክ ጥያቄ መጥቷል: {update}")

    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        # 🔄 ትዕዛዞችን የመለየት ሎጂክ
        if text == "/start":
            reply_text = "👋 እንኳን ደህና መጡ! የሽያጭ ማስተዳደሪያ ቦቱን በመጠቀም ንግድዎን ያስተዳድሩ::"
            send_telegram_message(chat_id, reply_text)
            
        elif text == "/status":
            reply_text = "🟢 ሰርቨሩ፣ ዌብሳይቱ እና ቦቱ በጥሩ ሁኔታ ላይ ይገኛሉ!"
            send_telegram_message(chat_id, reply_text)
            
        elif text == "/sales":
            # 🔐 የባለቤቱን ማንነት በChat ID ማረጋገጥ
            if not OWNER_ID or str(chat_id) != str(OWNER_ID):
                send_telegram_message(chat_id, "🔒 ይቅርታ፣ ይህንን ሚስጥራዊ የሱቅ መረጃ ለማየት ፈቃድ የለዎትም።")
            else:
                reply_text = fetch_today_sales()
                send_telegram_message(chat_id, reply_text)
                
        elif text == "/debt":
            # 🔐 የባለቤቱን ማንነት በChat ID ማረጋገጥ
            if not OWNER_ID or str(chat_id) != str(OWNER_ID):
                send_telegram_message(chat_id, "🔒 ይቅርታ፣ ይህንን ሚስጥራዊ የዱቤ መረጃ ለማየት ፈቃድ የለዎትም።")
            else:
                reply_text = fetch_active_debts()
                send_telegram_message(chat_id, reply_text)
                
        else:
            reply_text = f"የላኩት መልዕክት ደርሶኛል: '{text}'"
            send_telegram_message(chat_id, reply_text)

    return jsonify({"status": "ok"}), 200

# 🌐 የቪዚተር/የሙከራ ገጽ
@app.route('/')
def home():
    return jsonify({"status": "healthy", "message": "የሽያጭ ማስተዳደሪያ ኤፒአይ እና ቦት በጥሩ ሁኔታ ላይ ናቸው!"})

# ------------------------------------------------------------------
# 🛒 የዌብ አፕ (HTML Web App) ኤፒአይ መንገዶች ወደፊት እዚህ ይቀጥላሉ...
# ለምሳሌ፦ ምርቶችን ለመዘርዘር (@app.route('/api/products') ወዘተ)
# ------------------------------------------------------------------
