import os
from datetime import date, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update

app = FastAPI(title="Smart Sook Cloud API")

# --- 1. CONFIGURATION & CLIENTS ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

# --- 2. PYDANTIC SCHEMAS ---
class ProductCreate(BaseModel):
    name: str
    quantity: int
    barcode: str | None = None
    buying_price: float
    selling_price: float
    expiry_date: str

# --- 3. KEYBOARD MENU ---
def get_main_menu():
    markup = InlineKeyboardMarkup()
    # የቴሌግራም ሚኒ አፕ መክፈቻ ባተን
    markup.row(InlineKeyboardButton("➕ አዲስ ዕቃ መዝግብ (Mini App)", web_app=telebot.types.WebAppInfo(url="https://smart-sook.vercel.app/")))
    markup.row(InlineKeyboardButton("📦 የዕቃዎች ክምችት (Stock)", callback_data="check_stock"))
    markup.row(InlineKeyboardButton("⚠️ ኤክስፓየር ዴት (Expiry)", callback_data="check_expiry"))
    markup.row(InlineKeyboardButton("📝 የዱቤ መዝገብ (Credit)", callback_data="check_credit"))
    return markup

# --- 4. TELEGRAM BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "እንኳን ወደ ስማርት ሱቅ ማስተዳደሪያ ቦት በሰላም መጡ! 🛍️\n\nለመጠቀም ከታች ያሉትን አማራጮች ይጫኑ፦", 
        reply_markup=get_main_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data == "check_stock")
def bot_out_of_stock(call):
    try:
        data = supabase.table("products").select("name, quantity").lte("quantity", 5).execute()
        if not data.data:
            bot.edit_message_text("ክምችቱ አስተማማኝ ነው፣ ያለቀ ዕቃ የለም። ✅", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
            return
            
        response = "🚨 **ያለቁ ወይም ሊያልቁ የተቃረቡ ዕቃዎች:**\n\n"
        for item in data.data:
            response += f"• {item['name']} - የቀረው ብዛት: {item['quantity']}\n"
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        bot.edit_message_text(f"የዳታቤዝ ስህተት፦ {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "check_expiry")
def bot_check_expiry(call):
    today = date.today()
    warning_date = today + timedelta(days=30)
    try:
        data = supabase.table("products").select("name, expiry_date").lte("expiry_date", str(warning_date)).gte("expiry_date", str(today)).execute()
        if not data.data:
            bot.edit_message_text("በሚቀጥሉት 30 ቀናት ውስጥ ኤክስፓየር የሚሆን ዕቃ የለም። ✅", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
            return
            
        response = "⚠️ **ኤክስፓየር ሊሆኑ የቀረቡ ዕቃዎች:**\n\n"
        for item in data.data:
            response += f"• {item['name']} - ቀን: {item['expiry_date']}\n"
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        bot.edit_message_text(f"የዳታቤዝ ስህተት፦ {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "check_credit")
def bot_check_credit(call):
    try:
        data = supabase.table("customers_credit").select("customer_name, total_debt").gt("total_debt", 0).execute()
        if not data.data:
            bot.edit_message_text("በአሁኑ ሰዓት ምንም የዱቤ ዕዳ ያለበት ደንበኛ የለም። 🕊️", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
            return
            
        response = "📝 **የዱቤ መዝገብ (ባለዕዳዎች):**\n\n"
        for customer in data.data:
            response += f"• {customer['customer_name']} - ዕዳ: {customer['total_debt']} ብር\n"
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        bot.edit_message_text(f"የዳታቤዝ ስህተት፦ {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())

# --- 5. FASTAPI ROUTES (WEBHOOK & FRONTEND) ---
@app.get("/", response_class=HTMLResponse)
def read_root():
    """ ወደ ዋናው ሊንክ ሲገባ ሚኒ አፑን (HTML ገጹን) እንዲከፍት ማድረግ """
    try:
        with open("api/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h3>index.html ፋይል በ api/ ፎልደር ውስጥ አልተገኘም!</h3>"

@app.post("/api/products")
def create_product(product: ProductCreate):
    """ ከሚኒ አፑ የሚመጣውን ዳታ ተቀብሎ Supabase ላይ መመዝገብ """
    try:
        data = supabase.table("products").insert(product.model_dump()).execute()
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
