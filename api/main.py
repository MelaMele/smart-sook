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
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text == "/start":
            reply_text = "👋 እንኳን ደህና መጡ! የሽያጭ ማስተዳደሪያ ቦቱ ከVercel እና Supabase ጋር በትክክል ተገናኝቷል::\n\nበዌብ ገፅ ላይ የሚልኩት ትዕዛዝም እዚህ ይደርሳል!"
            send_telegram_message(chat_id, reply_text)
        elif text == "/status":
            reply_text = "🟢 ሰርቨሩ፣ ዌብሳይቱ እና ቦቱ በጥሩ ሁኔታ ላይ ይገኛሉ!"
            send_telegram_message(chat_id, reply_text)
        else:
            reply_text = f"የላኩት መልዕክት ደርሶኛል: '{text}'\nየእርስዎ የቴሌግራም መለያ ቁጥር (Chat ID): `{chat_id}` ነው:: ይህንን ቁጥር ማዘዣ ገፁ ላይ መጠቀም ይችላሉ::"
            send_telegram_message(chat_id, reply_text)

    return jsonify({"status": "ok"}), 200

def send_telegram_message(chat_id, text):
    if not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")

# 💳 2. ዌብ ገፅ ማገናኛ - የደንበኛ እዳ መፈለጊያ (NEW)
@app.route('/api/customer/debt', methods=['GET'])
def check_customer_debt():
    name = request.args.get('name')
    if not name:
        return jsonify({"status": "error", "message": "ስም ያስፈልጋል"}), 400
    try:
        supabase = get_supabase()
        # በ credit ሰንጠረዥ ውስጥ በደንበኛ ስም መፈለግ
        result = supabase.table('credit').select('total_debt').eq('customer_name', name).execute()
        if result.data:
            debt = result.data[0].get('total_debt', 0)
            return jsonify({"status": "success", "debt": debt})
        return jsonify({"status": "success", "debt": 0, "message": "የለብዎትም"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 🛍️ 3. ዌብ ገፅ ማገናኛ - አዲስ ትዕዛዝ መቀበያ እና በቦት ማሳወቂያ (NEW)
@app.route('/api/customer/order', methods=['POST'])
def place_customer_order():
    data = request.get_json()
    customer_name = data.get('customer_name')
    telegram_id = data.get('telegram_id')
    product_name = data.get('product_name')
    quantity = data.get('quantity')
    note = data.get('note', '')

    try:
        supabase = get_supabase()
        # ማስታወሻ፡ በSupabase ላይ 'orders' የሚል ሰንጠረዥ አስቀድሞ መኖሩን ያረጋግጡ
        supabase.table('orders').insert({
            "customer_name": customer_name,
            "telegram_id": telegram_id,
            "product_name": product_name,
            "quantity": quantity,
            "note": note,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()

        # 🔥 ቦቱ በራስ-ሰር ለደንበኛው ቴሌግራም ላይ የትዕዛዝ ማረጋገጫ ይልካል!
        if telegram_id:
            msg = f"🛍️ *አዲስ ትዕዛዝ በተሳካ ሁኔታ ደርሶናል!*\n\n👤 *ስም:* {customer_name}\n📦 *ዕቃ:* {product_name}\n🔢 *ብዛት:* {quantity}\n📝 *ማስታወሻ:* {note}\n\nእናመሰግናለን!"
            send_telegram_message(telegram_id, msg)

        return jsonify({"status": "success", "message": "ትዕዛዝዎ ደርሷል!"})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500

# 🏢 4. SHOP REGISTRATION & LOGIN
@app.route('/api/shop/register', methods=['POST'])
def register_shop():
    data = request.get_json()
    shop_name = data.get('shop_name')
    password = data.get('password')
    try:
        supabase = get_supabase()
        existing = supabase.table('shops').select('*').eq('shop_name', shop_name).execute()
        if existing.data:
            return jsonify({"status": "error", "message": "ይህ የሱቅ ስም ቀድሞ ተይዟል!"}), 400
        supabase.table('shops').insert({"shop_name": shop_name, "password": password}).execute()
        return jsonify({"status": "success", "message": "ሱቅዎ በተሳካ ሁኔታ ተመዝግቧል!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/shop/login', methods=['POST'])
def login_shop():
    data = request.get_json()
    shop_name = data.get('shop_name')
    password = data.get('password')
    role = data.get('role', 'owner')
    try:
        supabase = get_supabase()
        user = supabase.table('shops').select('*').eq('shop_name', shop_name).eq('password', password).execute()
        if not user.data:
            return jsonify({"status": "error", "message": "የሱቅ ስም ወይም የይለፍ ቃል የተሳሳተ ነው!"}), 401
        return jsonify({"status": "success", "message": f"እንኳን ደህና መጡ! መግቢያዎ እንደ {role} ጸድቋል::"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 📦 5. PRODUCTS (GET & POST)
@app.route('/api/products', methods=['GET', 'POST'])
def handle_products():
    try:
        supabase = get_supabase()
        if request.method == 'POST':
            data = request.get_json()
            supabase.table('products').insert({
                "shop_name": data.get('shop_name'),
                "name": data.get('name'),
                "quantity": data.get('quantity'),
                "barcode": data.get('barcode'),
                "buying_price": data.get('buying_price'),
                "selling_price": data.get('selling_price'),
                "expiry_date": data.get('expiry_date')
            }).execute()
            return jsonify({"status": "success", "message": "ምርቱ በተሳካ ሁኔታ ተመዝግቧል!"})
        else:
            shop_name = request.args.get('shop_name')
            products = supabase.table('products').select('*').eq('shop_name', shop_name).gt('quantity', 0).execute()
            return jsonify(products.data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 🛒 6. REGISTER SALE
@app.route('/api/sales', methods=['POST'])
def register_sale():
    data = request.get_json()
    product_id = data.get('product_id')
    sold_qty = int(data.get('sold_qty'))
    shop_name = data.get('shop_name')
    price_per_item = float(data.get('price_per_item'))
    total_price = sold_qty * price_per_item
    try:
        supabase = get_supabase()
        product = supabase.table('products').select('quantity').eq('id', product_id).single().execute()
        current_qty = product.data.get('quantity', 0)
        if current_qty < sold_qty:
            return jsonify({"status": "error", "message": "በቂ ቀሪ ምርት የለም!"}), 400
        new_qty = current_qty - sold_qty
        supabase.table('products').update({"quantity": new_qty}).eq('id', product_id).execute()
        supabase.table('sales').insert({
            "shop_name": shop_name,
            "product_id": product_id,
            "product_name": data.get('product_name'),
            "sold_qty": sold_qty,
            "price_per_item": price_per_item,
            "total_price": total_price,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return jsonify({"status": "success", "message": "ሽያጩ በተሳካ ሁኔታ ተመዝግቧል!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 📊 7. OWNER DASHBOARD INSIGHTS
@app.route('/api/owner/dashboard', methods=['GET'])
def get_owner_dashboard():
    shop_name = request.args.get('shop_name')
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    two_months_later = (datetime.now(timezone.utc) + timedelta(days=60)).strftime('%Y-%m-%d')
    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        supabase = get_supabase()
        sales_today = supabase.table('sales').select('total_price').eq('shop_name', shop_name).gte('created_at', today_str).execute()
        today_sales_total = sum(item.get('total_price', 0) for item in sales_today.data)
        expenses_today = supabase.table('finance').select('amount').eq('shop_name', shop_name).eq('type', 'expense').gte('created_at', today_str).execute()
        today_expenses_total = sum(item.get('amount', 0) for item in expenses_today.data)
        low_stock = supabase.table('products').select('name', 'quantity').eq('shop_name', shop_name).lt('quantity', 5).execute()
        near_expiry = supabase.table('products').select('name', 'expiry_date').eq('shop_name', shop_name).lte('expiry_date', two_months_later).gte('expiry_date', today_str).execute()
        sold_details = supabase.table('sales').select('product_name', 'sold_qty', 'total_price').eq('shop_name', shop_name).gte('created_at', today_str).execute()
        formatted_sold = [{"name": s['product_name'], "sold_qty": s['sold_qty'], "total_price": s['total_price']} for s in sold_details.data]
        recent_sales = supabase.table('sales').select('product_id').eq('shop_name', shop_name).gte('created_at', one_week_ago).execute()
        sold_ids = set(item['product_id'] for item in recent_sales.data)
        all_products = supabase.table('products').select('id', 'name').eq('shop_name', shop_name).execute()
        stale_products = [{"name": p['name']} for p in all_products.data if p['id'] not in sold_ids]
        return jsonify({
            "today_sales": today_sales_total,
            "today_expenses": today_expenses_total,
            "low_stock": low_stock.data,
            "near_expiry": near_expiry.data,
            "sold_items_details": formatted_sold,
            "stale_products": stale_products[:10]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 💰 8. FINANCE & CREDIT
@app.route('/api/finance', methods=['POST'])
def handle_finance():
    data = request.get_json()
    try:
        supabase = get_supabase()
        supabase.table('finance').insert({
            "shop_name": data.get('shop_name'),
            "type": data.get('type'),
            "amount": data.get('amount'),
            "description": data.get('description'),
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return jsonify({"status": "success"})
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/credit', methods=['POST'])
def handle_credit():
    data = request.get_json()
    try:
        supabase = get_supabase()
        supabase.table('credit').insert({
            "shop_name": data.get('shop_name'),
            "customer_name": data.get('customer_name'),
            "total_debt": data.get('total_debt'),
            "phone_number": data.get('phone_number'),
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return jsonify({"status": "success"})
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
