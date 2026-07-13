import os
import requests
from flask import Flask, request, jsonify
from supabase import create_client
from datetime import datetime, timezone

app = Flask(__name__)

# 🔑 የEnvironment Variables መረጃዎች
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OWNER_ID = os.environ.get("OWNER_TELEGRAM_ID")

# 🗄️ የSupabase ግንኙነት መክፈቻ
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
        today = datetime.now(timezone.utc).date().isoformat()
        res = supabase.table("sales").select("amount").gte("created_at", today).execute()
        
        sales_data = res.data
        if not sales_data:
            return f"📊 የዛሬ ሽያጭ ({today})፦ እስካሁን የተመዘገበ አዲስ ሽያጭ የለም።"
            
        total_amount = sum(item.get("amount", 0) for item in sales_data)
        total_count = len(sales_data)
        
        return f"📊 የዕለቱ የሽያጭ መረጃ ({today})፦\n\n💰 ጠቅላላ ገቢ፦ {total_amount:,} ብር\n🛒 የሽያጭ ብዛት፦ {total_count} ጊዜ"
    except Exception as e:
        return f"❌ የሽያጭ መረጃ ከSupabase ሲነበብ ስህተት አጋጠመ፦ {str(e)}"

# 🚨 ያልተከፈሉ የዱቤ እዳዎችን ከSupabase ፈልጎ የሚያመጣ ተግባር
def fetch_active_debts():
    try:
        supabase = get_supabase()
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
        return f"❌ የዱቤ መረጃ ከSupabase ሲነበብ ስህተት አጋጠመ፦ {str(e)}"

# ✉️ የተሻሻለ መልዕክት መላኪያ (የቁልፍ ማውጫዎችን/Keyboard መደገፍ የሚችል)
def send_telegram_message(chat_id, text, reply_markup=None):
    if not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"🚨 የኔትወርክ ስህተት: {e}")

# 📬 1. TELEGRAM WEBHOOK HANDLER
@app.route('/api/webhook', methods=['POST'])
def telegram_webhook():
    update = request.get_json()

    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        # 👑 ለሱቅ ባለቤቱ ብቻ የሚላክ የቁልፍ ማውጫ (Reply Keyboard)
        owner_keyboard = {
            "keyboard": [
                [{"text": "📊 የዛሬ ሽያጭ"}, {"text": "🚨 የዱቤ መዝገብ"}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False
        }

        if text == "/start":
            if OWNER_ID and str(chat_id) == str(OWNER_ID):
                reply_text = "👋 እንኳን ደህና መጡ ባለቤት! የሽያጭ መቆጣጠሪያ ቁልፎች ከታች ተዘጋጅተውልዎታል።"
                send_telegram_message(chat_id, reply_text, reply_markup=owner_keyboard)
            else:
                reply_text = "👋 እንኳን ደህና መጡ ወደ ዘመናዊ ማከፋፈያ ሱቅ ቦት! ከታች ያለውን «🛍️ ሱቅ ክፈት» ቁልፍ ተጭነው ትዕዛዝ ማቅረብ ይችላሉ።"
                send_telegram_message(chat_id, reply_text)
            
        elif text in ["/sales", "📊 የዛሬ ሽያጭ"]:
            if not OWNER_ID or str(chat_id) != str(OWNER_ID):
                send_telegram_message(chat_id, "🔒 ይቅርታ፣ ይህንን መረጃ ለማየት ፈቃድ የለዎትም።")
            else:
                send_telegram_message(chat_id, fetch_today_sales(), reply_markup=owner_keyboard)
                
        elif text in ["/debt", "🚨 የዱቤ መዝገብ"]:
            if not OWNER_ID or str(chat_id) != str(OWNER_ID):
                send_telegram_message(chat_id, "🔒 ይቅርታ፣ ይህንን መረጃ ለማየት ፈቃድ የለዎት።")
            else:
                send_telegram_message(chat_id, fetch_active_debts(), reply_markup=owner_keyboard)
                
        else:
            send_telegram_message(chat_id, f"የላኩት መልዕክት ደርሶኛል: '{text}'")

    return jsonify({"status": "ok"}), 200

# 🛍️ 2. WEB APP ORDER ENDPOINT (ከHTML ገጹ ላይ ትዕዛዝ መቀበያ)
@app.route('/api/place-order', methods=['POST'])
def place_order():
    try:
        data = request.get_json() or {}
        amount = data.get("amount")
        customer_name = data.get("customer_name", "የዌብ አፕ ደንበኛ")
        
        if not amount:
            return jsonify({"success": False, "error": "የገንዘብ መጠን አልተገለጸም!"}), 400
            
        supabase = get_supabase()
        
        # 1. ሽያጩን በዳታቤዝ መመዝገብ
        supabase.table("sales").insert({"amount": float(amount)}).execute()
        
        # 2. ለሱቅ ባለቤቱ በቴሌግራም ወዲያውኑ ማሳወቅ
        if OWNER_ID:
            alert_text = f"🛒 🎉 አዲስ ትዕዛዝ በዌብ አፕ ተመዝግቧል!\n\n👤 ደንበኛ፦ {customer_name}\n💰 መጠን፦ {amount:,} ብር"
            send_telegram_message(OWNER_ID, alert_text)
            
        return jsonify({"success": True, "message": "ትዕዛዝዎ በስኬት ተመዝግቧል!"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# 🌐 3. የዌብ አፕ (HTML Web App) ገፅን ፈልጎ በቀጥታ ለቴሌግራም የሚያስረክብ መንገድ (ፍፁም አስተማማኝ አቀራረብ)
@app.route('/')
@app.route('/index.html')
def home():
    try:
        # የ index.py ፋይል ያለበትን አቃፊ ማግኘት (ለምሳሌ፦ /api/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # የፕሮጀክቱን ዋና ስር (Root Directory) ማግኘት
        project_root = os.path.dirname(current_dir)
        
        # ፍፁም አስተማማኝ የሆኑ የፋይል መሄጃ መንገዶች (Absolute Paths)
        paths_to_check = [
            os.path.join(project_root, 'public', 'index.html'),
            os.path.join(current_dir, 'public', 'index.html'),
            os.path.join(project_root, 'index.html'),
            os.path.join(current_dir, 'index.html')
        ]
        
        for path in paths_to_check:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
        
        return "⚠️ ስህተት፡ index.html ፋይል በፕሮጀክቱ ውስጥ አልተገኘም! እባክህ በ public ፎልደር ውስጥ መኖሩን አረጋግጥ።", 404
    except Exception as e:
        return f"❌ የሰርቨር ስህተት አጋጠመ፦ {str(e)}", 500
