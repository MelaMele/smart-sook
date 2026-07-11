import os
from datetime import date, timedelta
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
import bcrypt

app = FastAPI(title="Smart Sook Multi-Shop Cloud API")

# --- 1. CONFIGURATION & CLIENTS ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not all([SUPABASE_URL, SUPABASE_KEY, TELEGRAM_TOKEN]):
    raise RuntimeError("የአካባቢ ተለዋዋጮች (Environment Variables) አልተዘጋጁም!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

# --- PASSWORD HASHING UTILS ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# --- 2. PYDANTIC SCHEMAS ---
class ShopAuth(BaseModel):
    shop_name: str
    password: str

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

# --- 3. TELEGRAM BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🚀 ስማርት ሱቅን ክፈት (Open App)", web_app=telebot.types.WebAppInfo(url="https://smart-sook.vercel.app/")))
    
    welcome_text = (
        "እንኳን ወደ **ስማርት ሱቅ ማስተዳደሪያ** በሰላም መጡ! 🛍️✨\n\n"
        "ይህ ቦት የሱቅዎን ሽያጭ፣ የዕቃ ክምችት፣ የዱቤ መዝገብ እና የደንበኞችን ትዕዛዝ በዘመናዊ መልኩ ለመቆጣጠር ይረዳዎታል።\n\n"
        "ለመጀመር ከታች ያለውን ባለቀለም አዝራር ይጫኑ፦"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# --- 4. AUTHENTICATION ENDPOINTS ---
@app.post("/api/shop/register")
def register_shop(auth: ShopAuth):
    try:
        existing = supabase.table("shop_accounts").select("shop_name").eq("shop_name", auth.shop_name).execute()
        if existing.data:
            return {"status": "error", "message": "ይህ የሱቅ ስም ቀድሞ የተመዘገበ ነው! እባክዎ ሌላ ስም ይምረጡ።"}
        
        hashed_pwd = hash_password(auth.password)
        supabase.table("shop_accounts").insert({"shop_name": auth.shop_name, "password": hashed_pwd}).execute()
        return {"status": "success", "message": "የሱቅ አካውንትዎ በተሳካ ሁኔታ ተፈጥሯል!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/shop/login")
def login_shop(auth: ShopAuth):
    try:
        data = supabase.table("shop_accounts").select("password").eq("shop_name", auth.shop_name).execute()
        if not data.data:
            return {"status": "error", "message": "የሱቅ ስሙ አልተገኘም! እባክዎ መጀመሪያ አካውንት ይፍጠሩ።"}
        
        if verify_password(auth.password, data.data[0]['password']):
            return {"status": "success", "message": "በስኬት ገብተዋል!"}
        else:
            return {"status": "error", "message": "የተሳሳተ ሚስጥር ቃል ነው!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- 5. CORE API ROUTES ---
@app.get("/", response_class=HTMLResponse)
def read_root():
    try:
        with open("api/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h3>Welcome to Smart Sook API (Index file missing)</h3>"

@app.get("/customer", response_class=HTMLResponse)
def read_customer_root():
    try:
        with open("api/customer.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h3>Customer Portal (Customer file missing)</h3>"

@app.get("/api/customer/products")
def get_active_products(shop_name: str | None = None):
    try:
        query = supabase.table("products").select("name, selling_price")
        if shop_name:
            query = query.eq("shop_name", shop_name)
        data = query.execute()
        return {"status": "success", "products": data.data}
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
            supabase.table("warehouse_stock").insert({
                "product_name": product.name, 
                "quantity": product.quantity, 
                "barcode": product.barcode, 
                "shop_name": product.shop_name
            }).execute()
            
        shelf_exist = supabase.table("products").select("id").eq("name", product.name).eq("shop_name", product.shop_name).execute()
        if not shelf_exist.data:
            supabase.table("products").insert({
                "name": product.name, 
                "quantity": 0, 
                "barcode": product.barcode, 
                "buying_price": product.buying_price, 
                "selling_price": product.selling_price, 
                "expiry_date": product.expiry_date, 
                "shop_name": product.shop_name
            }).execute()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/transfer")
def transfer_product(transfer: TransferCreate):
    try:
        w_item = supabase.table("warehouse_stock").select("*").eq("product_name", transfer.product_name).eq("shop_name", transfer.shop_name).execute()
        if not w_item.data or w_item.data[0]['quantity'] < transfer.quantity:
            return {"status": "error", "message": "በቂ ዕቃ ማከማቻ ውስጥ የለም!"}
        
        new_w_qty = w_item.data[0]['quantity'] - transfer.quantity
        supabase.table("warehouse_stock").update({"quantity": new_w_qty}).eq("product_name", transfer.product_name).eq("shop_name", transfer.shop_name).execute()
        
        shelf_item = supabase.table("products").select("quantity").eq("name", transfer.product_name).eq("shop_name", transfer.shop_name).execute()
        if shelf_item.data:
            new_s_qty = shelf_item.data[0]['quantity'] + transfer.quantity
            supabase.table("products").update({"quantity": new_s_qty}).eq("name", transfer.product_name).eq("shop_name", transfer.shop_name).execute()
        else:
            supabase.table("products").insert({
                "name": transfer.product_name, 
                "quantity": transfer.quantity, 
                "barcode": w_item.data[0].get('barcode'), 
                "shop_name": transfer.shop_name,
                "buying_price": w_item.data[0].get('buying_price', 0),
                "selling_price": w_item.data[0].get('selling_price', 0),
                "expiry_date": w_item.data[0].get('expiry_date')
            }).execute()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/credit")
def create_credit(credit: CreditCreate):
    try:
        existing = supabase.table("customers_credit").select("id, total_debt").eq("customer_name", credit.customer_name).eq("shop_name", credit.shop_name).execute()
        if existing.data:
            new_debt = float(existing.data[0]['total_debt']) + credit.total_debt
            res = supabase.table("customers_credit").update({"total_debt": new_debt, "phone_number": credit.phone_number}).eq("id", existing.data[0]['id']).execute()
        else:
            res = supabase.table("customers_credit").insert(credit.model_dump()).execute()
        return {"status": "success", "data": res.data if hasattr(res, 'data') else res}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/finance")
def create_finance(finance: FinanceCreate):
    try:
        res = supabase.table("finance_records").insert(finance.model_dump()).execute()
        return {"status": "success", "data": res.data if hasattr(res, 'data') else res}
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
