import os
from datetime import date, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update

app = FastAPI(title="Smart Sook Multi-Shop Cloud API")

# --- 1. CONFIGURATION & CLIENTS ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# 🔐 የባለሱቁ መግቢያ ሚስጥር ቃል (በ Vercel ላይ ካልተጫነ ዲፎልት '1234' ይሆናል)
SHOP_PASSWORD = os.getenv("SHOP_PASSWORD", "1234") 

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

# 🔄 የባለሱቃትን ጊዜያዊ የመግቢያ ሁኔታ መከታተያ (Session Dictionary)
# { chat_id: {"step": "awaiting_shop_name", "shop_name": "xyz"} }
user_sessions = {}

# --- 2. PYDANTIC SCHEMAS ---
class ProductCreate(BaseModel):
    name: str
    quantity: int
    barcode: str | None = None
    buying_price: float
    selling_price: float
    expiry_date: str
    shop_name: str

class TransferCreate(BaseModel):
    product_name: str
    quantity: int
    shop_name: str

class CreditCreate(BaseModel):
    customer_name: str
    total_debt: float
    phone_number: str | None = None
    shop_name: str

class FinanceCreate(BaseModel):
    type: str
    amount: float
    description: str
    shop_name: str

class OrderCreate(BaseModel):
    customer_name: str
    telegram_id: str
    product_name: str
    quantity: int
    note: str

# --- 3. 🎯 NEW MAIN PORTAL BUTTONS (ቦቱ ሲከፈት የሚመጡ 2 በተኖች) ---
def get_portal_menu(chat_id):
    markup = InlineKeyboardMarkup()
    
    # 🏢 የባለሱቅ በተን - መጀመሪያ ወደ ጽሑፍ ሎጂክ ይመራዋል (ቀጥታ ሚኒ አፕ አይከፍትም)
    markup.row(InlineKeyboardButton("🏢 የባለሱቅ ገጽ (Login)", callback_data="shop_login"))
    
    # 🛍️ የደንበኞች በተን - በቀጥታ የደንበኛ ማዘዣ ዌብ አፕ ይከፍታል
    markup.row(InlineKeyboardButton("🛍️ የደንበኞች ገጽ (Direct Access)", web_app=telebot.types.WebAppInfo(url="https://smart-sook.vercel.app/customer")))
    
    return markup

# 🔐 ባለሱቁ በስኬት ሲገባ ብቻ የሚከፈትለት የባለሱቅ ልዩ ሚኒ አፕ በተን
def get_authenticated_shop_menu(shop_name):
    markup = InlineKeyboardMarkup()
    # የሱቁን ስም በ URL parameter አሳልፈን እንልካለን
    url = f"https://smart-sook.vercel.app/?shop={shop_name}"
    markup.row(InlineKeyboardButton(f"🚀 ወደ {shop_name} ማስተዳደሪያ ግባ", web_app=telebot.types.WebAppInfo(url=url)))
    return markup

# --- 4. TELEGRAM BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    if chat_id in user_sessions:
        del user_sessions[chat_id] # ሴሽኑን ማፅዳት
        
    bot.send_message(
        chat_id, 
        "እንኳን ወደ ስማርት ሱቅ ማስተዳደሪያ ቦት በሰላም መጡ! 👋\n\nእባክዎ ከታች ካሉት አማራጮች አንዱን ይምረጡ፦", 
        reply_markup=get_portal_menu(chat_id)
    )

# 🏢 የባለሱቅ መግቢያ ሲጫን
@bot.callback_query_handler(func=lambda call: call.data == "shop_login")
def shop_login_start(call):
    chat_id = call.message.chat.id
    user_sessions[chat_id] = {"step": "awaiting_shop_name"}
    bot.send_message(chat_id, "📝 እባክዎ የሱቅዎን ወይም የማከፋፈያዎን ስም ያስገቡ፦")
    bot.answer_callback_query(call.id)

# 📝 የባለሱቅ ስምና ፓስወርድ መቀበያ ሎጂክ
@bot.message_handler(func=lambda message: message.chat.id in user_sessions)
def handle_login_steps(message):
    chat_id = message.chat.id
    step = user_sessions[chat_id].get("step")
    
    if step == "awaiting_shop_name":
        user_sessions[chat_id]["shop_name"] = message.text.strip()
        user_sessions[chat_id]["step"] = "awaiting_password"
        bot.send_message(chat_id, "🔐 አሁን ደግሞ ሚስጥር ቃሉን (Password) ያስገቡ፦")
        
    elif step == "awaiting_password":
        entered_password = message.text.strip()
        shop_name = user_sessions[chat_id]["shop_name"]
        
        if entered_password == SHOP_PASSWORD:
            bot.send_message(
                chat_id, 
                f"✅ ማረጋገጫው ተሳክቷል! እንኳን ደህና መጡ የ {shop_name} ባለቤት።\n\nወደ ማስተዳደሪያው ለመግባት ከታች ያለውን አዝራር ይጫኑ፦", 
                reply_markup=get_authenticated_shop_menu(shop_name)
            )
            # ከገባ በኋላ ሴሽኑን እናጠፋዋለን
            del user_sessions[chat_id]
        else:
            bot.send_message(
                chat_id, 
                "❌ የተሳሳተ ሚስጥር ቃል ነው! እባክዎ እንደገና ይሞክሩ።\n/start ን ተጭነው ከእጅግ ይጀምሩ።"
            )
            del user_sessions[chat_id]

# --- 5. FASTAPI ROUTES ---
@app.get("/", response_class=HTMLResponse)
def read_root():
    try:
        with open("api/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h3>index.html አልተገኘም</h3>"

@app.get("/customer", response_class=HTMLResponse)
def read_customer_root():
    try:
        with open("api/customer.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h3>customer.html አልተገኘም</h3>"

@app.get("/api/customer/products")
def get_active_products(shop_name: str | None = None):
    try:
        if shop_name:
            data = supabase.table("products").select("name, selling_price").eq("shop_name", shop_name).execute()
        else:
            data = supabase.table("products").select("name, selling_price").execute()
        return {"status": "success", "products": data.data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/customer/debt")
def get_customer_debt(name: str, shop_name: str | None = None):
    try:
        query = supabase.table("customers_credit").select("total_debt").eq("customer_name", name)
        if shop_name:
            query = query.eq("shop_name", shop_name)
        data = query.execute()
        debt = data.data[0]['total_debt'] if data.data else 0.0
        return {"status": "success", "debt": debt}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/customer/order")
def create_customer_order(order: OrderCreate):
    try:
        ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
        msg = f"🔔 **አዲስ የደንበኛ ትዕዛዝ ደርሷል!** 🛒\n\n👤 ደንበኛ፦ {order.customer_name}\n📦 ምርት፦ {order.product_name}\n🔢 ብዛት፦ {order.quantity}\n📝 ማስታወሻ፦ {order.note}\n"
        if ADMIN_CHAT_ID:
            bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/products")
def create_product(product: ProductCreate):
    try:
        existing = supabase.table("warehouse_stock").select("id, quantity").eq("product_name", product.name).eq("shop_name", product.shop_name).execute()
        if existing.data:
            new_qty = existing.data[0]['quantity'] + product.quantity
            supabase.table("warehouse_stock").update({"quantity": new_qty}).eq("id", existing.data[0]['id']).execute()
        else:
            supabase.table("warehouse_stock").insert({"product_name": product.name, "quantity": product.quantity, "barcode": product.barcode, "shop_name": product.shop_name}).execute()
            
        shelf_exist = supabase.table("products").select("id").eq("name", product.name).eq("shop_name", product.shop_name).execute()
        if not shelf_exist.data:
            supabase.table("products").insert({"name": product.name, "quantity": 0, "barcode": product.barcode, "buying_price": product.buying_price, "selling_price": product.selling_price, "expiry_date": product.expiry_date, "shop_name": product.shop_name}).execute()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/transfer")
def transfer_product(transfer: TransferCreate):
    try:
        w_item = supabase.table("warehouse_stock").select("quantity, barcode").eq("product_name", transfer.product_name).eq("shop_name", transfer.shop_name).execute()
        if not w_item.data or w_item.data[0]['quantity'] < transfer.quantity:
            return {"status": "error", "message": "በቂ ዕቃ ማከማቻ ውስጥ የለም!"}
        new_w_qty = w_item.data[0]['quantity'] - transfer.quantity
        barcode = w_item.data[0]['barcode']
        supabase.table("warehouse_stock").update({"quantity": new_w_qty}).eq("product_name", transfer.product_name).eq("shop_name", transfer.shop_name).execute()
        
        shelf_item = supabase.table("products").select("quantity").eq("name", transfer.product_name).eq("shop_name", transfer.shop_name).execute()
        if shelf_item.data:
            new_s_qty = shelf_item.data[0]['quantity'] + transfer.quantity
            supabase.table("products").update({"quantity": new_s_qty}).eq("name", transfer.product_name).eq("shop_name", transfer.shop_name).execute()
        else:
            supabase.table("products").insert({"name": transfer.product_name, "quantity": transfer.quantity, "barcode": barcode, "shop_name": transfer.shop_name}).execute()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/credit")
def create_credit(credit: CreditCreate):
    try:
        existing = supabase.table("customers_credit").select("id, total_debt").eq("customer_name", credit.customer_name).eq("shop_name", credit.shop_name).execute()
        if existing.data:
            new_debt = float(existing.data[0]['total_debt']) + credit.total_debt
            data = supabase.table("customers_credit").update({"total_debt": new_debt, "phone_number": credit.phone_number}).eq("id", existing.data[0]['id']).execute()
        else:
            data = supabase.table("customers_credit").insert(credit.model_dump()).execute()
        return {"status": "success", "data": data.data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/finance")
def create_finance(finance: FinanceCreate):
    try:
        data = supabase.table("finance_records").insert(finance.model_dump()).execute()
        return {"status": "success", "data": data.data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    try:
        raw_json = await request.json()
        update = Update.de_json(raw_json)
        bot.process_new_updates([update])
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
