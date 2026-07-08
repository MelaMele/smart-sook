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

@bot.callback_query_handler(func=lambda call: call.data == "check_stock")
def bot_out_of_stock(call):
    try:
        # ሁሉንም እቃዎች ከዳታቤዝ ማምጣት
        data = supabase.table("products").select("name, quantity").execute()
        
        if not data.data:
            bot.edit_message_text("በሱቁ ውስጥ ምንም የተመዘገበ ዕቃ የለም። 🛍️", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
            return
            
        response = "📦 **የሱቁ ዕቃዎች አጠቃላይ ክምችት (Stock)፦**\n\n"
        out_of_stock_warnings = ""
        
        for item in data.data:
            qty = item['quantity']
            # እቃው ካለቀ ወይም ከ 5 በታች ከሆነ ልዩ ምልክት መስጠት
            if qty == 0:
                out_of_stock_warnings += f"❌ {item['name']} - **አልቋል!** (0)\n"
            elif qty <= 5:
                out_of_stock_warnings += f"⚠️ {item['name']} - ሊያልቅ ነው! ({qty})\n"
            else:
                response += f"• {item['name']} - ብዛት፦ {qty}\n"
        
        # ማስጠንቀቂያዎች ካሉ ከላይ እንዲታዩ ማድረግ
        if out_of_stock_warnings:
            response = "🚨 **አስቸኳይ ትኩረት የሚሹ፦**\n" + out_of_stock_warnings + "\n" + response
            
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
