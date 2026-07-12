import os
from flask import Flask, request, jsonify
from supabase import create_client, Client
from datetime import datetime, timedelta

app = Flask(__name__)

# 🔑 Supabase Credentials ከአካባቢ ተለዋዋጮች (Env Variables) መጫን
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("🚨 እባክዎ SUPABASE_URL እና SUPABASE_KEY በVercel Environment Variables ላይ ይጫኑ!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🏢 1. SHOP REGISTRATION (ባለቤት ብቻ)
@app.route('/api/shop/register', models=['POST'])
def register_shop():
    data = request.get_json()
    shop_name = data.get('shop_name')
    password = data.get('password')

    try:
        # ቀድሞ የተመዘገበ ተመሳሳይ ሱቅ መኖሩን ማረጋገጥ
        existing = supabase.table('shops').select('*').eq('shop_name', shop_name).execute()
        if existing.data:
            return jsonify({"status": "error", "message": "ይህ የሱቅ ስም ቀድሞ ተይዟል!"}), 400

        # አዲስ ሱቅ መመዝገብ
        supabase.table('shops').insert({"shop_name": shop_name, "password": password}).execute()
        return jsonify({"status": "success", "message": "ሱቅዎ በተሳካ ሁኔታ ተመዝግቧል!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 🔑 2. SHOP LOGIN (ለባለቤትም ለተቀጣሪም)
@app.route('/api/shop/login', models=['POST'])
def login_shop():
    data = request.get_json()
    shop_name = data.get('shop_name')
    password = data.get('password')
    role = data.get('role', 'owner') # 'owner' ወይም 'employee'

    try:
        # የሱቅ ስምና ፓስወርድ ማረጋገጥ
        user = supabase.table('shops').select('*').eq('shop_name', shop_name).eq('password', password).execute()
        if not user.data:
            return jsonify({"status": "error", "message": "የሱቅ ስም ወይም የይለፍ ቃል የተሳሳተ ነው!"}), 401
        
        return jsonify({"status": "success", "message": f"እንኳን ደህና መጡ! መግቢያዎ እንደ {role} ጸድቋል::"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 📦 3. PRODUCTS (GET & POST)
@app.route('/api/products', models=['GET', 'POST'])
def handle_products():
    if request.method == 'POST':
        data = request.get_json()
        try:
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
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    else: # GET Request (ለተቀጣሪው ሊስት ማሳያ)
        shop_name = request.args.get('shop_name')
        try:
            products = supabase.table('products').select('*').eq('shop_name', shop_name).gt('quantity', 0).execute()
            return jsonify(products.data)
        except Exception as e:
            return jsonify([]), 500

# 🛒 4. REGISTER SALE (የተቀጣሪ የሽያጭ መዝገብ)
@app.route('/api/sales', models=['POST'])
def register_sale():
    data = request.get_json()
    product_id = data.get('product_id')
    sold_qty = int(data.get('sold_qty'))
    shop_name = data.get('shop_name')
    price_per_item = float(data.get('price_per_item'))
    total_price = sold_qty * price_per_item

    try:
        # 1. አሁን ያለውን የዕቃ ብዛት (Stock) ማረጋገጥ
        product = supabase.table('products').select('quantity').eq('id', product_id).single().execute()
        current_qty = product.data.get('quantity', 0)

        if current_qty < sold_qty:
            return jsonify({"status": "error", "message": "በቂ ቀሪ ምርት የለም!"}), 400

        # 2. የምርት መጠን መቀነስ (Update Stock)
        new_qty = current_qty - sold_qty
        supabase.table('products').update({"quantity": new_qty}).eq('id', product_id).execute()

        # 3. ሽያጩን መመዝገብ (Insert Sale)
        supabase.table('sales').insert({
            "shop_name": shop_name,
            "product_id": product_id,
            "product_name": data.get('product_name'),
            "sold_qty": sold_qty,
            "price_per_item": price_per_item,
            "total_price": total_price,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        return jsonify({"status": "success", "message": "ሽያጩ በተሳካ ሁኔታ ተመዝግቧል!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 📊 5. OWNER DASHBOARD INSIGHTS
@app.route('/api/owner/dashboard', models=['GET'])
def get_owner_dashboard():
    shop_name = request.args.get('shop_name')
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    two_months_later = (datetime.utcnow() + timedelta(days=60)).strftime('%Y-%m-%d')
    one_week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    try:
        # ሀ. የዛሬ ጠቅላላ ሽያጭ
        sales_today = supabase.table('sales').select('total_price').eq('shop_name', shop_name).gte('created_at', today_str).execute()
        today_sales_total = sum(item.get('total_price', 0) for item in sales_today.data)

        # ለ. የዛሬ ጠቅላላ ወጪ (ከፋይናንስ ቴብል)
        expenses_today = supabase.table('finance').select('amount').eq('shop_name', shop_name).eq('type', 'expense').gte('created_at', today_str).execute()
        today_expenses_total = sum(item.get('amount', 0) for item in expenses_today.data)

        # ሐ. የምርት መቀነስ (ከ 5 በታች የሆኑ)
        low_stock = supabase.table('products').select('name', 'quantity').eq('shop_name', shop_name).lt('quantity', 5).execute()

        # መ. ጊዜያቸው ሊያልፍ 2 ወር የቀራቸው ዕቃዎች
        near_expiry = supabase.table('products').select('name', 'expiry_date').eq('shop_name', shop_name).lte('expiry_date', two_months_later).gte('expiry_date', today_str).execute()

        # ሠ. ዛሬ የተሸጡ የዕቃ ዝርዝሮች
        sold_details = supabase.table('sales').select('product_name', 'sold_qty', 'total_price').eq('shop_name', shop_name).gte('created_at', today_str).execute()
        formatted_sold = [{"name": s['product_name'], "sold_qty": s['sold_qty'], "total_price": s['total_price']} for s in sold_details.data]

        # ረ. ለሳምንት ያልተሸጡ ዕቃዎች (Stale Stock)
        # በ7 ቀን ውስጥ ከተሸጡት ውጪ የሆኑትን ከምርት ማውጫ መለየት
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
            "stale_products": stale_products[:10] # ከፍተኛ 10ዱን ብቻ ለማሳየት
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 💰 6. FINANCE & 📝 7. CREDIT
@app.route('/api/finance', models=['POST'])
def handle_finance():
    data = request.get_json()
    try:
        supabase.table('finance').insert({
            "shop_name": data.get('shop_name'),
            "type": data.get('type'),
            "amount": data.get('amount'),
            "description": data.get('description'),
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/credit', models=['POST'])
def handle_credit():
    data = request.get_json()
    try:
        supabase.table('credit').insert({
            "shop_name": data.get('shop_name'),
            "customer_name": data.get('customer_name'),
            "total_debt": data.get('total_debt'),
            "phone_number": data.get('phone_number'),
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

# Vercel እንዲያነበው አፑን ማስነሳት
if __name__ == '__main__':
    app.run(debug=True)
