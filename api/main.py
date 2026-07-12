import os
import requests  # 🌐 ለቴሌግራም መልዕክት መላኪያ የተጨመረ
from flask import Flask, request, jsonify
from supabase import create_client
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# 🔑 የEnvironment Variables ስሞች
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# 🔑 የሱፓቤዝ ክላይንትን በደህንነት መንገድ መጥሪያ ዘዴ
def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("🚨 ስህተት: SUPABASE_URL ወይም SUPABASE_KEY አልተጫነም!")
    return create_client(url, key)

# 📬 1. TELEGRAM WEBHOOK HANDLER (ቦቱ መልዕክት የሚቀበልበት እና ምላሽ የሚሰጥበት)
@app.route('/api/webhook', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    
    # መልዕክት መኖሩን ማረጋገጥ
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        # 🤖 የቦቱ ትዕዛዞች ማስተናገጃ (እዚህ ጋር የፈለግከውን የቦት ሎጂክ መጨመር ትችላለህ)
        if text == "/start":
            reply_text = "👋 እንኳን ደህና መጡ! የሽያጭ ማስተዳደሪያ ቦቱ ከVercel እና Supabase ጋር በትክክል ተገናኝቷል::\n\nእባክዎ ትዕዛዝ ያቅርቡ::"
            send_telegram_message(chat_id, reply_text)
            
        elif text == "/status":
            reply_text = "🟢 ሰርቨሩ እና ቦቱ በጥሩ ሁኔታ ላይ ይገኛሉ!"
            send_telegram_message(chat_id, reply_text)
            
        else:
            reply_text = f"የላኩት መልዕክት ደርሶኛል: '{text}'\nሙሉ የቦት ስራዎችን እዚህ ላይ ማስተካከል እንችላለን::"
            send_telegram_message(chat_id, reply_text)

    return jsonify({"status": "ok"}), 200

# ✉️ የቴሌግራም መልዕክት መላኪያ ረዳት ፈንክሽን
def send_telegram_message(chat_id, text):
    if not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")

# 🌐 የሙከራ ገጽ
@app.route('/')
def home():
    return jsonify({"status": "healthy", "message": "የሽያጭ ማስተዳደሪያ ኤፒአይ እና ቦት በተሳካ ሁኔታ እየሰሩ ነው!"})

# 🏢 2. SHOP REGISTRATION
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

# 🔑 3. SHOP LOGIN
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

# 📦 4. PRODUCTS (GET & POST)
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

# 🛒 5. REGISTER SALE
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

# 📊 6. OWNER DASHBOARD INSIGHTS
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

# 💰 7. FINANCE & 📝 8. CREDIT
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
