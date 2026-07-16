import os
import requests
from flask import Flask, request, jsonify
from supabase import create_client
from datetime import datetime, timezone

app = Flask(__name__)

# 🔑 የEnvironment Variables መረጃዎች
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
OWNER_ID = os.environ.get("OWNER_TELEGRAM_ID")

# 🗄️ የSupabase ግንኙነት መክፈቻ
def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("🚨 ስህተት: SUPABASE_URL ወይም SUPABASE_KEY አልተጫነም!")
    return create_client(url, key)

# 📊 የዛሬ ሽያጮችን ከSupabase (ከ finances ቴብል) ፈልጎ የሚያመጣ ተግባር
def fetch_today_sales():
    try:
        supabase = get_supabase()
        today = datetime.now(timezone.utc).date().isoformat()
        
        # አዲሱን የ 'finances' ቴብል ስም እንጠቀማለን
        res = supabase.table("finances").select("amount").eq("type", "income").gte("created_at", today).execute()
        
        sales_data = res.data
        if not sales_data:
            return f"📊 የዛሬ ሽያጭ ({today})፦ እስካሁን የተመዘገበ አዲስ ሽያጭ የለም።"
            
        total_amount = sum(float(item.get("amount", 0)) for item in sales_data)
        total_count = len(sales_data)
        
        return f"📊 የዕለቱ የሽያጭ መረጃ ({today})፦\n\n💰 ጠቅላላ ገቢ፦ {total_amount:,} ብር\n🛒 የሽያጭ ብዛት፦ {total_count} ጊዜ"
    except Exception as e:
        return f"❌ የሽያጭ መረጃ ከSupabase ሲነበብ ስህተት አጋጠመ፦ {str(e)}"

# 🚨 ያልተከፈሉ የዱቤ እዳዎችን ከSupabase (ከ credits ቴብል) ፈልጎ የሚያመጣ ተግባር
def fetch_active_debts():
    try:
        supabase = get_supabase()
        
        # አዲሱን የ 'credits' ቴብል ስም እንጠቀማለን
        res = supabase.table("credits").select("customer_name, total_debt").gt("total_debt", 0).execute()
        
        debt_data = res.data
        if not debt_data:
            return "🟢 የዱቤ መረጃ፡ በአሁኑ ሰዓት ያልተሰበሰበ ምንም የዱቤ እዳ የለም!"
            
        total_debt = sum(float(item.get("total_debt", 0)) for item in debt_data)
        report = "🚨 ያልተሰበሰቡ የዱቤ/እዳ መዝገቦች ማጠቃለያ፦\n\n"
        for index, item in enumerate(debt_data, 1):
            report += f"{index}. {item['customer_name']} ➡️ {item['total_debt']:,} ብር\n"
            
        report += f"\n🛑 ጠቅላላ ያልተሰበሰበ እዳ፦ {total_debt:,} ብር"
        return report
    except Exception as e:
        return f"❌ የዱቤ መረጃ ከSupabase ሲነበብ ስህተት አጋጠመ፦ {str(e)}"

# ✉️ የተሻሻለ መልዕክት መላኪያ
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

        # 👑 ለሱቅ ባለቤቱ የሚላክ የቁልፍ ማውጫ (Reply Keyboard)
        owner_keyboard = {
            "keyboard": [
                [{"text": "📊 የዛሬ ሽያጭ"}, {"text": "🚨 የዱቤ መዝገብ"}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False
        }

        # 🛍️ ለደንበኞች የዌብ አፕ መክፈቻ ቁልፍ (ወደ /customer ይመራል)
        app_url = f"https://{request.host}/customer" 
        customer_keyboard = {
            "inline_keyboard": [
                [{"text": "🚀 ስማርት ሱቅን ክፈት (Open App)", "web_app": {"url": app_url}}]
            ]
        }

        if text == "/start":
            if OWNER_ID and str(chat_id) == str(OWNER_ID):
                reply_text = "👋 እንኳን ደህና መጡ ባለቤት! የሽያጭ መቆጣጠሪያ ቁልፎች ከታች ተዘጋጅተውልዎታል።"
                send_telegram_message(chat_id, reply_text, reply_markup=owner_keyboard)
            else:
                reply_text = "👋 እንኳን ደህና መጡ ወደ ዘመናዊ ማከፋፈያ ሱቅ ቦት! ከታች ያለውን «🚀 ስማርት ሱቅን ክፈት» ቁልፍ ተጭነው መግባት ይችላሉ።"
                send_telegram_message(chat_id, reply_text, reply_markup=customer_keyboard)
            
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

# 👥 2. የደንበኛ እዳ ፍለጋ ኤፒአይ (ከHTML ገጹ ላይ የሚጠራው)
@app.route('/api/customer/debt', methods=['GET'])
def get_customer_debt():
    try:
        name = request.args.get('name', '').strip()
        if not name:
            return jsonify({"status": "error", "message": "ስም አልተገለጸም"}), 400
            
        supabase = get_supabase()
        res = supabase.table("credits").select("total_debt").eq("customer_name", name).execute()
        
        if res.data:
            debt_amount = float(res.data[0].get("total_debt", 0))
            return jsonify({"status": "success", "debt": debt_amount}), 200
        else:
            return jsonify({"status": "not_found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 🛍️ 3. አዲስ ትዕዛዝ መቀበያ ኤፒአይ (ከHTML ገጹ ላይ የሚጠራው)
@app.route('/api/customer/order', methods=['POST'])
def place_customer_order():
    try:
        data = request.get_json() or {}
        customer_name = data.get("customer_name")
        telegram_id = data.get("telegram_id")
        product_name = data.get("product_name")
        quantity = data.get("quantity", 1)
        note = data.get("note", "")
        
        if not customer_name or not telegram_id or not product_name:
            return jsonify({"status": "error", "detail": "እባክዎ ሁሉንም አስፈላጊ መረጃዎች ያስገቡ!"}), 400
            
        # 1. ለባለቤቱ ወዲያውኑ በቴሌግራም ማሳወቅ (Real-time Notification)
        if OWNER_ID:
            alert_text = (
                f"🛒 🎉 **አዲስ ትዕዛዝ ደርሷል!**\n\n"
                f"👤 **ደንበኛ:** {customer_name}\n"
                f"🆔 **Telegram ID:** {telegram_id}\n"
                f"📦 **ዕቃ:** {product_name}\n"
                f"🔢 **ብዛት:** {quantity}\n"
                f"📝 **ማስታወሻ:** {note if note else 'የለም'}"
            )
            send_telegram_message(OWNER_ID, alert_text)
            
        return jsonify({"status": "success", "message": "ትዕዛዝዎ በስኬት ደርሷል!"}), 200
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500

# 🌐 4. የባለሱቅ መግቢያ ገፅ (index.html) አቀራረብ
@app.route('/')
@app.route('/index.html')
def home():
    return serve_html_file('index.html')

# 👥 5. የደንበኛ ገፅ (customer.html) አቀራረብ
@app.route('/customer')
@app.route('/customer.html')
def customer_home():
    return serve_html_file('customer.html')

# 📂 የ HTML ፋይሎችን በስርዓት ፈልጎ ለማቅረብ የሚረዳ የጋራ ተግባር
def serve_html_file(filename):
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        
        paths_to_check = [
            os.path.join(project_root, 'public', filename),
            os.path.join(current_dir, 'public', filename),
            os.path.join(project_root, filename),
            os.path.join(current_dir, filename),
            os.path.join(project_root, 'api', filename),
            os.path.join(current_dir, 'api', filename)
        ]
        
        for path in paths_to_check:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
        
        return f"⚠️ ስህተት፦ {filename} ፋይል በፕሮጀክቱ ውስጥ አልተገኘም!", 404
    except Exception as e:
        return f"❌ የሰርቨር ስህተት አጋጠመ፦ {str(e)}", 500
